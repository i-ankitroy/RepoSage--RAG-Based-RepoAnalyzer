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
  
  queryRepo: (repo, question, topK = 5) => apiCall("/query", {
    method: "POST",
    body: { repo, question, top_k: topK }
  }),
  
  getRepoFiles: (name) => apiCall(`/repos/${name}/files`),
  
  getFileContent: (name, filePath) => {
    const encodedPath = encodeURIComponent(filePath);
    return apiCall(`/repos/${name}/file-content?file_path=${encodedPath}`);
  }
};
