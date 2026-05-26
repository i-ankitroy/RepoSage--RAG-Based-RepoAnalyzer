import sys
import time
from pathlib import Path

# Add project root to sys.path to allow running cli.py directly
sys.path.append(str(Path(__file__).resolve().parent.parent))

import typer
from typing import Optional

from backend.indexer.walker import walk_directory, clone_git_repo
from backend.indexer.chunker import chunk_file
from backend.indexer.embedder import EmbedderManager
from backend.retriever.vector_store import VectorStoreManager
from backend.retriever.reranker import RerankerManager
from backend.generator.groq_client import LLMClient
from backend.generator.prompt_builder import build_rag_messages

cli_app = typer.Typer(name="reposage", help="RepoSage: Ask your codebase anything.")

@cli_app.command()
def index(
    path_or_url: str = typer.Argument(..., help="Path to local folder or Git repository URL"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Unique name for the collection. Defaults to directory/repo name.")
):
    """
    Indexes a repository's code files into a local ChromaDB collection.
    """
    path_or_url = path_or_url.strip()
    
    # Generate name from path or url if not specified
    if not name:
        if path_or_url.endswith(".git"):
            name = Path(path_or_url[:-4]).name
        else:
            name = Path(path_or_url).name
            
    name = name.strip()
    
    is_git_url = path_or_url.startswith(("http://", "https://", "git@", "git://"))
    
    typer.echo(f"Indexing repository '{name}'...")
    
    try:
        if is_git_url:
            typer.echo("Cloning git repository (this might take a few seconds)...")
            repo_path = clone_git_repo(path_or_url, name)
        else:
            repo_path = Path(path_or_url).resolve()
            if not repo_path.exists() or not repo_path.is_dir():
                typer.secho(f"Error: Directory '{path_or_url}' does not exist.", fg=typer.colors.RED)
                raise typer.Exit(1)

        typer.echo("Scanning for supported code files...")
        files = walk_directory(repo_path)
        if not files:
            typer.secho("Error: No supported files found in this directory.", fg=typer.colors.RED)
            raise typer.Exit(1)
            
        typer.echo(f"Found {len(files)} files. Extracting code chunks...")
        
        all_chunks = []
        with typer.progressbar(files, label="Chunking files") as progress:
            for file in progress:
                rel_path = str(file.relative_to(repo_path)).replace("\\", "/")
                chunks = chunk_file(file, rel_path)
                all_chunks.extend(chunks)
                
        if not all_chunks:
            typer.secho("Error: No code chunks could be generated.", fg=typer.colors.RED)
            raise typer.Exit(1)
            
        typer.echo(f"Generated {len(all_chunks)} chunks. Generating embeddings and building index...")
        chunk_texts = [c["content"] for c in all_chunks]
        
        # This will download the sentence transformer model if not present
        embeddings = EmbedderManager.embed_documents(chunk_texts)
        
        typer.echo("Saving to local database...")
        VectorStoreManager.add_repo_chunks(name, str(repo_path), all_chunks, embeddings)
        
        typer.secho(f"Success! Repository '{name}' successfully indexed. {len(files)} files, {len(all_chunks)} chunks.", fg=typer.colors.GREEN, bold=True)
        
    except Exception as e:
        typer.secho(f"Indexing failed: {e}", fg=typer.colors.RED, bold=True)
        raise typer.Exit(1)

@cli_app.command()
def ask(
    repo: str = typer.Argument(..., help="Name of the indexed collection"),
    question: str = typer.Argument(..., help="Question to ask about the codebase"),
    top_k: int = typer.Option(5, "--top-k", "-k", help="Number of code chunks to retrieve")
):
    """
    Queries an indexed repository using semantic search and local/Groq LLM.
    """
    try:
        # Check if repo exists
        collections = VectorStoreManager.list_collections()
        sanitized_name = repo.lower().replace("_", "-").replace(" ", "-") # Simple check matching sanitize
        
        # Try exact or sanitized match
        matched_collection = None
        for c in collections:
            if c == repo or c == sanitized_name:
                matched_collection = c
                break
                
        if not matched_collection:
            typer.secho(f"Error: Collection '{repo}' not found. Available collections: {collections}", fg=typer.colors.RED)
            raise typer.Exit(1)
            
        typer.echo(f"Searching index for: '{question}'...")
        start_time = time.perf_counter()
        
        # 1. Embed query
        query_emb = EmbedderManager.embed_query(question)
        
        # 2. Retrieve
        candidates = VectorStoreManager.query_repo(matched_collection, query_emb, top_k=max(top_k * 3, 10))
        if not candidates:
            typer.secho("No relevant code snippets found.", fg=typer.colors.YELLOW)
            raise typer.Exit(0)
            
        # 3. Rerank
        reranked_chunks = RerankerManager.rerank(question, candidates, top_k=top_k)
        
        # 4. Generate answer
        typer.echo("Generating answer...")
        messages = build_rag_messages(question, reranked_chunks)
        llm_response = LLMClient.generate_completion(messages)
        
        latency = time.perf_counter() - start_time
        
        # Print results
        typer.echo("\n" + "="*80)
        typer.secho("ANSWER:", fg=typer.colors.GREEN, bold=True)
        typer.echo("="*80)
        typer.echo(llm_response.get("answer", ""))
        typer.echo("="*80 + "\n")
        
        typer.secho("CITATIONS:", fg=typer.colors.CYAN, bold=True)
        citations = llm_response.get("citations", [])
        if not citations:
            # Fallback to top 2 retrieved sources
            for rc in reranked_chunks[:2]:
                meta = rc["metadata"]
                typer.echo(f"- {meta['file']} (Lines {meta['start_line']}-{meta['end_line']}) [Score: {rc.get('rerank_score', 0.5):.2f}]")
        else:
            for idx, c in enumerate(citations):
                typer.echo(f"[{idx+1}] {c.get('file')} (Lines {c.get('start_line')}-{c.get('end_line')})")
                
        typer.echo(f"\nModel: {llm_response.get('model')} | Latency: {latency:.2f}s")
        
    except Exception as e:
        typer.secho(f"Query failed: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)

@cli_app.command()
def list():
    """
    Lists all indexed repositories.
    """
    try:
        collections = VectorStoreManager.list_collections()
        if not collections:
            typer.echo("No repositories indexed yet. Use 'reposage index <path>' to start.")
        else:
            typer.echo("Indexed repositories:")
            for col in collections:
                path = VectorStoreManager.get_repo_path(col)
                typer.echo(f"  • {col} (Path: {path})")
    except Exception as e:
        typer.secho(f"Error listing collections: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)

@cli_app.command()
def delete(
    name: str = typer.Argument(..., help="Name of the repository index to delete")
):
    """
    Deletes an indexed repository.
    """
    try:
        collections = VectorStoreManager.list_collections()
        if name not in collections:
            # Try to match sanitized name
            from backend.retriever.vector_store import sanitize_collection_name
            san_name = sanitize_collection_name(name)
            if san_name not in collections:
                typer.secho(f"Error: Collection '{name}' does not exist.", fg=typer.colors.RED)
                raise typer.Exit(1)
            name = san_name
            
        repo_path_str = VectorStoreManager.get_repo_path(name)
        VectorStoreManager.delete_repo_collection(name)
        
        # Clean up files if it was a Git clone
        if repo_path_str:
            repo_path = Path(repo_path_str)
            if CLONED_REPOS_DIR in repo_path.parents and repo_path.exists():
                import shutil
                shutil.rmtree(repo_path)
                
        typer.secho(f"Deleted index and data for '{name}'.", fg=typer.colors.GREEN)
    except Exception as e:
        typer.secho(f"Error deleting collection: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)

if __name__ == "__main__":
    cli_app()
