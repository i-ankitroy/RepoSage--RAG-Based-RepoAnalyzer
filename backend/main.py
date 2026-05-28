import sys
from pathlib import Path

# Add project root to sys.path to allow running main.py directly
sys.path.append(str(Path(__file__).resolve().parent.parent))

import time
import os
import json
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any

from backend.models.schemas import (
    RepoIndexRequest, RepoIndexResponse,
    QueryRequest, QueryResponse,
    FileContentResponse, FileNode
)
from backend.indexer.walker import walk_directory, clone_git_repo, get_file_tree, calculate_file_hash
from backend.indexer.chunker import chunk_file
from backend.indexer.embedder import EmbedderManager
from backend.retriever.vector_store import VectorStoreManager, sanitize_collection_name
from backend.retriever.bm25 import BM25Manager
from backend.retriever.reranker import RerankerManager
from backend.generator.groq_client import LLMClient
from backend.generator.prompt_builder import build_rag_messages, build_rag_messages_stream
from backend.config import CLONED_REPOS_DIR, APP_DIR, OLLAMA_MODEL
from fastapi.responses import StreamingResponse

METADATA_DIR = APP_DIR / "metadata"
METADATA_DIR.mkdir(parents=True, exist_ok=True)


app = FastAPI(
    title="RepoSage API",
    description="Developer-first Codebase Q&A Engine API powered by local RAG.",
    version="1.0"
)

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For local-first apps, allowing all is convenient
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {"status": "healthy", "time": time.time()}

