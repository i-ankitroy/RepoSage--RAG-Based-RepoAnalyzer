from typing import List, Dict, Any

SYSTEM_PROMPT = """You are RepoSage, an expert developer assistant specialized in codebase Q&A.
Your task is to answer the user's question about the repository based ONLY on the provided source code chunks.

Follow these strict guidelines:
1. Grounding: Answer the question using ONLY the provided code snippets. Do not make up facts, functions, or file paths that are not present in the context.
2. Incomplete Context: If the provided code chunks do not contain enough information to answer the question, state: "I don't have enough context in the indexed files to answer this question."
3. Citations: When you reference code, files, or logic, cite them inline in your answer using the format `[filename:Lstart-lend]` (e.g. `[main.py:L10-25]`).
4. Output Format: You MUST respond with a valid JSON object in the following format:
{
  "answer": "Your markdown answer here. Keep it detailed and use inline citations. Use code blocks for code snippets.",
  "citations": [
    {
      "file": "path/to/file.py",
      "start_line": 10,
      "end_line": 25,
      "snippet": "exact code snippet cited (optional, keep it brief)",
      "score": 0.95
    }
  ]
}

CRITICAL JSON ESCAPING RULE:
Inside the "answer" string, you MUST escape any double quotes as \\" and any backslashes as \\\\. Do not write literal newlines inside the JSON string; represent them with \\n. Make sure the JSON object is complete and closed with a final closing brace.
Ensure that every file cited in your inline citations is present in the `citations` list.
The `score` in the citation list should reflect your estimate of how critical that code is to the answer.
"""

def build_rag_messages(query: str, chunks: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Assembles context chunks and user query into a list of messages for ChatCompletion.
    """
    # Build context string
    context_parts = []
    for idx, chunk in enumerate(chunks):
        meta = chunk["metadata"]
        score = chunk.get("rerank_score", chunk.get("distance_score", 0.0))
        
        context_parts.append(
            f"--- Context Chunk {idx+1} (File: {meta['file']}, Lines {meta['start_line']}-{meta['end_line']}, Score: {score:.3f}) ---\n"
            f"{chunk['content']}\n"
        )
        
    context_str = "\n".join(context_parts)
    
    user_prompt = (
        f"Context from codebase:\n"
        f"======================\n"
        f"{context_str}\n"
        f"======================\n\n"
        f"User Question: {query}\n\n"
        f"Generate the JSON response containing the answer and citations list."
    )
    
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ]
