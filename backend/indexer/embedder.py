import torch
from sentence_transformers import SentenceTransformer
from backend.config import EMBEDDING_MODEL_NAME

class EmbedderManager:
    _model = None

    @classmethod
    def get_model(cls) -> SentenceTransformer:
        """
        Lazily load and return the embedding model.
        Forces CPU usage since this is meant to be run locally without requiring GPU resources.
        """
        if cls._model is None:
            print(f"Loading embedding model '{EMBEDDING_MODEL_NAME}' on CPU...")
            # Force CPU usage
            device = "cpu"
            cls._model = SentenceTransformer(EMBEDDING_MODEL_NAME, device=device)
            print("Embedding model loaded.")
        return cls._model

    @classmethod
    def embed_documents(cls, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for a list of document texts.
        """
        model = cls.get_model()
        # normalize_embeddings=True uses cosine similarity via dot product
        embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return embeddings.tolist()

    @classmethod
    def embed_query(cls, text: str) -> list[float]:
        """
        Generate embedding for a single query text.
        """
        model = cls.get_model()
        embedding = model.encode(text, normalize_embeddings=True, show_progress_bar=False)
        return embedding.tolist()