@app.post("/repos/index", response_model=RepoIndexResponse)
def index_repository(payload: RepoIndexRequest):
    path_or_url = payload.path_or_url.strip()
    repo_name = payload.name.strip()
    
    if not path_or_url or not repo_name:
        raise HTTPException(status_code=400, detail="Repository path/URL and name must be provided.")
        
    is_git_url = path_or_url.startswith(("http://", "https://", "git@", "git://"))
    
    try:
        if is_git_url:
            # Clone repo locally
            repo_path = clone_git_repo(path_or_url, repo_name)
        else:
            # Use local path
            repo_path = Path(path_or_url).resolve()
            if not repo_path.exists() or not repo_path.is_dir():
                raise HTTPException(status_code=400, detail=f"Local path '{path_or_url}' does not exist or is not a directory.")
        
        # Metadata setup for incremental indexing
        metadata_file = METADATA_DIR / f"{repo_name}.json"
        old_metadata = {}
        if metadata_file.exists():
            try:
                with open(metadata_file, "r") as f:
                    old_metadata = json.load(f)
            except Exception:
                pass

        # 1. Walk directory and filter files
        files = walk_directory(repo_path)
        if not files:
            raise HTTPException(status_code=400, detail="No supported files found in the specified repository path.")
            
        # Calculate current file hashes
        current_hashes = {}
        for f in files:
            rel = str(f.relative_to(repo_path)).replace("\\", "/")
            current_hashes[rel] = calculate_file_hash(f)

        # Check if incremental sync is possible
        is_incremental = False
        old_hashes = old_metadata.get("file_hashes", {})
        existing_repos = VectorStoreManager.list_collections()
        sanitized_name = sanitize_collection_name(repo_name)
        if sanitized_name in existing_repos and old_hashes:
            is_incremental = True

        if is_incremental:
            # Detect changes
            added_files = []
            modified_files = []
            deleted_files = []
            
            for rel, cur_h in current_hashes.items():
                if rel not in old_hashes:
                    added_files.append(rel)
                elif old_hashes[rel] != cur_h:
                    modified_files.append(rel)
                    
            for rel in old_hashes.keys():
                if rel not in current_hashes:
                    deleted_files.append(rel)
                    
            # If no changes, return early
            if not added_files and not modified_files and not deleted_files:
                return RepoIndexResponse(
                    name=repo_name,
                    status="success",
                    message="No changes detected. Codebase is already up to date.",
                    files_indexed=len(files)
                )
                
            print(f"Incremental sync: {len(added_files)} added, {len(modified_files)} modified, {len(deleted_files)} deleted.")
            
            # 1. Delete chunks of modified & deleted files from ChromaDB
            for rel in deleted_files + modified_files:
                VectorStoreManager.delete_file_chunks(repo_name, rel)
                
            # 2. Chunk and embed added & modified files
            new_chunks = []
            for rel in added_files + modified_files:
                full_path = repo_path / rel
                if full_path.exists():
                    chunks = chunk_file(full_path, rel)
                    new_chunks.extend(chunks)
                    
            if new_chunks:
                chunk_texts = [c["content"] for c in new_chunks]
                print(f"Generating embeddings for {len(chunk_texts)} new/modified chunks...")
                new_embeddings = EmbedderManager.embed_documents(chunk_texts)
                # Add to existing collection
                VectorStoreManager.add_chunks_to_existing(repo_name, new_chunks, new_embeddings)
                
            # 3. Rebuild BM25 index from all current chunks in database
            print("Rebuilding BM25 index...")
            all_current_chunks = VectorStoreManager.get_all_chunks(repo_name)
            BM25Manager.build_and_save(repo_name, all_current_chunks)
            
            # 4. Save metadata
            new_meta = {
                "repo_path": str(repo_path),
                "file_hashes": current_hashes,
                "last_indexed": time.time()
            }
            with open(metadata_file, "w") as f:
                json.dump(new_meta, f, indent=2)
                
            return RepoIndexResponse(
                name=repo_name,
                status="success",
                message=f"Incremental sync complete. Added {len(added_files)} files, modified {len(modified_files)} files, deleted {len(deleted_files)} files. Total chunks: {len(all_current_chunks)}.",
                files_indexed=len(files)
            )
        else:
            # Full indexing
            print("Performing full index...")
            all_chunks = []
            for file in files:
                rel_path = str(file.relative_to(repo_path)).replace("\\", "/")
                chunks = chunk_file(file, rel_path)
                all_chunks.extend(chunks)
                
            if not all_chunks:
                raise HTTPException(status_code=400, detail="No code chunks could be generated from the files.")
                
            # Compute Embeddings
            chunk_texts = [c["content"] for c in all_chunks]
            print(f"Generating embeddings for {len(chunk_texts)} chunks...")
            embeddings = EmbedderManager.embed_documents(chunk_texts)
            
            # Save to vector DB
            print(f"Indexing chunks in ChromaDB collection '{repo_name}'...")
            VectorStoreManager.add_repo_chunks(repo_name, str(repo_path), all_chunks, embeddings)
            
            # Build and save BM25 index from ChromaDB chunks to keep IDs aligned
            print("Building BM25 index...")
            all_current_chunks = VectorStoreManager.get_all_chunks(repo_name)
            BM25Manager.build_and_save(repo_name, all_current_chunks)
            
            # Save metadata
            new_meta = {
                "repo_path": str(repo_path),
                "file_hashes": current_hashes,
                "last_indexed": time.time()
            }
            with open(metadata_file, "w") as f:
                json.dump(new_meta, f, indent=2)
                
            return RepoIndexResponse(
                name=repo_name,
                status="success",
                message=f"Successfully indexed {len(files)} files into {len(all_chunks)} chunks.",
                files_indexed=len(files)
            )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Indexing failed: {str(e)}")

@app.get("/repos", response_model=List[str])
def list_repositories():
    try:
        return VectorStoreManager.list_collections()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list repositories: {e}")

@app.delete("/repos/{name}")
def delete_repository(name: str):
    try:
        # Get path first to check if we need to remove cloned repository folder
        repo_path_str = VectorStoreManager.get_repo_path(name)
        
        # Delete ChromaDB collection
        VectorStoreManager.delete_repo_collection(name)
        
        # Delete BM25 index
        BM25Manager.delete_index(name)
        
        # Delete metadata file
        metadata_file = METADATA_DIR / f"{name}.json"
        if metadata_file.exists():
            try:
                os.remove(metadata_file)
            except Exception:
                pass
        
        # If the repository was cloned, clean up the files from the disk
        if repo_path_str:
            repo_path = Path(repo_path_str)
            if CLONED_REPOS_DIR in repo_path.parents and repo_path.exists():
                import shutil
                shutil.rmtree(repo_path)
                
        return {"status": "success", "message": f"Repository '{name}' deleted successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete repository '{name}': {e}")

