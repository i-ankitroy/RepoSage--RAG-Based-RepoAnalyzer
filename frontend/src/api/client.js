const BASE_URL = "http://localhost:8000";

async function apiCall(endpoint, options = {}) {
  const url = `${BASE_URL}${endpoint}`;
  
  const headers = {
    "Content-Type": "application/json",
    ...options.headers,
  };
  
  const config = {
    ...options,
    headers,
  };
  
  if (options.body && typeof options.body === "object") {
    config.body = JSON.stringify(options.body);
  }
  
  try {
    const response = await fetch(url, config);
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `API error: ${response.status} ${response.statusText}`);
    }
    return await response.json();
  } catch (error) {
    console.error(`API Call failed to ${endpoint}:`, error);
    throw error;
  }
}

export const api = {
  getHealth: () => apiCall("/health"),
  
  listRepos: () => apiCall("/repos"),
  
  indexRepo: (pathOrUrl, name) => apiCall("/repos/index", {
    method: "POST",
    body: { path_or_url: pathOrUrl, name }
  }),
  
  deleteRepo: (name) => apiCall(`/repos/${name}`, {
    method: "DELETE"
  }),
  
  queryRepo: (repo, question, topK = 5, provider = null) => apiCall("/query", {
    method: "POST",
    body: { repo, question, top_k: topK, provider }
  }),
  
  queryRepoStream: async (repo, question, onChunk, onError, provider = null, topK = 5) => {
    const url = `${BASE_URL}/query/stream`;
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          repo,
          question,
          top_k: topK,
          provider
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `API error: ${response.status} ${response.statusText}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Process SSE lines
        const lines = buffer.split("\n\n");
        // Keep the last incomplete part in the buffer
        buffer = lines.pop() || "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) continue;
          if (trimmed.startsWith("data: ")) {
            const dataStr = trimmed.slice(6).trim();
            if (dataStr) {
              try {
                const parsed = JSON.parse(dataStr);
                onChunk(parsed);
              } catch (e) {
                console.error("Error parsing stream chunk:", e);
              }
            }
          }
        }
      }
      
      // Process remaining buffer
      if (buffer.trim().startsWith("data: ")) {
        const trimmed = buffer.trim();
        const dataStr = trimmed.slice(6).trim();
        if (dataStr) {
          try {
            const parsed = JSON.parse(dataStr);
            onChunk(parsed);
          } catch (e) {
            console.error("Error parsing stream chunk:", e);
          }
        }
      }

    } catch (error) {
      console.error("Streaming query failed:", error);
      onError(error);
    }
  },
  
  getRepoFiles: (name) => apiCall(`/repos/${name}/files`),
  
  getFileContent: (name, filePath) => {
    const encodedPath = encodeURIComponent(filePath);
    return apiCall(`/repos/${name}/file-content?file_path=${encodedPath}`);
  }
};
