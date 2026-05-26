import ast
import re
from pathlib import Path
from typing import List, Dict, Any

def get_python_chunks(content: str, rel_path: str) -> List[Dict[str, Any]]:
    """
    Extract chunks from Python files using the AST module.
    """
    chunks = []
    lines = content.splitlines()
    total_lines = len(lines)
    
    try:
        tree = ast.parse(content)
    except SyntaxError:
        # Fallback to sliding window if syntax is invalid
        return get_sliding_window_chunks(content, rel_path)

    # Track covered lines to identify global/module-level code
    covered_lines = set()
    
    # Inner helper to add a chunk
    def add_chunk(start_line: int, end_line: int, chunk_type: str):
        # 1-based indexing for lines
        start_idx = max(0, start_line - 1)
        end_idx = min(total_lines, end_line)
        chunk_lines = lines[start_idx:end_idx]
        snippet = "\n".join(chunk_lines)
        
        # Don't add empty or trivial chunks
        if len(snippet.strip()) < 20:
            return
            
        chunks.append({
            "content": f"# File: {rel_path} (Lines {start_line}-{end_line})\n# Type: {chunk_type}\n\n{snippet}",
            "metadata": {
                "file": rel_path,
                "start_line": start_line,
                "end_line": end_line,
                "language": "python"
            }
        })
        for i in range(start_line, end_line + 1):
            covered_lines.add(i)

    # Walk AST and find classes and functions
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            # lineno and end_lineno are available in Python 3.8+
            start = node.lineno
            end = getattr(node, "end_lineno", start + 5)
            
            # For classes, we might want to also index the class itself
            # For functions, we index the function definition
            node_type = "class" if isinstance(node, ast.ClassDef) else "function"
            add_chunk(start, end, node_type)

    # Chunk the remaining uncovered lines (globals, imports, etc.)
    uncovered_start = None
    for i in range(1, total_lines + 1):
        if i not in covered_lines:
            if uncovered_start is None:
                uncovered_start = i
        else:
            if uncovered_start is not None:
                add_chunk(uncovered_start, i - 1, "module_code")
                uncovered_start = None
                
    if uncovered_start is not None:
        add_chunk(uncovered_start, total_lines, "module_code")
        
    return chunks if chunks else get_sliding_window_chunks(content, rel_path)


def get_brace_chunks(content: str, rel_path: str, lang: str) -> List[Dict[str, Any]]:
    """
    Extract chunks from brace-based languages (JS, TS, C++, Java, Go, Rust).
    It tracks curly braces {} to identify functions/classes.
    """
    chunks = []
    lines = content.splitlines()
    total_lines = len(lines)
    
    # We will scan character by character to find block boundaries
    brace_level = 0
    block_start_line = 0
    in_string = False
    string_char = None
    in_comment = False
    in_multiline_comment = False
    
    # Track block candidates: (start_line, end_line)
    blocks = []
    
    # Simply track lines where we see level transitions
    # To keep it robust, let's scan line-by-line and count braces, ignoring string literals
    for line_idx, line in enumerate(lines):
        # Simple string/comment escaping for brace matching
        i = 0
        while i < len(line):
            char = line[i]
            
            # Handle comments
            if not in_string:
                if in_multiline_comment:
                    if i + 1 < len(line) and line[i:i+2] == "*/":
                        in_multiline_comment = False
                        i += 2
                        continue
                elif i + 1 < len(line) and line[i:i+2] == "//":
                    break  # rest of the line is a comment
                elif i + 1 < len(line) and line[i:i+2] == "/*":
                    in_multiline_comment = True
                    i += 2
                    continue
                    
            if in_multiline_comment:
                i += 1
                continue
                
            # Handle strings
            if char in ('"', "'", "`"):
                if not in_string:
                    in_string = True
                    string_char = char
                elif string_char == char:
                    # Check for escape backslash
                    escaped = False
                    k = i - 1
                    while k >= 0 and line[k] == "\\":
                        escaped = not escaped
                        k -= 1
                    if not escaped:
                        in_string = False
                i += 1
                continue
                
            if in_string:
                i += 1
                continue
                
            # Count braces
            if char == "{":
                if brace_level == 0:
                    # Capture definition leading up to block
                    block_start_line = max(0, line_idx - 2) # Include up to 2 lines prior for signature
                brace_level += 1
            elif char == "}":
                brace_level -= 1
                if brace_level == 0:
                    # End of a top-level block
                    blocks.append((block_start_line + 1, line_idx + 1))
            i += 1
            
    # Add blocks as chunks
    covered_lines = set()
    for start, end in blocks:
        # Don't add tiny blocks (less than 4 lines)
        if end - start < 3:
            continue
            
        snippet = "\n".join(lines[start-1:end])
        if len(snippet.strip()) < 30:
            continue
            
        chunks.append({
            "content": f"// File: {rel_path} (Lines {start}-{end})\n// Language: {lang}\n\n{snippet}",
            "metadata": {
                "file": rel_path,
                "start_line": start,
                "end_line": end,
                "language": lang
            }
        })
        for l in range(start, end + 1):
            covered_lines.add(l)
            
    # Fill in uncovered lines with sliding window
    uncovered_start = None
    for i in range(1, total_lines + 1):
        if i not in covered_lines:
            if uncovered_start is None:
                uncovered_start = i
        else:
            if uncovered_start is not None:
                # Add uncovered block
                snippet = "\n".join(lines[uncovered_start-1:i-1])
                if len(snippet.strip()) > 20:
                    chunks.append({
                        "content": f"// File: {rel_path} (Lines {uncovered_start}-{i-1})\n\n{snippet}",
                        "metadata": {
                            "file": rel_path,
                            "start_line": uncovered_start,
                            "end_line": i - 1,
                            "language": lang
                        }
                    })
                uncovered_start = None
                
    if uncovered_start is not None:
        snippet = "\n".join(lines[uncovered_start-1:total_lines])
        if len(snippet.strip()) > 20:
            chunks.append({
                "content": f"// File: {rel_path} (Lines {uncovered_start}-{total_lines})\n\n{snippet}",
                "metadata": {
                    "file": rel_path,
                    "start_line": uncovered_start,
                    "end_line": total_lines,
                    "language": lang
                }
            })
            
    return chunks if chunks else get_sliding_window_chunks(content, rel_path, lang)


