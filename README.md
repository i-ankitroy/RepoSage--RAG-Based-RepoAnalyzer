<<<<<<< HEAD
# RepoSage 🦉

> **Ask your codebase anything.** A developer-first, local RAG-powered Codebase Q&A engine.

RepoSage allows developers to index local directories or remote Git repositories and ask plain-English questions, receiving accurate, markdown answers with precise file and line number citations. It features a dark-first IDE-inspired three-panel layout and is designed to run entirely locally (using Ollama) or at zero cost (using free-tier Groq APIs).

---

## Key Features

- 📂 **Multi-Repo Indexing**: Index local paths or Git clone URLs directly.
- ⚡ **AST-Aware Smart Chunker**: Splits code files by function and class boundaries (built-in parser for Python, brace-scoping tracker for C-like languages).
- 🔍 **Hybrid Re-ranking**: Combines local ChromaDB vector retrieval with a Cross-Encoder reranker (`ms-marco-MiniLM`) for high-precision retrieval.
- 💬 **Interactive Chat**: Natural language Q&A with clickable code citations that load, highlight, and scroll to the exact lines in a built-in file viewer.
- 🪟 **Expandable & Resizable Code Panel**: Toggle the code viewer panel to double its size (**55% of the screen width**) or drag it manually to your desired size for enhanced readability.
- ⤶ **Line-Aligned Word Wrap**: Toggle text wrapping in the code viewer, keeping line numbers perfectly aligned with wrapped code blocks.
- ✨ **Smooth Collapse Transitions**: Sidebars collapse and expand with hardware-accelerated animations, utilizing a zero-lag transition bypass class during active resizing.
- 🛠️ **Run-From-Anywhere Import Paths**: Dynamic path-appending in main entry points allowing you to run the backend directly from the `backend/` directory or project root.
- 🌐 **Dual LLM Providers**: Seamless support for ultra-fast cloud **Groq** APIs or 100% offline local **Ollama** runs.

---

## Tech Stack

- **Backend**: FastAPI, Pydantic, ChromaDB, Typer CLI, SentenceTransformers (local CPU).
- **Frontend**: React, Vite, Lucide-React, Vanilla CSS (Premium Dark Theme).

---

## Setup Instructions

### Prerequisites
- **Python**: version 3.11+
- **Node.js**: version 18+
- (Optional) **Ollama**: running locally on `http://127.0.0.1:11434` (if running fully offline).

### 1. Backend Setup
Navigate to the `backend/` directory:
```bash
cd backend
```

Create a virtual environment and install dependencies:
```bash
python -m venv venv
# On Windows PowerShell:
.\venv\Scripts\Activate.ps1
# On macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

#### Configure Environment
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Open `.env` and add your `GROQ_API_KEY` (optional). If left blank, RepoSage will fall back to local Ollama.
*Default settings in `.env` are configured for robust Windows networking (`127.0.0.1`) and target the local **`llama3.2`** model.*

#### Install CLI Command
Install the package locally to enable the `reposage` terminal command:
```bash
pip install -e .
```

### 2. Frontend Setup
Navigate to the `frontend/` directory:
```bash
cd ../frontend
npm install
```

---

## Running the Application

### Step 1: Start the Backend API
You can run the backend server from **either** the project root folder or directly from the `backend/` folder:
```bash
# Inside backend/ folder:
python main.py

# Or from project root:
.\backend\venv\Scripts\python.exe -m backend.main
```
The server will start at `http://127.0.0.1:8000`. You can visit `http://127.0.0.1:8000/docs` to view the Swagger API details.

### Step 2: Start the React Frontend
From the `frontend/` folder:
```bash
npm run dev
```
The frontend will start at `http://localhost:5173`. Open this URL in your web browser.

---

## CLI Usage

You can also index and query codebases directly from your terminal!

1. **List collections**:
   ```bash
   reposage list
   ```

2. **Index a repository**:
   ```bash
   reposage index /path/to/local/codebase --name my-project
   # Or a Git URL:
   reposage index https://github.com/username/repo.git
   ```

3. **Ask a question**:
   ```bash
   reposage ask my-project "How is authentication handled?"
   ```

4. **Delete a collection**:
   ```bash
   reposage delete my-project
   ```

---

## Data Privacy & Directory Locations
- All database embeddings and collections are stored locally on your machine at `~/.reposage/chroma/`.
- Cloned repositories are temporarily cached at `~/.reposage/cloned_repos/`.
- RepoSage is local-first: your source code is **never** sent to any third party, except for the 5 most relevant context chunks sent to the LLM (Groq or local Ollama) during query execution.
=======
# RepoSage--RAG-Based-RepoAnalyzer
>>>>>>> b2f5d5579e8208132cb93f71671d77829c931adc
