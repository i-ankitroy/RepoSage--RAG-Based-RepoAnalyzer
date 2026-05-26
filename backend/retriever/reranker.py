from sentence_transformers import CrossEncoder
from backend.config import RERANKER_MODEL_NAME

class RerankerManager:
    _model = None

    @classmethod
    def get_model(cls) -> CrossEncoder:
        """
        Lazily load and return the CrossEncoder reranker model.
        Forces CPU usage for cheap/free local execution.
        """
        if cls._model is None:
            print(f"Loading reranker model '{RERANKER_MODEL_NAME}' on CPU...")
            cls._model = CrossEncoder(RERANKER_MODEL_NAME, device="cpu")
            print("Reranker model loaded.")
        return cls._model

    @classmethod
    def rerank(cls, query: str, candidates: list[dict], top_k: int = 5) -> list[dict]:
        """
        Re-ranks vector search candidate chunks against the user query.
        Returns the top_k most relevant chunks.
        """
        if not candidates:
            return []
            
        model = cls.get_model()
        
        # Prepare pairs for cross-encoder prediction
        pairs = [[query, candidate["content"]] for candidate in candidates]
        
        # Predict relevance scores
        scores = model.predict(pairs)
        
        # Attach scores to candidates
        for idx, score in enumerate(scores):
            # Convert float32 numpy float to native float
            candidates[idx]["rerank_score"] = float(score)
            
        # Sort candidates by rerank score descending
        sorted_candidates = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)
        
        # Return top K results
        return sorted_candidates[:top_k]
