import React, { useState } from "react";
import Navbar from "./components/Navbar";
import Sidebar from "./components/Sidebar";
import ChatPanel from "./components/ChatPanel";
import CitationsPanel from "./components/CitationsPanel";

function App() {
  const [selectedRepo, setSelectedRepo] = useState("");
  const [activeFile, setActiveFile] = useState("");
  const [activeLineRange, setActiveLineRange] = useState(null);
  const [citations, setCitations] = useState([]);

  // Resizing and collapsing state
  const [rightWidth, setRightWidth] = useState(420);
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const [isMaximized, setIsMaximized] = useState(false);

  // Global app state
  const [activeProvider, setActiveProvider] = useState("default");
  const [responseModel, setResponseModel] = useState("");

  const handleCitationClick = ({ file, start_line, end_line }) => {
    setActiveFile(file);
    setActiveLineRange({ start: start_line, end: end_line });
    // Expand right panel automatically when a citation is clicked
    if (rightCollapsed) {
      setRightCollapsed(false);
    }
  };

  const handleFileSelect = (filePath) => {
    setActiveFile(filePath);
    setActiveLineRange(null); // Clear highlight when clicking a file from sidebar
    // Expand right panel automatically when a file is selected
    if (rightCollapsed) {
      setRightCollapsed(false);
    }
  };

  // Drag-to-resize handler for right sidebar
  const startResizeRight = (e) => {
    e.preventDefault();
    document.body.classList.add("is-resizing");
    const handleMouseMove = (moveEvent) => {
      const newWidth = Math.max(300, Math.min(window.innerWidth * 0.65, window.innerWidth - moveEvent.clientX));
      setRightWidth(newWidth);
    };
    const handleMouseUp = () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
      document.body.style.cursor = "default";
      document.body.classList.remove("is-resizing");
    };
    document.body.style.cursor = "col-resize";
    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
  };

  return (
    <div className="app-container">
      {/* Ambient Background Orbs */}
      <div className="orb orb-1" />
      <div className="orb orb-2" />
      <div className="orb orb-3" />

      {/* Universal Topbar */}
      <Navbar 
        leftCollapsed={leftCollapsed}
        setLeftCollapsed={setLeftCollapsed}
        rightCollapsed={rightCollapsed}
        setRightCollapsed={setRightCollapsed}
        activeProvider={activeProvider}
        setActiveProvider={setActiveProvider}
        responseModel={responseModel}
      />

      {/* Main Content Area */}
      <div className="app-content-area">
        {/* 1. Left Sidebar: Indexer, Repos, File Tree */}
        <Sidebar 
          selectedRepo={selectedRepo} 
          setSelectedRepo={setSelectedRepo} 
          onFileSelect={handleFileSelect}
          activeFile={activeFile}
          isCollapsed={leftCollapsed}
        />

        {/* 2. Center Chat Panel: Message Thread & Question input */}
        <ChatPanel 
          selectedRepo={selectedRepo} 
          onCitationClick={handleCitationClick}
          setCitations={setCitations}
          activeProvider={activeProvider}
          setActiveProvider={setActiveProvider}
          setResponseModel={setResponseModel}
        />

        {/* Right Resize Divider handle */}
        <div 
          className={`resize-handle ${rightCollapsed || isMaximized ? "collapsed" : ""}`} 
          onMouseDown={rightCollapsed || isMaximized ? null : startResizeRight}
        />

        {/* 3. Right Citations Panel: Code Viewer & Chunks Reference */}
        <CitationsPanel 
          selectedRepo={selectedRepo} 
          activeFile={activeFile} 
          activeLineRange={activeLineRange}
          citations={citations}
          onCitationClick={handleCitationClick}
          isCollapsed={rightCollapsed}
          width={rightWidth}
          isMaximized={isMaximized}
          setIsMaximized={setIsMaximized}
        />
      </div>
    </div>
  );
}

export default App;