def reciprocal_rank_fusion(dense_results: List[Dict[str, Any]], sparse_results: List[Dict[str, Any]], k: int = 60, top_n: int = 20) -> List[Dict[str, Any]]:
    """
    Combines dense and sparse search results using Reciprocal Rank Fusion.
    """
    rrf_scores = {}
    doc_map = {}
    
    def get_doc_id(doc: Dict[str, Any]) -> str:
        meta = doc.get("metadata", {})
        return f"{meta.get('file', '')}:{meta.get('start_line', 0)}-{meta.get('end_line', 0)}"

    for rank, doc in enumerate(dense_results):
        doc_id = get_doc_id(doc)
        doc_map[doc_id] = doc
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (k + (rank + 1))
        
    for rank, doc in enumerate(sparse_results):
        doc_id = get_doc_id(doc)
        if doc_id not in doc_map:
            doc_map[doc_id] = doc
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (k + (rank + 1))
        
    sorted_doc_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
    
    merged_results = []
    for doc_id in sorted_doc_ids[:top_n]:
        doc = doc_map[doc_id]
        doc["rrf_score"] = rrf_scores[doc_id]
        merged_results.append(doc)
        
    return merged_results

@app.post("/query", response_model=QueryResponse)
def query_repository(payload: QueryRequest):
    repo_name = payload.repo
    question = payload.question
    top_k = payload.top_k
    
    start_time = time.perf_counter()
    
    try:
        # 1. Dense retrieval: embed query and search ChromaDB
        query_emb = EmbedderManager.embed_query(question)
        dense_candidates = VectorStoreManager.query_repo(repo_name, query_emb, top_k=30)
        
        # 2. Sparse retrieval: search BM25 index
        sparse_candidates = BM25Manager.query(repo_name, question, top_k=30)
        
        # 3. Hybrid fusion using Reciprocal Rank Fusion (RRF)
        candidates = reciprocal_rank_fusion(dense_candidates, sparse_candidates, top_n=max(top_k * 3, 20))
        
        if not candidates:
            # Return empty response if no documents found
            latency = int((time.perf_counter() - start_time) * 1000)
            return QueryResponse(
                answer="No relevant code was found in the database. Please make sure the codebase has been indexed properly.",
                citations=[],
                model="N/A",
                latency_ms=latency
            )
            
        # 4. Re-rank results
        reranked_chunks = RerankerManager.rerank(question, candidates, top_k=top_k)
        
        # 5. Generate Answer
        messages = build_rag_messages(question, reranked_chunks)
        llm_response = LLMClient.generate_completion(messages, provider=payload.provider)
        
        # Compute latency
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        
        # Map citations response
        citations = []
        for c in llm_response.get("citations", []):
            # Check if this matches a retrieved chunk to get its score
            score = 0.5
            for rc in reranked_chunks:
                if rc["metadata"]["file"] == c.get("file"):
                    score = rc.get("rerank_score", rc.get("distance_score", 0.5))
                    break
                    
            citations.append({
                "file": c.get("file", ""),
                "start_line": c.get("start_line", 0),
                "end_line": c.get("end_line", 0),
                "snippet": c.get("snippet", ""),
                "score": score
            })
            
        # If no citations were generated by LLM, let's attach our reranked ones
        if not citations and reranked_chunks:
            for rc in reranked_chunks[:2]:  # fallback top 2
                citations.append({
                    "file": rc["metadata"]["file"],
                    "start_line": rc["metadata"]["start_line"],
                    "end_line": rc["metadata"]["end_line"],
                    "snippet": rc["content"].split("\n\n", 1)[1] if "\n\n" in rc["content"] else rc["content"],
                    "score": rc.get("rerank_score", rc.get("distance_score", 0.5))
                })
        
        return QueryResponse(
            answer=llm_response.get("answer", ""),
            citations=citations,
            model=llm_response.get("model", ""),
            latency_ms=latency_ms
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")

@app.post("/query/stream")
def query_repository_stream(payload: QueryRequest):
    repo_name = payload.repo
    question = payload.question
    top_k = payload.top_k
    provider = payload.provider
    
    def event_generator():
        start_time = time.perf_counter()
        try:
            # 1. Dense retrieval
            query_emb = EmbedderManager.embed_query(question)
            dense_candidates = VectorStoreManager.query_repo(repo_name, query_emb, top_k=30)
            
            # 2. Sparse retrieval
            sparse_candidates = BM25Manager.query(repo_name, question, top_k=30)
            
            # 3. Hybrid fusion
            candidates = reciprocal_rank_fusion(dense_candidates, sparse_candidates, top_n=max(top_k * 3, 20))
            
            if not candidates:
                yield f"data: {json.dumps({'type': 'token', 'token': 'No relevant code was found in the database. Please make sure the codebase has been indexed properly.'})}\n\n"
                yield f"data: {json.dumps({'type': 'citations', 'citations': []})}\n\n"
                yield f"data: {json.dumps({'type': 'model', 'model': 'N/A'})}\n\n"
                yield f"data: {json.dumps({'type': 'latency', 'latency_ms': 0})}\n\n"
                return
                
            # 4. Re-rank results
            reranked_chunks = RerankerManager.rerank(question, candidates, top_k=top_k)
            
            # 5. Build citations
            citations = []
            for rc in reranked_chunks:
                citations.append({
                    "file": rc["metadata"]["file"],
                    "start_line": rc["metadata"]["start_line"],
                    "end_line": rc["metadata"]["end_line"],
                    "snippet": rc["content"].split("\n\n", 1)[1] if "\n\n" in rc["content"] else rc["content"],
                    "score": rc.get("rerank_score", rc.get("distance_score", 0.5))
                })
                
            messages = build_rag_messages_stream(question, reranked_chunks)
            
            # Determine actual provider string
            actual_prov = provider or LLMClient.get_provider()
            if actual_prov == "nvidia":
                model_used = f"nvidia/{os.getenv('NVIDIA_MODEL', 'openai/gpt-oss-120b')}"
            elif actual_prov == "groq":
                model_used = "llama-3.1-8b-instant"
            else:
                model_used = f"ollama/{OLLAMA_MODEL}"
            
            # Stream tokens from LLMClient
            # If provider is explicitly given, allow_fallback is set to False in LLMClient
            for chunk in LLMClient.generate_completion_stream(messages, provider=provider):
                if chunk.get("type") == "token":
                    yield f"data: {json.dumps(chunk)}\n\n"
            
            # Compute latency
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            
            # Yield metadata at the end of the stream
            yield f"data: {json.dumps({'type': 'citations', 'citations': citations})}\n\n"
            yield f"data: {json.dumps({'type': 'model', 'model': model_used})}\n\n"
            yield f"data: {json.dumps({'type': 'latency', 'latency_ms': latency_ms})}\n\n"
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            error_msg = str(e)
            yield f"data: {json.dumps({'type': 'error', 'error': error_msg})}\n\n"
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/repos/{name}/files", response_model=FileNode)
def get_repository_files(name: str):
    repo_path_str = VectorStoreManager.get_repo_path(name)
    if not repo_path_str:
        raise HTTPException(status_code=404, detail=f"Repository '{name}' not found.")
        
    repo_path = Path(repo_path_str)
    if not repo_path.exists():
        raise HTTPException(status_code=404, detail=f"Indexed directory path '{repo_path_str}' no longer exists on disk.")
        
    try:
        # Build recursive file tree dictionary
        tree = get_file_tree(repo_path, repo_path)
        return tree
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate file tree: {e}")

@app.get("/repos/{name}/file-content", response_model=FileContentResponse)
def get_file_content(name: str, file_path: str = Query(..., description="Relative file path")):
    repo_path_str = VectorStoreManager.get_repo_path(name)
    if not repo_path_str:
        raise HTTPException(status_code=404, detail=f"Repository '{name}' not found.")
        
    repo_path = Path(repo_path_str).resolve()
    target_path = (repo_path / file_path).resolve()
    
    # Security check: ensure path is within repository folder
    if not str(target_path).startswith(str(repo_path)):
        raise HTTPException(status_code=403, detail="Directory traversal is not allowed.")
        
    if not target_path.exists() or not target_path.is_file():
        raise HTTPException(status_code=404, detail=f"File '{file_path}' not found in repository.")
        
    try:
        with open(target_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            
        ext = target_path.suffix.lower()
        lang_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".go": "go",
            ".java": "java",
            ".cpp": "cpp",
            ".cc": "cpp",
            ".cxx": "cpp",
            ".h": "cpp",
            ".hpp": "cpp",
            ".rs": "rust",
            ".md": "markdown",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".toml": "toml"
        }
        language = lang_map.get(ext, "plaintext")
        
        return FileContentResponse(content=content, language=language)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
