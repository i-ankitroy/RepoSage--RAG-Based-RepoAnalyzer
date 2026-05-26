import React, { useState, useRef, useEffect } from "react";
import { Send, Terminal, Loader2, Cpu } from "lucide-react";
import { api } from "../api/client";

export default function ChatPanel({ selectedRepo, onCitationClick, setCitations }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [responseModel, setResponseModel] = useState("");
  const messagesEndRef = useRef(null);

  useEffect(() => {
    // Clear chat when repo changes
    setMessages([]);
    setResponseModel("");
  }, [selectedRepo]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
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
    setIsLoading(true);

    try {
      const result = await api.queryRepo(selectedRepo, userMessage.text);
      
      const botMessage = {
        sender: "assistant",
        text: result.answer,
        citations: result.citations || [],
        latency: result.latency_ms
      };
      
      setResponseModel(result.model);
      setMessages(prev => [...prev, botMessage]);
      setCitations(result.citations || []);
    } catch (error) {
      const errorMessage = {
        sender: "assistant",
        text: `Error: ${error.message}. Please check if the backend server is running.`,
        citations: []
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  // Simple, custom Markdown + Citation formatter
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

      // 2. Parse inline code `code` and bold **bold**
      let inlineParts = [part];

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
            return <code key={`${idx}-${sIdx}`}>{sub.slice(1, -1)}</code>;
          }
          return sub;
        });
      });

      // 3. Format citations: [filename:L12-34] or [filename:L12]
      // Regex detects: [name.py:L12-34] or [name.js:12-34] or [path/name.rs:12]
      inlineParts = inlineParts.flatMap((item, idx) => {
        if (typeof item !== "string") return item;
        
        const citationRegex = /\[([a-zA-Z0-9_\-.\/]+):L?(\d+)(?:-L?(\d+))?\]/g;
        const result = [];
        let lastIndex = 0;
        let match;

        while ((match = citationRegex.exec(item)) !== null) {
          // Push text before match
          if (match.index > lastIndex) {
            result.push(item.substring(lastIndex, match.index));
          }

          const fullMatch = match[0];
          const fileName = match[1];
          const startLine = parseInt(match[2], 10);
          const endLine = match[3] ? parseInt(match[3], 10) : startLine;

          result.push(
            <button
              key={match.index}
              className="citation-link"
              onClick={() => onCitationClick({ file: fileName, start_line: startLine, end_line: endLine })}
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

      return <span key={index}>{inlineParts}</span>;
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
        <div className="chat-title">
          {selectedRepo ? `Chat — ${selectedRepo}` : "Chat"}
        </div>
        {responseModel && (
          <div className="chat-model-info">
            <Cpu size={12} style={{ marginRight: "4px", verticalAlign: "middle" }} />
            {responseModel}
          </div>
        )}
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
          messages.map((msg, idx) => (
            <div key={idx} className={`message ${msg.sender}`}>
              <div className="avatar">
                {msg.sender === "user" ? "U" : "RS"}
              </div>
              <div className="bubble">
                <div style={{ whiteSpace: "pre-wrap" }}>
                  {formatMessageText(msg.text)}
                </div>
                {msg.latency && (
                  <div style={{ fontSize: "0.65rem", color: "var(--text-muted)", marginTop: "8px", textAlign: "right" }}>
                    Latency: {(msg.latency / 1000).toFixed(2)}s
                  </div>
                )}
              </div>
            </div>
          ))
        )}
        
        {isLoading && (
          <div className="message assistant">
            <div className="avatar">RS</div>
            <div className="bubble" style={{ padding: "12px 20px" }}>
              <div className="loader-container">
                <Loader2 size={16} className="animate-spin" />
                Searching codebase and formulating response...
              </div>
            </div>
          </div>
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
    </div>
  );
}
