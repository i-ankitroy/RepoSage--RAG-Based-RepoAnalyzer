import React, { useState, useEffect, useRef } from "react";
import { 
  Code, List, FileCode, CheckCircle, Loader2, 
  Maximize2, Minimize2, WrapText, ChevronRight
} from "lucide-react";
import { api } from "../api/client";

export default function CitationsPanel({ 
  selectedRepo, 
  activeFile, 
  activeLineRange, 
  citations,
  onCitationClick,
  onCollapse,
  isCollapsed,
  width,
  isMaximized,
  setIsMaximized
}) {
  const [activeTab, setActiveTab] = useState("viewer"); // "viewer" | "citations"
  const [fileContent, setFileContent] = useState("");
  const [language, setLanguage] = useState("plaintext");
  const [isLoadingFile, setIsLoadingFile] = useState(false);
  const [fileError, setFileError] = useState("");
  
  // Toggles for expandable layout and word wrap
  const [wordWrap, setWordWrap] = useState(false);
  
  const containerRef = useRef(null);

  // Fetch file content whenever selectedRepo or activeFile changes
  useEffect(() => {
    if (activeFile && selectedRepo) {
      loadFileContent(selectedRepo, activeFile);
      setActiveTab("viewer"); // Switch to viewer tab when a file is clicked
    } else {
      setFileContent("");
      setLanguage("plaintext");
    }
  }, [activeFile, selectedRepo]);

  // Scroll to cited line when activeLineRange changes or file content finishes loading
  useEffect(() => {
    if (activeLineRange && activeLineRange.start && fileContent) {
      setTimeout(() => {
        const lineElement = document.getElementById(`line-${activeLineRange.start}`);
        if (lineElement) {
          lineElement.scrollIntoView({ 
            behavior: "smooth", 
            block: "center",
            inline: "nearest"
          });
        }
      }, 150);
    }
  }, [activeLineRange, fileContent]);

  const loadFileContent = async (repo, path) => {
    setIsLoadingFile(true);
    setFileError("");
    try {
      const data = await api.getFileContent(repo, path);
      setFileContent(data.content);
      setLanguage(data.language);
    } catch (error) {
      console.error("Failed to load file content:", error);
      setFileError(`Failed to load file content: ${error.message}`);
      setFileContent("");
    } finally {
      setIsLoadingFile(false);
    }
  };

  const isLineHighlighted = (lineNum) => {
    if (!activeLineRange) return false;
    return lineNum >= activeLineRange.start && lineNum <= activeLineRange.end;
  };

  const renderCodeViewer = () => {
    if (isLoadingFile) {
      return (
        <div className="citation-empty-state">
          <Loader2 size={28} className="animate-spin" style={{ color: "var(--accent)" }} />
          <p>Loading file content...</p>
        </div>
      );
    }

    if (fileError) {
      return (
        <div className="citation-empty-state">
          <p style={{ color: "var(--danger)" }}>{fileError}</p>
        </div>
      );
    }

    if (!activeFile) {
      return (
        <div className="citation-empty-state">
          <FileCode size={28} style={{ color: "var(--text-muted)" }} />
          <p>Select a file in the sidebar or click a citation in the chat to view code.</p>
        </div>
      );
    }

    const lines = fileContent.split("\n");

    return (
      <div className="code-viewer-container">
        {/* Code Viewer Sub-header with Word Wrap Option */}
        <div className="code-viewer-header">
          <span 
            className="code-viewer-file-path" 
            title={activeFile}
            style={{ maxWidth: "70%", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
          >
            {activeFile}
          </span>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <button
              onClick={() => setWordWrap(!wordWrap)}
              className="btn-delete"
              style={{ 
                padding: "3px 6px", 
                fontSize: "0.72rem", 
                display: "flex", 
                alignItems: "center", 
                gap: "4px",
                borderColor: wordWrap ? "var(--accent)" : "var(--border-color)",
                color: wordWrap ? "var(--accent)" : "var(--text-muted)",
                backgroundColor: wordWrap ? "var(--accent-dim)" : "transparent"
              }}
              title="Toggle Word Wrap"
            >
              <WrapText size={12} />
              Wrap
            </button>
            <span className="code-viewer-lang">{language}</span>
          </div>
        </div>
        
        {/* Unified Layout supporting perfect Line Number alignment during word wrap */}
        <div className="code-editor-layout unified-layout" ref={containerRef}>
          <div className={`code-container-lines ${wordWrap ? "wrap-lines" : ""}`}>
            {lines.map((line, idx) => {
              const lineNum = idx + 1;
              const highlighted = isLineHighlighted(lineNum);
              return (
                <div 
                  id={`line-${lineNum}`}
                  key={lineNum} 
                  className={`code-line-row ${highlighted ? "highlighted" : ""}`}
                >
                  <div className={`line-number-cell ${highlighted ? "highlighted" : ""}`}>
                    {lineNum}
                  </div>
                  <div className="code-line-content">
                    {line || " "}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    );
  };

  return (
    <aside 
      className={`citations-panel ${isCollapsed ? "collapsed" : ""} ${isMaximized ? "maximized" : ""}`} 
      style={{ 
        width: isCollapsed ? 0 : (isMaximized ? "55vw" : width), 
        minWidth: isCollapsed ? 0 : (isMaximized ? "55vw" : width) 
      }}
    >
      {/* Tab Selectors */}
      <div className="citations-header" style={{ justifyContent: "center" }}>
        <div className="citations-tabs">
          <button
            className={`citation-tab ${activeTab === "viewer" ? "active" : ""}`}
            onClick={() => setActiveTab("viewer")}
          >
            <Code size={13} />
            Code
          </button>
          <button
            className={`citation-tab ${activeTab === "citations" ? "active" : ""}`}
            onClick={() => setActiveTab("citations")}
          >
            <List size={13} />
            Refs ({citations.length})
          </button>
        </div>
      </div>

      {/* Main Tab Content */}
      <div className="citations-content">
        {activeTab === "viewer" ? (
          renderCodeViewer()
        ) : (
          /* Citations List Tab */
          <div className="citation-cards-list">
            {citations.length === 0 ? (
              <div className="citation-empty-state" style={{ marginTop: "40px" }}>
                <CheckCircle size={28} style={{ color: "var(--text-muted)" }} />
                <p>No citation references available yet. Ask a question to load references.</p>
              </div>
            ) : (
              citations.map((cit, idx) => (
                <div 
                  key={idx} 
                  className="citation-card"
                  onClick={() => onCitationClick({ file: cit.file, start_line: cit.start_line, end_line: cit.end_line })}
                >
                  <div className="citation-card-header">
                    <div className="citation-card-file" title={cit.file}>
                      {cit.file.split("/").pop()}
                    </div>
                    <div className="citation-card-score">
                      {cit.score ? `${(cit.score * 100).toFixed(0)}% Match` : "Cited"}
                    </div>
                  </div>
                  <div className="citation-card-lines">
                    Line {cit.start_line === cit.end_line ? cit.start_line : `${cit.start_line}-${cit.end_line}`}
                  </div>
                  {cit.snippet && (
                    <div className="citation-card-preview">
                      {cit.snippet}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </aside>
  );
}
