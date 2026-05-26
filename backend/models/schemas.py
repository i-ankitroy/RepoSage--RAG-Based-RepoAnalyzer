from pydantic import BaseModel, Field
from typing import List, Optional

class RepoIndexRequest(BaseModel):
    path_or_url: str = Field(..., description="Local folder path or Git repository URL")
    name: str = Field(..., description="Unique name for the indexed repository")

class RepoIndexResponse(BaseModel):
    name: str
    status: str
    message: str
    files_indexed: int

class QueryRequest(BaseModel):
    repo: str = Field(..., description="Name of the indexed repository collection")
    question: str = Field(..., description="Natural language question about the codebase")
    top_k: int = Field(default=5, description="Number of source chunks to retrieve")

class Citation(BaseModel):
    file: str = Field(..., description="Relative file path in the repository")
    start_line: int = Field(..., description="Starting line number of the snippet")
    end_line: int = Field(..., description="Ending line number of the snippet")
    snippet: str = Field(..., description="Code snippet content")
    score: float = Field(..., description="Re-ranking relevance score")

class QueryResponse(BaseModel):
    answer: str = Field(..., description="Generated answer from the LLM")
    citations: List[Citation] = Field(..., description="List of source code citations")
    model: str = Field(..., description="LLM model used for generation")
    latency_ms: int = Field(..., description="Processing latency in milliseconds")

class FileContentRequest(BaseModel):
    repo: str
    file_path: str

class FileContentResponse(BaseModel):
    content: str
    language: str

class FileNode(BaseModel):
    name: str
    path: str
    type: str  # "file" or "directory"
    children: Optional[List["FileNode"]] = None

# Update forward references for recursive model
FileNode.model_rebuild()
