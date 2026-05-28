import React from "react";
import { Sparkles, Cpu, ChevronLeft, ChevronRight, Menu, LayoutPanelLeft } from "lucide-react";

export default function Navbar({
  leftCollapsed,
  setLeftCollapsed,
  rightCollapsed,
  setRightCollapsed,
  activeProvider,
  setActiveProvider,
  responseModel
}) {
  return (
    <nav className="navbar">
      {/* Left Area: Logo and Sidebar Toggle */}
      <div className="navbar-left">
        <button 
          className="btn-icon" 
          onClick={() => setLeftCollapsed(!leftCollapsed)}
          title={leftCollapsed ? "Expand Sidebar" : "Collapse Sidebar"}
        >
          {leftCollapsed ? <Menu size={16} /> : <LayoutPanelLeft size={16} />}
        </button>
        
        <div className="logo">
          <div className="logo-icon">
            <Sparkles size={16} style={{ color: "#1a1810" }} />
          </div>
          <span>RepoSage</span>
        </div>
      </div>

      {/* Center Area: Empty (repo badge moved back to Chat) */}
      <div className="navbar-center">
      </div>

      {/* Right Area: Model Selector and Citations Toggle */}
      <div className="navbar-right">
        {responseModel && (
          <div className="chat-model-info">
            <Cpu size={11} />
            {responseModel}
          </div>
        )}
        
        <select
          value={activeProvider}
          onChange={(e) => setActiveProvider(e.target.value)}
          className="model-select"
          title="Switch LLM Model Provider"
        >
          <option value="default">Default Cloud</option>
          <option value="nvidia">NVIDIA (gpt-oss-120b)</option>
          <option value="groq">Groq (Llama 3.1)</option>
          <option value="ollama">Local Ollama</option>
        </select>
        
        <button 
          className="btn-icon" 
          onClick={() => setRightCollapsed(!rightCollapsed)}
          title={rightCollapsed ? "Show Sources" : "Hide Sources"}
        >
          {rightCollapsed ? <ChevronLeft size={16} /> : <ChevronRight size={16} />}
        </button>
      </div>
    </nav>
  );
}
