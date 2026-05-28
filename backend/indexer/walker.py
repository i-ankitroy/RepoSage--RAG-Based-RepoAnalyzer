import os
import shutil
import git
import hashlib
from pathlib import Path
from typing import List, Union
from backend.config import SUPPORTED_EXTENSIONS, IGNORE_DIRS, CLONED_REPOS_DIR

def calculate_file_hash(file_path: Path) -> str:
    """
    Computes the SHA-256 hash of a file to check for modifications.
    """
    hasher = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception:
        return ""


def walk_directory(directory_path: Union[str, Path]) -> List[Path]:
    """
    Recursively traverse the directory, filter files by supported extensions,
    and skip ignored directories.
    """
    dir_path = Path(directory_path).resolve()
    if not dir_path.exists():
        raise FileNotFoundError(f"Directory {dir_path} does not exist.")
    
    file_paths = []
    
    for root, dirs, files in os.walk(dir_path):
        # Modify dirs in-place to avoid traversing ignored directories
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        
        for file in files:
            file_ext = Path(file).suffix.lower()
            # Include files with supported extensions or specific exceptions like .env.example
            if file_ext in SUPPORTED_EXTENSIONS or file == ".env.example":
                full_path = Path(root) / file
                file_paths.append(full_path)
                
    return file_paths

def clone_git_repo(url: str, repo_name: str) -> Path:
    """
    Clones a remote Git repository to the local app directory and returns its path.
    """
    clone_path = CLONED_REPOS_DIR / repo_name
    
    # If it already exists, remove it to do a clean clone
    if clone_path.exists():
        shutil.rmtree(clone_path)
        
    print(f"Cloning {url} to {clone_path}...")
    # Perform shallow clone (depth=1) to optimize speed and disk space
    git.Repo.clone_from(url, clone_path, depth=1)
    print("Clone complete.")
    
    return clone_path

def get_file_tree(directory_path: Union[str, Path], root_dir: Union[str, Path]) -> dict:
    """
    Recursively builds a tree structure of the directory for the React sidebar.
    """
    dir_path = Path(directory_path).resolve()
    base_path = Path(root_dir).resolve()
    
    name = dir_path.name
    rel_path = str(dir_path.relative_to(base_path)).replace("\\", "/")
    
    if dir_path.is_file():
        return {
            "name": name,
            "path": rel_path,
            "type": "file"
        }
        
    children = []
    try:
        for entry in os.scandir(dir_path):
            if entry.is_dir():
                if entry.name in IGNORE_DIRS:
                    continue
                children.append(get_file_tree(entry.path, base_path))
            elif entry.is_file():
                ext = Path(entry.name).suffix.lower()
                if ext in SUPPORTED_EXTENSIONS or entry.name == ".env.example":
                    children.append({
                        "name": entry.name,
                        "path": str(Path(entry.path).relative_to(base_path)).replace("\\", "/"),
                        "type": "file"
                    })
    except PermissionError:
        pass  # Skip directories where permission is denied
        
    # Sort: directories first, then files alphabetically
    children.sort(key=lambda x: (0 if x["type"] == "directory" else 1, x["name"].lower()))
    
    return {
        "name": name,
        "path": rel_path if rel_path != "." else "",
        "type": "directory",
        "children": children
    }