def get_sliding_window_chunks(content: str, rel_path: str, lang: str = "text", window_size: int = 30, overlap: int = 5) -> List[Dict[str, Any]]:
    """
    Standard sliding window of lines as a fallback for any language.
    """
    chunks = []
    lines = content.splitlines()
    total_lines = len(lines)
    
    if total_lines == 0:
        return []
        
    comment_char = "#" if lang in ("python", "yaml", "toml", "dockerfile", "text") else "//"
    if lang == "markdown":
        comment_char = "<!--"
        comment_end = "-->"
    else:
        comment_end = ""
        
    step = window_size - overlap
    for start_idx in range(0, total_lines, step):
        end_idx = min(start_idx + window_size, total_lines)
        chunk_lines = lines[start_idx:end_idx]
        snippet = "\n".join(chunk_lines)
        
        if len(snippet.strip()) < 20:
            continue
            
        start_line = start_idx + 1
        end_line = end_idx
        
        comment_header = f"{comment_char} File: {rel_path} (Lines {start_line}-{end_line}){comment_end}"
        
        chunks.append({
            "content": f"{comment_header}\n\n{snippet}",
            "metadata": {
                "file": rel_path,
                "start_line": start_line,
                "end_line": end_line,
                "language": lang
            }
        })
        
        if end_idx == total_lines:
            break
            
    return chunks


def chunk_file(file_path: Path, relative_path: str) -> List[Dict[str, Any]]:
    """
    Intelligently split a file into chunks based on language syntax.
    """
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return []
        
    ext = file_path.suffix.lower()
    
    if ext == ".py":
        return get_python_chunks(content, relative_path)
    elif ext in (".js", ".ts", ".go", ".java", ".cpp", ".cc", ".cxx", ".rs", ".h", ".hpp"):
        lang_map = {
            ".js": "javascript",
            ".ts": "typescript",
            ".go": "go",
            ".java": "java",
            ".cpp": "cpp",
            ".cc": "cpp",
            ".cxx": "cpp",
            ".h": "cpp",
            ".hpp": "cpp",
            ".rs": "rust"
        }
        return get_brace_chunks(content, relative_path, lang_map.get(ext, "code"))
    elif ext == ".md":
        return get_sliding_window_chunks(content, relative_path, "markdown")
    elif ext in (".json", ".yaml", ".yml", ".toml", ".env.example"):
        lang_map = {
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".toml": "toml",
            ".env.example": "dotenv"
        }
        return get_sliding_window_chunks(content, relative_path, lang_map.get(ext, "data"), window_size=40, overlap=5)
    else:
        return get_sliding_window_chunks(content, relative_path, "text")
