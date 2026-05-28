import React, { useState, useRef, useEffect } from "react";
import { Send, Terminal, Loader2, Cpu } from "lucide-react";
import { api } from "../api/client";

export default function ChatPanel({ selectedRepo, onCitationClick, setCitations }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [responseModel, setResponseModel] = useState("");
  const [showFailoverModal, setShowFailoverModal] = useState(false);
  const [pendingQuestion, setPendingQuestion] = useState("");
  const [activeProvider, setActiveProvider] = useState("default"); // "default", "groq", "ollama"
  const [flatFiles, setFlatFiles] = useState([]);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    // Clear chat and reset provider/files when repo changes
    setMessages([]);
    setResponseModel("");
    if (selectedRepo) {
      fetchFlatFiles(selectedRepo);
    } else {
      setFlatFiles([]);
    }
  }, [selectedRepo]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const fetchFlatFiles = async (repoName) => {
    try {
      const tree = await api.getRepoFiles(repoName);
      const flattened = [];
      const flatten = (node) => {
        if (!node) return;
        if (node.type === "file") {
          flattened.push(node.path);
        } else if (node.children) {
          node.children.forEach(flatten);
        }
      };
      flatten(tree);
      setFlatFiles(flattened);
    } catch (error) {
      console.error("Failed to fetch flat files list:", error);
      setFlatFiles([]);
    }
  };

  const resolveFilePath = (fileName) => {
    if (!flatFiles || flatFiles.length === 0) return null;
    const cleanName = fileName.replace(/\\/g, "/").toLowerCase();
    
    // Try exact match
    const exactMatch = flatFiles.find(f => f.toLowerCase() === cleanName);
    if (exactMatch) return exactMatch;
    
    // Try suffix match (e.g. "groq_client.py" matches "backend/generator/groq_client.py")
    const suffixMatch = flatFiles.find(f => f.toLowerCase().endsWith("/" + cleanName));
    if (suffixMatch) return suffixMatch;
    
    return null;
  };

  const updateLastAssistantMessage = (updateFn) => {
    setMessages(prev => {
      if (prev.length === 0) return prev;
      const next = [...prev];
      const lastIndex = next.length - 1;
      if (next[lastIndex].sender === "assistant") {
        next[lastIndex] = updateFn(next[lastIndex]);
      }
      return next;
    });
  };

  const handleQueryError = (error, questionText, providerUsed) => {
    const isOllama = providerUsed === "ollama";
    if (!isOllama) {
      setPendingQuestion(questionText);
      setShowFailoverModal(true);
      
      // Remove the last assistant placeholder message
      setMessages(prev => {
        if (prev.length === 0) return prev;
        const next = [...prev];
        if (next[next.length - 1].sender === "assistant") {
          next.pop();
        }
        return next;
      });
    } else {
      updateLastAssistantMessage(msg => ({
        ...msg,
        text: `Error: ${error.message}. Please check if the local Ollama backend is running.`
      }));
    }
  };

  const runStreamQuery = async (questionText, providerToUse) => {
    setIsLoading(true);
    
    const botMessagePlaceholder = {
      sender: "assistant",
      text: "",
      citations: [],
      latency: null,
      model: ""
    };
    
    setMessages(prev => [...prev, botMessagePlaceholder]);
    
    let accumulatedText = "";
    let citationsSet = false;
    
    try {
      await api.queryRepoStream(
        selectedRepo,
        questionText,
        (chunk) => {
          if (chunk.type === "token") {
            accumulatedText += chunk.token;
            updateLastAssistantMessage(msg => ({
              ...msg,
              text: accumulatedText
            }));
          } else if (chunk.type === "citations") {
            updateLastAssistantMessage(msg => ({
              ...msg,
              citations: chunk.citations || []
            }));
            setCitations(chunk.citations || []);
            citationsSet = true;
          } else if (chunk.type === "model") {
            updateLastAssistantMessage(msg => ({
              ...msg,
              model: chunk.model
            }));
            setResponseModel(chunk.model);
          } else if (chunk.type === "latency") {
            updateLastAssistantMessage(msg => ({
              ...msg,
              latency: chunk.latency_ms
            }));
          } else if (chunk.type === "error") {
            throw new Error(chunk.error);
          }
        },
        (error) => {
          handleQueryError(error, questionText, providerToUse);
        },
        providerToUse === "default" ? null : providerToUse
      );
    } catch (err) {
      handleQueryError(err, questionText, providerToUse);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSend = async (e) => {
    e?.preventDefault();
    if (!input.trim() || !selectedRepo || isLoading) return;

    const userMessage = {
      sender: "user",
      text: input.trim()
    };

    setMessages(prev => [...prev, userMessage]);
    setInput("");
    
    await runStreamQuery(userMessage.text, activeProvider);
  };

  const handleConfirmFailover = async () => {
    setShowFailoverModal(false);
    setActiveProvider("ollama");
    const questionToRetry = pendingQuestion;
    setPendingQuestion("");
    await runStreamQuery(questionToRetry, "ollama");
  };

  const handleCancelFailover = () => {
    setShowFailoverModal(false);
    setPendingQuestion("");
    const cloudName = activeProvider === "default" ? "Cloud API" : activeProvider.toUpperCase();
    const errorMessage = {
      sender: "assistant",
      text: `Failed to connect to ${cloudName}. Query cancelled.`,
      citations: []
    };
    setMessages(prev => [...prev, errorMessage]);
  };

  // Helper to format inline markdown elements (bold, code, links, file references)
  const formatInlineElements = (content) => {
    let inlineParts = [content];

    // Format bold text
    inlineParts = inlineParts.flatMap((item, idx) => {
      if (typeof item !== "string") return item;
      const subParts = item.split(/(\*\*.*?\*\*)/g);
      return subParts.map((sub, sIdx) => {
        if (sub.startsWith("**") && sub.endsWith("**")) {
          return <strong key={`${idx}-${sIdx}`}>{sub.slice(2, -2)}</strong>;
        }
        return sub;
      });
    });

    // Format inline code
    inlineParts = inlineParts.flatMap((item, idx) => {
      if (typeof item !== "string") return item;
      const subParts = item.split(/(`.*?`)/g);
      return subParts.map((sub, sIdx) => {
        if (sub.startsWith("`") && sub.endsWith("`")) {
          const codeContent = sub.slice(1, -1);
          const trimmed = codeContent.trim();
          
          let parsedFile = trimmed;
          let startLine = null;
          let endLine = null;
          let isFileMatch = false;
          let resolvedPath = null;
          
          // Check for line suffix at the end (e.g. :10-20 or :10)
          const colonMatch = /:(\d+)(?:-(\d+))?$/.exec(trimmed);
          if (colonMatch) {
            parsedFile = trimmed.substring(0, colonMatch.index).trim();
            startLine = parseInt(colonMatch[1], 10);
            endLine = colonMatch[2] ? parseInt(colonMatch[2], 10) : startLine;
            resolvedPath = resolveFilePath(parsedFile);
            if (resolvedPath) isFileMatch = true;
          }
          
          // Check for word range suffix at the end (e.g. lines 10-20 or L10-20)
          if (!isFileMatch) {
            const wordMatch = /(?:\s*,\s*|\s+)(?:lines?|L)\s*(\d+)(?:\s*-\s*(\d+))?$/i.exec(trimmed);
            if (wordMatch) {
              parsedFile = trimmed.substring(0, wordMatch.index).trim();
              startLine = parseInt(wordMatch[1], 10);
              endLine = wordMatch[2] ? parseInt(wordMatch[2], 10) : startLine;
              resolvedPath = resolveFilePath(parsedFile);
              if (resolvedPath) isFileMatch = true;
            }
          }
          
          // If no suffix matched, check if the entire trimmed string resolves to a file path
          if (!isFileMatch) {
            resolvedPath = resolveFilePath(trimmed);
            if (resolvedPath) {
              isFileMatch = true;
            }
          }
          
          if (isFileMatch && resolvedPath) {
            return (
              <button
                key={`${idx}-${sIdx}`}
                className="citation-link code-citation"
                onClick={() => onCitationClick({ 
                  file: resolvedPath, 
                  start_line: startLine || 1, 
                  end_line: endLine || startLine || 1 
                })}
              >
                {codeContent}
              </button>
            );
          }
          
          return <code key={`${idx}-${sIdx}`}>{codeContent}</code>;
        }
        return sub;
      });
    });

    // 3.1 Format bracket citations: [filename:L12-34] or [filename:L12]
    inlineParts = inlineParts.flatMap((item, idx) => {
      if (typeof item !== "string") return item;
      
      const citationRegex = /\[([a-zA-Z0-9_\-.\/]+):L?(\d+)(?:-L?(\d+))?\]/g;
      const result = [];
      let lastIndex = 0;
      let match;

      while ((match = citationRegex.exec(item)) !== null) {
        if (match.index > lastIndex) {
          result.push(item.substring(lastIndex, match.index));
        }

        const fileName = match[1];
        const startLine = parseInt(match[2], 10);
        const endLine = match[3] ? parseInt(match[3], 10) : startLine;

        const resolvedPath = resolveFilePath(fileName) || fileName;

        result.push(
          <button
            key={match.index}
            className="citation-link"
            onClick={() => onCitationClick({ file: resolvedPath, start_line: startLine, end_line: endLine })}
          >
            {fileName}:{startLine}{endLine !== startLine ? `-${endLine}` : ""}
          </button>
        );

        lastIndex = citationRegex.lastIndex;
      }

      if (lastIndex < item.length) {
        result.push(item.substring(lastIndex));
      }

      return result;
    });

    // 3.2 Format plain file mentions with line/range specifiers
    inlineParts = inlineParts.flatMap((item, idx) => {
      if (typeof item !== "string") return item;

      const fileMentionRegex = /\b([a-zA-Z0-9_\-.\/]+\.(?:py|js|ts|jsx|tsx|go|rs|java|cpp|cc|h|md|json|yaml|yml|toml))\b(?:(?:\s*,\s*|\s+)(?:lines?|L)\s*(\d+)(?:\s*-\s*(\d+))?|:(\d+)(?:-(\d+))?)?/gi;
      const result = [];
      let lastIndex = 0;
      let match;

      fileMentionRegex.lastIndex = 0;

      while ((match = fileMentionRegex.exec(item)) !== null) {
        const rawFileName = match[1];
        const resolvedPath = resolveFilePath(rawFileName);

        if (resolvedPath) {
          if (match.index > lastIndex) {
            result.push(item.substring(lastIndex, match.index));
          }

          let startLine = null;
          let endLine = null;

          if (match[4]) {
            startLine = parseInt(match[4], 10);
            endLine = match[5] ? parseInt(match[5], 10) : startLine;
          } else if (match[2]) {
            startLine = parseInt(match[2], 10);
            endLine = match[3] ? parseInt(match[3], 10) : startLine;
          }

          const label = match[0];

          result.push(
            <button
              key={match.index}
              className="citation-link"
              onClick={() => onCitationClick({ 
                file: resolvedPath, 
                start_line: startLine || 1, 
                end_line: endLine || startLine || 1 
              })}
            >
              {label}
            </button>
          );

          lastIndex = fileMentionRegex.lastIndex;
        } else {
          if (match.index > lastIndex) {
            result.push(item.substring(lastIndex, match.index));
          }
          result.push(match[0]);
          lastIndex = fileMentionRegex.lastIndex;
        }
      }

      if (lastIndex < item.length) {
        result.push(item.substring(lastIndex));
      }

      return result;
    });

    return inlineParts;
  };

  // Advanced custom Markdown + Block element + Citation formatter
  const formatMessageText = (text) => {
    if (!text) return "";

    // 1. Process code blocks: ```code```
    const parts = text.split(/(```[\s\S]*?```)/g);
    
    return parts.map((part, index) => {
      if (part.startsWith("```") && part.endsWith("```")) {
        // Extract language and code
        const lines = part.slice(3, -3).trim().split("\n");
        let lang = "code";
        let codeLines = lines;
        if (lines[0] && !lines[0].includes(" ") && lines[0].length < 15) {
          lang = lines[0];
          codeLines = lines.slice(1);
        }
        return (
          <pre key={index}>
            <code className={`language-${lang}`}>
              {codeLines.join("\n")}
            </code>
          </pre>
        );
      }

      // 2. Format block level markers (headings, lists, line breaks)
      const lines = part.split("\n");
      return (
        <div key={index} className="text-block">
          {lines.map((line, lineIdx) => {
            const trimmed = line.trim();
            
            // 2.1 Handle horizontal rules (e.g. --- or ***)
            if (/^(?:---|\*\*\*|___)$/.test(trimmed)) {
              return <hr key={lineIdx} style={{ margin: "16px 0", borderColor: "var(--border-color)", borderStyle: "solid", borderWidth: "1px 0 0 0" }} />;
            }
            
            // 2.2 Handle headers (e.g. # Title, ## Title, ### Title)
            const headerMatch = line.match(/^(#{1,6})\s+(.*)$/);
            if (headerMatch) {
              const level = headerMatch[1].length;
              const content = headerMatch[2];
              const parsedContent = formatInlineElements(content);
              
              if (level === 1) return <h1 key={lineIdx} className="chat-h1">{parsedContent}</h1>;
              if (level === 2) return <h2 key={lineIdx} className="chat-h2">{parsedContent}</h2>;
              if (level === 3) return <h3 key={lineIdx} className="chat-h3">{parsedContent}</h3>;
              return <h4 key={lineIdx} className="chat-h4">{parsedContent}</h4>;
            }
            
            // 2.3 Handle list items starting with *, -, or +
            const listMatch = line.match(/^(\s*)([*+-])\s+(.*)$/);
            if (listMatch) {
              const indent = listMatch[1].length;
              const content = listMatch[3];
              const parsedContent = formatInlineElements(content);
              return (
                <div key={lineIdx} style={{ paddingLeft: `${indent + 16}px`, marginBottom: "6px", display: "flex", gap: "8px", alignItems: "flex-start" }}>
                  <span style={{ color: "var(--teal)", marginTop: "2px", fontSize: "1.1rem", lineHeight: "1" }}>•</span>
                  <span>{parsedContent}</span>
                </div>
              );
            }

            // 2.4 Handle numbered list items (e.g. 1. Item)
            const numListMatch = line.match(/^(\s*)(\d+)\.\s+(.*)$/);
            if (numListMatch) {
              const indent = numListMatch[1].length;
              const num = numListMatch[2];
              const content = numListMatch[3];
              const parsedContent = formatInlineElements(content);
              return (
                <div key={lineIdx} style={{ paddingLeft: `${indent + 16}px`, marginBottom: "6px", display: "flex", gap: "8px", alignItems: "flex-start" }}>
                  <span style={{ color: "var(--teal)", fontWeight: 600 }}>{num}.</span>
                  <span>{parsedContent}</span>
                </div>
              );
            }

            // 2.5 Empty lines
            if (trimmed === "") {
              return <div key={lineIdx} style={{ height: "6px" }} />;
            }

            // 2.6 Strip raw HTML tags from the lines for safety and neatness
            let cleanLine = line;
            cleanLine = cleanLine.replace(/<[^>]*>/g, "");

            // Ignore line if it was purely tags and is now empty
            if (cleanLine.trim() === "" && line.trim() !== "") {
              return null;
            }

            return (
              <p key={lineIdx} style={{ marginBottom: "6px", lineHeight: "1.5" }}>
                {formatInlineElements(cleanLine)}
              </p>
            );
          })}
        </div>
      );
    });
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="main-panel">
      {/* Header */}
      <div className="chat-header">
        <div className="chat-title" style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span>{selectedRepo ? `Chat — ${selectedRepo}` : "Chat"}</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <select
            value={activeProvider}
            onChange={(e) => {
              setActiveProvider(e.target.value);
              setResponseModel("");
            }}
            className="model-select"
            title="Switch LLM Model Provider"
          >
            <option value="default">Default Cloud</option>
            <option value="nvidia">NVIDIA (gpt-oss-120b)</option>
            <option value="groq">Groq (Llama 3.1)</option>
            <option value="ollama">Local Ollama</option>
          </select>
          
          {responseModel && (
            <div className="chat-model-info" style={{ margin: 0 }}>
              <Cpu size={12} style={{ marginRight: "4px", verticalAlign: "middle" }} />
              {responseModel}
            </div>
          )}
        </div>
      </div>

      {/* Messages */}
      <div className="chat-messages">
        {messages.length === 0 ? (
          <div className="chat-empty">
            <Terminal size={40} />
            <h3>Ask anything about {selectedRepo || "your codebase"}</h3>
            <p style={{ maxWidth: "340px", fontSize: "0.85rem" }}>
              {selectedRepo 
                ? "Enter your question in plain English below, and RepoSage will search and reference files in this codebase." 
                : "Please select or index a repository in the sidebar to get started."}
            </p>
          </div>
        ) : (
          messages.map((msg, idx) => {
            const isLast = idx === messages.length - 1;
            const showLoader = isLast && isLoading && msg.sender === "assistant" && msg.text === "";
            
            return (
              <div key={idx} className={`message ${msg.sender}`}>
                <div className="avatar">
                  {msg.sender === "user" ? "U" : "RS"}
                </div>
                <div className="bubble" style={showLoader ? { padding: "12px 20px" } : null}>
                  {showLoader ? (
                    <div className="loader-container" style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <Loader2 size={16} className="animate-spin" />
                      Retrieving chunks and starting response...
                    </div>
                  ) : (
                    <div style={{ whiteSpace: "pre-wrap" }}>
                      {formatMessageText(msg.text)}
                    </div>
                  )}
                  {msg.latency && (
                    <div style={{ fontSize: "0.65rem", color: "var(--text-muted)", marginTop: "8px", textAlign: "right" }}>
                      Latency: {(msg.latency / 1000).toFixed(2)}s
                    </div>
                  )}
                </div>
              </div>
            );
          })
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="chat-input-container">
        <form onSubmit={handleSend} className="chat-input-wrapper">
          <textarea
            className="chat-input"
            placeholder={selectedRepo ? "Ask a question about the code..." : "Select a codebase to ask questions"}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading || !selectedRepo}
          />
          <button
            type="submit"
            className="btn-send"
            disabled={isLoading || !selectedRepo || !input.trim()}
          >
            <Send size={16} />
          </button>
        </form>
      </div>

      {/* Neumorphic Failover Modal */}
      {showFailoverModal && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="modal-header">
              <div className="modal-icon-container">
                <Cpu size={24} />
              </div>
              <h3 className="modal-title">Switch to Local Ollama?</h3>
            </div>
            <div className="modal-body">
              Failed to connect to the Cloud LLM API. Would you like to switch to your local Ollama instance and retry your question?
            </div>
            <div className="modal-actions">
              <button className="modal-btn modal-btn-secondary" onClick={handleCancelFailover}>
                Cancel
              </button>
              <button className="modal-btn modal-btn-primary" onClick={handleConfirmFailover}>
                Yes, Switch & Retry
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
