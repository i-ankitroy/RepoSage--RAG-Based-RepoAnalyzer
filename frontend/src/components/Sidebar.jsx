import React, { useState, useEffect } from "react";
import { 
  Folder, FolderOpen, FileCode, FileText, 
  Plus, Trash2, ChevronRight, ChevronLeft, ChevronDown, 
  Loader2, GitBranch, Sparkles
} from "lucide-react";
import { api } from "../api/client";

export default function Sidebar({ 
  selectedRepo, 
  setSelectedRepo, 
  onFileSelect, 
  activeFile,
  onCollapse,
  isCollapsed
}) {
  const [repos, setRepos] = useState([]);
  const [pathOrUrl, setPathOrUrl] = useState("");
  const [customName, setCustomName] = useState("");
  const [isIndexing, setIsIndexing] = useState(false);
  const [indexingStatus, setIndexingStatus] = useState("");
  const [fileTree, setFileTree] = useState(null);
  const [expandedNodes, setExpandedNodes] = useState({});

  useEffect(() => {
    fetchRepos();
  }, []);

  useEffect(() => {
    if (selectedRepo) {
      fetchFileTree(selectedRepo);
    } else {
      setFileTree(null);
    }
  }, [selectedRepo]);

  const fetchRepos = async () => {
    try {
      const data = await api.listRepos();
      setRepos(data);
      if (data.length > 0 && !selectedRepo) {
        setSelectedRepo(data[0]);
      }
    } catch (error) {
      console.error("Failed to load repositories:", error);
    }
  };

  const fetchFileTree = async (repoName) => {
    try {
      const tree = await api.getRepoFiles(repoName);
      setFileTree(tree);
      // Auto-expand root
      setExpandedNodes({ "": true });
    } catch (error) {
      console.error("Failed to load file tree:", error);
      setFileTree(null);
    }
  };

  const handleIndex = async (e) => {
    e.preventDefault();
    if (!pathOrUrl.trim()) return;

    setIsIndexing(true);
    setIndexingStatus("Scanning & Chunking...");
    
    // Auto-generate name if empty
    let name = customName.trim();
    if (!name) {
      const cleanPath = pathOrUrl.trim().replace(/\/$/, "");
      if (cleanPath.endsWith(".git")) {
        name = cleanPath.split("/").pop().replace(".git", "");
      } else {
        name = cleanPath.split(/[/\\]/).pop();
      }
    }

    try {
      setIndexingStatus("Embedding & Indexing (this takes a moment)...");
      const result = await api.indexRepo(pathOrUrl.trim(), name);
      setPathOrUrl("");
      setCustomName("");
      await fetchRepos();
      setSelectedRepo(name);
      alert(`Success! Indexed ${result.files_indexed} files.`);
    } catch (error) {
      alert(`Indexing failed: ${error.message}`);
    } finally {
      setIsIndexing(false);
      setIndexingStatus("");
    }
  };

  const handleDelete = async () => {
    if (!selectedRepo) return;
    if (!confirm(`Are you sure you want to delete the index for '${selectedRepo}'?`)) return;

    try {
      await api.deleteRepo(selectedRepo);
      const remainingRepos = repos.filter(r => r !== selectedRepo);
      setRepos(remainingRepos);
      setSelectedRepo(remainingRepos.length > 0 ? remainingRepos[0] : "");
    } catch (error) {
      alert(`Delete failed: ${error.message}`);
    }
  };

  const toggleNode = (path) => {
    setExpandedNodes(prev => ({
      ...prev,
      [path]: !prev[path]
    }));
  };

  // Helper to determine icon based on file extension
  const getFileIcon = (fileName) => {
    const ext = fileName.split(".").pop().toLowerCase();
    const codeExtensions = ["py", "js", "ts", "jsx", "tsx", "go", "java", "cpp", "cc", "rs", "json", "yaml", "yml", "toml"];
    if (codeExtensions.includes(ext)) {
      return <FileCode size={15} style={{ color: "var(--accent)" }} />;
    }
    return <FileText size={15} style={{ color: "var(--text-muted)" }} />;
  };

  // Recursive Tree Node Renderer
  const renderTreeNode = (node) => {
    const isDir = node.type === "directory";
    const isExpanded = expandedNodes[node.path];
    const isActive = activeFile === node.path;
    
    // Skip empty paths or folder root itself to display children directly at top level
    if (node.path === "" && isDir) {
      return node.children ? node.children.map(child => renderTreeNode(child)) : null;
    }

    const handleClick = () => {
      if (isDir) {
        toggleNode(node.path);
      } else {
        onFileSelect(node.path);
      }
    };

    return (
      <div key={node.path} className="tree-node">
        <div 
          className={`tree-node-row ${isActive ? "active-file" : ""}`}
          onClick={handleClick}
          style={{ paddingLeft: `${isDir ? 0 : 6}px` }}
        >
          {isDir && (
            isExpanded ? <ChevronDown size={13} /> : <ChevronRight size={13} />
          )}
          {isDir ? (
            isExpanded ? 
              <FolderOpen size={15} style={{ color: "var(--accent)" }} /> : 
              <Folder size={15} style={{ color: "var(--gray)" }} />
          ) : (
            getFileIcon(node.name)
          )}
          <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {node.name}
          </span>
        </div>
        
        {isDir && isExpanded && node.children && (
          <div style={{ borderLeft: "1px solid var(--border-color)", marginLeft: "8px", paddingLeft: "4px" }}>
            {node.children.map(child => renderTreeNode(child))}
          </div>
        )}
      </div>
    );
  };

  return (
    <aside 
      className={`sidebar ${isCollapsed ? "collapsed" : ""}`} 
      style={isCollapsed ? { width: 0, minWidth: 0 } : null}
    >
      {/* Indexer Panel */}
      <div className="index-section">
        <div className="section-title">Index New Repository</div>
        <div className="glass-card">
          <form onSubmit={handleIndex}>
            <div className="input-group">
              <input
                type="text"
                placeholder="Local path or Git HTTPS URL"
                className="input-field"
                value={pathOrUrl}
                onChange={(e) => setPathOrUrl(e.target.value)}
                disabled={isIndexing}
              />
              <input
                type="text"
                placeholder="Repo Name (optional)"
                className="input-field"
                value={customName}
                onChange={(e) => setCustomName(e.target.value)}
                disabled={isIndexing}
              />
            </div>
            <button 
              type="submit" 
              className="btn-primary" 
              style={{ width: "100%" }}
              disabled={isIndexing || !pathOrUrl.trim()}
            >
              {isIndexing ? (
                <>
                  <Loader2 size={15} className="animate-spin" />
                  Indexing...
                </>
              ) : (
                <>
                  <Plus size={15} />
                  Index Codebase
                </>
              )}
            </button>
          </form>
        </div>

        {isIndexing && (
          <div className="indexing-status-indicator">
            <div className="loader-spinner"></div>
            <span>
              {indexingStatus}
            </span>
          </div>
        )}
      </div>

      {/* Repository Selector */}
      <div className="repo-selector-section">
        <div className="section-title">Active Database</div>
        <div className="repo-dropdown-container">
          <select
            className="repo-select"
            value={selectedRepo}
            onChange={(e) => setSelectedRepo(e.target.value)}
            disabled={isIndexing}
          >
            {repos.length === 0 ? (
              <option value="">No indexed repos</option>
            ) : (
              repos.map(r => (
                <option key={r} value={r}>{r}</option>
              ))
            )}
          </select>
          <button
            onClick={handleDelete}
            className="btn-delete"
            title="Delete this repository index"
            disabled={isIndexing || !selectedRepo}
          >
            <Trash2 size={15} />
          </button>
        </div>
      </div>

      {/* File Tree Viewer */}
      <div className="file-tree-section">
        <div className="section-title" style={{ marginBottom: "10px" }}>
          <GitBranch size={13} />
          Files
        </div>
        {fileTree ? (
          <div style={{ overflowX: "hidden" }}>
            {renderTreeNode(fileTree)}
          </div>
        ) : (
          <div style={{ color: "var(--text-muted)", fontSize: "0.8rem", textAlign: "center", marginTop: "20px" }}>
            {selectedRepo ? "No files indexed or loading..." : "Select a codebase to browse files"}
          </div>
        )}
      </div>
    </aside>
  );
}
