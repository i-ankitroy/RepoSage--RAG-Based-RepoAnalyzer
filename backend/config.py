import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(override=True)

# Base directories
HOME_DIR = Path.home()
APP_DIR = HOME_DIR / ".reposage"
CHROMA_DIR = APP_DIR / "chroma"
CLONED_REPOS_DIR = APP_DIR / "cloned_repos"

# Ensure directories exist
APP_DIR.mkdir(parents=True, exist_ok=True)
CHROMA_DIR.mkdir(parents=True, exist_ok=True)
CLONED_REPOS_DIR.mkdir(parents=True, exist_ok=True)

# API keys and URLs
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

# LLM Provider settings
# Default to NVIDIA if key is present, then Groq, otherwise fall back to Ollama
if NVIDIA_API_KEY:
    DEFAULT_LLM_PROVIDER = "nvidia"
elif GROQ_API_KEY:
    DEFAULT_LLM_PROVIDER = "groq"
else:
    DEFAULT_LLM_PROVIDER = "ollama"

# Embeddings & Reranker Settings
EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"
RERANKER_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"

# Supported file extensions for indexing
SUPPORTED_EXTENSIONS = {
    ".py", ".js", ".ts", ".go", ".java", ".cpp", ".cc", ".cxx", ".h", ".hpp", 
    ".rs", ".md", ".json", ".yaml", ".yml", ".toml", ".env.example"
}

# Directories to ignore during walking
IGNORE_DIRS = {
    ".git", "node_modules", "venv", ".venv", "env", ".env", 
    "__pycache__", "build", "dist", "out", "target", "bin", "obj", 
    ".idea", ".vscode", ".chroma", ".reposage"
}
