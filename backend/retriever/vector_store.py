import re
import chromadb
from typing import List, Dict, Any
from backend.config import CHROMA_DIR

def sanitize_collection_name(name: str) -> str:
    """
    Sanitizes repository name to meet ChromaDB collection name requirements:
    - 3-63 characters
    - Starts and ends with alphanumeric
    - Contains only alphanumeric, underscores, or hyphens
    - No consecutive dots
    """
    # Replace invalid characters with hyphens
    sanitized = re.sub(r"[^a-zA-Z0-9_-]", "-", name)
    # Ensure it starts with alphanumeric
    sanitized = re.sub(r"^[^a-zA-Z0-9]+", "", sanitized)
    # Ensure it ends with alphanumeric
    sanitized = re.sub(r"[^a-zA-Z0-9]+$", "", sanitized)
    # Convert to lowercase
    sanitized = sanitized.lower()
    
    # Pad if too short
    if len(sanitized) < 3:
        sanitized = f"repo-{sanitized}"
    # Truncate if too long
    if len(sanitized) > 63:
        sanitized = sanitized[:63]
        
    return sanitized

class VectorStoreManager:
    _client = None

    @classmethod
    def get_client(cls) -> chromadb.PersistentClient:
        """
        Lazily initialize and return the persistent ChromaDB client.
        """
        if cls._client is None:
            cls._client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        return cls._client

    @classmethod
    def add_repo_chunks(cls, repo_name: str, repo_path: str, chunks: List[Dict[str, Any]], embeddings: List[List[float]]) -> None:
        """
        Inserts chunks and their pre-computed embeddings into a ChromaDB collection.
        Overwrites the collection if it already exists to ensure a clean re-indexing.
        Stores the repository's path in the collection metadata.
        """
        client = cls.get_client()
        collection_name = sanitize_collection_name(repo_name)
        
        # If collection exists, delete it first for clean indexing
        try:
            client.delete_collection(name=collection_name)
        except Exception:
            pass  # Does not exist
            
        collection = client.create_collection(
            name=collection_name, 
            metadata={"path": str(repo_path)}
        )
        
        ids = [f"chunk_{i}" for i in range(len(chunks))]
        documents = [c["content"] for c in chunks]
        metadatas = [c["metadata"] for c in chunks]
        
        # ChromaDB allows batching, but since we are running locally, 
        # let's add in batches of 500 to avoid any maximum request size constraints
        batch_size = 500
        for i in range(0, len(chunks), batch_size):
            end_idx = min(i + batch_size, len(chunks))
            collection.add(
                ids=ids[i:end_idx],
                embeddings=embeddings[i:end_idx],
                documents=documents[i:end_idx],
                metadatas=metadatas[i:end_idx]
            )

    @classmethod
    def get_repo_path(cls, repo_name: str) -> str:
        """
        Retrieves the repository path stored in the collection metadata.
        """
        client = cls.get_client()
        collection_name = sanitize_collection_name(repo_name)
        try:
            collection = client.get_collection(name=collection_name)
            if collection.metadata and "path" in collection.metadata:
                return collection.metadata["path"]
            return ""
        except Exception:
            return ""

    @classmethod
    def query_repo(cls, repo_name: str, query_embedding: List[float], top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Retrieves top_k similar chunks from ChromaDB for a query embedding.
        """
        client = cls.get_client()
        collection_name = sanitize_collection_name(repo_name)
        
        try:
            collection = client.get_collection(name=collection_name)
        except Exception as e:
            raise ValueError(f"Repository '{repo_name}' has not been indexed yet. Details: {e}")
            
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k
        )
        
        # Format the query results nicely
        formatted_results = []
        if results and "documents" in results and results["documents"]:
            docs = results["documents"][0]
            metas = results["metadatas"][0]
            ids = results["ids"][0]
            distances = results["distances"][0] if "distances" in results else [0.0] * len(docs)
            
            for doc, meta, cid, dist in zip(docs, metas, ids, distances):
                # Convert distance to similarity score
                similarity = 1.0 - min(max(dist, 0.0), 1.0)
                formatted_results.append({
                    "id": cid,
                    "content": doc,
                    "metadata": meta,
                    "distance_score": similarity
                })
                
        return formatted_results

    @classmethod
    def delete_repo_collection(cls, repo_name: str) -> None:
        """
        Deletes a repository collection from ChromaDB.
        """
        client = cls.get_client()
        collection_name = sanitize_collection_name(repo_name)
        client.delete_collection(name=collection_name)

    @classmethod
    def list_collections(cls) -> List[str]:
        """
        Lists all collections (indexed repos) stored in ChromaDB.
        """
        client = cls.get_client()
        collections = client.list_collections()
        return [c.name for c in collections]

    @classmethod
    def delete_file_chunks(cls, repo_name: str, relative_file_path: str) -> None:
        """
        Deletes all chunks associated with a specific file from the repository's collection.
        """
        client = cls.get_client()
        collection_name = sanitize_collection_name(repo_name)
        try:
            collection = client.get_collection(name=collection_name)
            collection.delete(where={"file": relative_file_path})
        except Exception as e:
            print(f"Error deleting chunks for file {relative_file_path} in collection {repo_name}: {e}")

    @classmethod
    def add_chunks_to_existing(cls, repo_name: str, chunks: List[Dict[str, Any]], embeddings: List[List[float]]) -> None:
        """
        Appends chunks to an existing ChromaDB collection using unique IDs.
        """
        client = cls.get_client()
        collection_name = sanitize_collection_name(repo_name)
        collection = client.get_collection(name=collection_name)
        
        import uuid
        ids = [f"chunk_{uuid.uuid4().hex[:12]}" for _ in range(len(chunks))]
        documents = [c["content"] for c in chunks]
        metadatas = [c["metadata"] for c in chunks]
        
        batch_size = 500
        for i in range(0, len(chunks), batch_size):
            end_idx = min(i + batch_size, len(chunks))
            collection.add(
                ids=ids[i:end_idx],
                embeddings=embeddings[i:end_idx],
                documents=documents[i:end_idx],
                metadatas=metadatas[i:end_idx]
            )

    @classmethod
    def get_all_chunks(cls, repo_name: str) -> List[Dict[str, Any]]:
        """
        Retrieves all documents and metadatas from the ChromaDB collection to rebuild the BM25 index.
        """
        client = cls.get_client()
        collection_name = sanitize_collection_name(repo_name)
        try:
            collection = client.get_collection(name=collection_name)
            results = collection.get(include=["documents", "metadatas"])
            chunks = []
            if results and "documents" in results and results["documents"]:
                for cid, doc, meta in zip(results["ids"], results["documents"], results["metadatas"]):
                    chunks.append({
                        "id": cid,
                        "content": doc,
                        "metadata": meta
                    })
            return chunks
        except Exception as e:
            print(f"Error fetching all chunks for {repo_name}: {e}")
            return []


