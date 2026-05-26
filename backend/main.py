import sys
from pathlib import Path

# Add project root to sys.path to allow running main.py directly
sys.path.append(str(Path(__file__).resolve().parent.parent))

import time
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List

from backend.models.schemas import (
    RepoIndexRequest, RepoIndexResponse,
    QueryRequest, QueryResponse,
    FileContentResponse, FileNode
)
from backend.indexer.walker import walk_directory, clone_git_repo, get_file_tree
from backend.indexer.chunker import chunk_file
from backend.indexer.embedder import EmbedderManager
from backend.retriever.vector_store import VectorStoreManager
from backend.retriever.reranker import RerankerManager
from backend.generator.groq_client import LLMClient
from backend.generator.prompt_builder import build_rag_messages
from backend.config import CLONED_REPOS_DIR

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
        
        # 1. Walk directory and filter files
        files = walk_directory(repo_path)
        if not files:
            raise HTTPException(status_code=400, detail="No supported files found in the specified repository path.")
            
        # 2. Chunk files
        all_chunks = []
        for file in files:
            rel_path = str(file.relative_to(repo_path)).replace("\\", "/")
            chunks = chunk_file(file, rel_path)
            all_chunks.extend(chunks)
            
        if not all_chunks:
            raise HTTPException(status_code=400, detail="No code chunks could be generated from the files.")
            
        # 3. Compute Embeddings
        chunk_texts = [c["content"] for c in all_chunks]
        print(f"Generating embeddings for {len(chunk_texts)} chunks...")
        embeddings = EmbedderManager.embed_documents(chunk_texts)
        
        # 4. Save to vector DB
        print(f"Indexing chunks in ChromaDB collection '{repo_name}'...")
        VectorStoreManager.add_repo_chunks(repo_name, str(repo_path), all_chunks, embeddings)
        
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
        
        # If the repository was cloned, clean up the files from the disk
        if repo_path_str:
            repo_path = Path(repo_path_str)
            if CLONED_REPOS_DIR in repo_path.parents and repo_path.exists():
                import shutil
                shutil.rmtree(repo_path)
                
        return {"status": "success", "message": f"Repository '{name}' deleted successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete repository '{name}': {e}")

@app.post("/query", response_model=QueryResponse)
def query_repository(payload: QueryRequest):
    repo_name = payload.repo
    question = payload.question
    top_k = payload.top_k
    
    start_time = time.perf_counter()
    
    try:
        # 1. Embed query
        query_emb = EmbedderManager.embed_query(question)
        
        # 2. Retrieve candidates (retrieve top_k * 3 for reranking)
        candidates = VectorStoreManager.query_repo(repo_name, query_emb, top_k=max(top_k * 3, 10))
        
        if not candidates:
            # Return empty response if no documents found
            latency = int((time.perf_counter() - start_time) * 1000)
            return QueryResponse(
                answer="No relevant code was found in the database. Please make sure the codebase has been indexed properly.",
                citations=[],
                model="N/A",
                latency_ms=latency
            )
            
        # 3. Re-rank results
        reranked_chunks = RerankerManager.rerank(question, candidates, top_k=top_k)
        
        # 4. Generate Answer
        messages = build_rag_messages(question, reranked_chunks)
        llm_response = LLMClient.generate_completion(messages)
        
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
