import os
import math
import re
import pickle
from pathlib import Path
from typing import List, Dict, Any
from backend.config import APP_DIR

BM25_DIR = APP_DIR / "bm25"
BM25_DIR.mkdir(parents=True, exist_ok=True)

class BM25Index:
    def __init__(self, corpus: List[Dict[str, Any]], k1: float = 1.5, b: float = 0.75):
        """
        corpus: List of dicts, each with "id", "content", "metadata"
        """
        self.k1 = k1
        self.b = b
        self.corpus_size = len(corpus)
        
        self.doc_ids = []
        self.doc_contents = []
        self.doc_metadatas = []
        self.doc_lengths = []
        
        # doc_frequencies[term] = number of documents containing term
        self.doc_frequencies = {}
        # doc_term_frequencies[i] = {term: count} for document i
        self.doc_term_frequencies = []
        
        # Tokenize and index each document
        total_length = 0
        for doc in corpus:
            doc_id = doc.get("id", "")
            content = doc.get("content", "")
            meta = doc.get("metadata", {})
            
            tokens = self.tokenize(content)
            doc_len = len(tokens)
            total_length += doc_len
            
            self.doc_ids.append(doc_id)
            self.doc_contents.append(content)
            self.doc_metadatas.append(meta)
            self.doc_lengths.append(doc_len)
            
            # Count term frequencies in this document
            tf = {}
            for token in tokens:
                tf[token] = tf.get(token, 0) + 1
            self.doc_term_frequencies.append(tf)
            
            # Count document frequency for each unique term
            for term in tf.keys():
                self.doc_frequencies[term] = self.doc_frequencies.get(term, 0) + 1
                
        self.avg_doc_length = total_length / self.corpus_size if self.corpus_size > 0 else 0
        
        # Precompute IDFs
        self.idfs = {}
        for term, df in self.doc_frequencies.items():
            # Standard BM25 IDF formula with smoothing to avoid negative values
            self.idfs[term] = math.log((self.corpus_size - df + 0.5) / (df + 0.5) + 1.0)

    @staticmethod
    def tokenize(text: str) -> List[str]:
        # Split on non-alphanumeric characters
        tokens = re.findall(r'[a-zA-Z0-9]+', text.lower())
        expanded = []
        for token in tokens:
            expanded.append(token)
            
            # Split camelCase: getUserAuthToken -> user, auth, token
            camel_parts = re.findall(r'[a-zA-Z][a-z0-9]*', token)
            if len(camel_parts) > 1:
                expanded.extend([p.lower() for p in camel_parts])
                
            # Split snake_case: user_auth_token -> user, auth, token
            snake_parts = token.split('_')
            if len(snake_parts) > 1:
                expanded.extend([p.lower() for p in snake_parts])
                
        # Return unique or multiset? For bag-of-words, we return the list of terms
        return [t for t in expanded if len(t) > 1]

    def search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        query_tokens = self.tokenize(query)
        if not query_tokens:
            return []
            
        scores = []
        for i in range(self.corpus_size):
            score = 0.0
            doc_len = self.doc_lengths[i]
            tf_dict = self.doc_term_frequencies[i]
            
            # If doc length is 0, score is 0
            if doc_len == 0:
                continue
                
            for token in query_tokens:
                if token in tf_dict:
                    tf = tf_dict[token]
                    idf = self.idfs.get(token, 0.0)
                    
                    # BM25 term score formula
                    numerator = tf * (self.k1 + 1.0)
                    denominator = tf + self.k1 * (1.0 - self.b + self.b * (doc_len / self.avg_doc_length))
                    score += idf * (numerator / denominator)
            
            # Only keep positive scores
            if score > 0:
                scores.append((score, i))
                
        # Sort by score descending
        scores.sort(key=lambda x: x[0], reverse=True)
        top_scores = scores[:top_k]
        
        results = []
        for score, idx in top_scores:
            results.append({
                "id": self.doc_ids[idx],
                "content": self.doc_contents[idx],
                "metadata": self.doc_metadatas[idx],
                "distance_score": score  # Return BM25 score as score representation
            })
        return results

class BM25Manager:
    @classmethod
    def get_index_path(cls, repo_name: str) -> Path:
        return BM25_DIR / f"{repo_name}.pkl"

    @classmethod
    def build_and_save(cls, repo_name: str, chunks: List[Dict[str, Any]]) -> None:
        """
        Builds a BM25Index from chunks and pickles it to disk.
        """
        formatted_chunks = []
        for i, chunk in enumerate(chunks):
            formatted_chunks.append({
                "id": chunk.get("id", f"chunk_{i}"),
                "content": chunk.get("content", ""),
                "metadata": chunk.get("metadata", {})
            })
            
        index = BM25Index(formatted_chunks)
        path = cls.get_index_path(repo_name)
        with open(path, "wb") as f:
            pickle.dump(index, f)

    @classmethod
    def query(cls, repo_name: str, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        path = cls.get_index_path(repo_name)
        if not path.exists():
            return []
            
        try:
            with open(path, "rb") as f:
                index = pickle.load(f)
            return index.search(query, top_k=top_k)
        except Exception as e:
            print(f"Error reading BM25 index for {repo_name}: {e}")
            return []

    @classmethod
    def delete_index(cls, repo_name: str) -> None:
        path = cls.get_index_path(repo_name)
        if path.exists():
            try:
                os.remove(path)
            except Exception:
                pass
