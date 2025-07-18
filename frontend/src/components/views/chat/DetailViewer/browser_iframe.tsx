import React, { useState, useEffect } from "react";
import SecurityBanner from "./SecurityBanner";

interface BrowserIframeProps {
  novncPort?: string;
  style?: React.CSSProperties;
  className?: string;
  showDimensions?: boolean;
  onPause?: () => void;
  runStatus?: string;
  quality?: number; // 0-9
  viewOnly?: boolean;
  scaling?: "local" | "remote" | "none";
  showTakeControlOverlay?: boolean;
  onTakeControl?: () => void;
  isControlMode?: boolean;
  serverUrl?: string;
}

const BrowserIframe: React.FC<BrowserIframeProps> = ({
  novncPort,
  style = {},
  className = "",
  showDimensions = true,
  onPause,
  runStatus,
  quality = 9,
  viewOnly = false,
  scaling = "local",
  showTakeControlOverlay = true,
  onTakeControl,
  isControlMode = false,
  serverUrl,
}) => {

  // Get the hostname of the current access address
  const currentHostname = window.location.hostname;

  // If serverUrl is not provided, use the current hostname
  const finalServerUrl = serverUrl || currentHostname;

  const [iframeDimensions, setIframeDimensions] = useState({
    width: 0,
    height: 0,
  });
  const [isHovering, setIsHovering] = useState(false);

  // Reset hover state when status changes back to active
  useEffect(() => {
    if (runStatus === "active") {
      setIsHovering(false);
    }
  }, [runStatus]);

  const handleOverlayClick = () => {
    if (runStatus === "active") {
      // Call both onPause and onTakeControl
      if (onPause) {
        onPause();
      }

      // Signal that take control was clicked
      if (onTakeControl) {
        onTakeControl();
      }
    }
  };

  if (!novncPort) {
    return (
      <div className="flex items-center justify-center h-full">
        <p>Waiting for browser session to start...</p>
      </div>
    );
  }

  // Build VNC URL with parameters
  const vncUrl = `http://${finalServerUrl}:${novncPort}/vnc.html?autoconnect=true&resize=${
    scaling === "remote" ? "remote" : "scale"
  }&show_dot=true&scaling=${scaling}&quality=${quality}&compression=0&view_only=${
    viewOnly ? 1 : 0
  }`;

  return (
    <div
      className={`relative w-full h-full ${className}`}
      onMouseEnter={() => setIsHovering(true)}
      onMouseLeave={() => setIsHovering(false)}
    >
      {isControlMode && (
        <SecurityBanner className="sticky top-0 left-0 right-0" />
      )}

      {showDimensions && (
        <div className="absolute top-2 right-2 bg-black bg-opacity-50 text-white px-2 py-1 rounded text-sm z-10">
          {iframeDimensions.width} × {iframeDimensions.height}
        </div>
      )}

      <iframe
        src={vncUrl}
        style={{
          width: "100%",
          height: "100%",
          border: "none",
          ...style,
        }}
        title="Browser View"
        className="rounded"
        onLoad={(e) => {
          const iframe = e.target as HTMLIFrameElement;
          setIframeDimensions({
            width: iframe.offsetWidth,
            height: iframe.offsetHeight,
          });
        }}
      />

      {/* Take Control overlay - only show when not in control mode */}
      {showTakeControlOverlay &&
        isHovering &&
        runStatus === "active" &&
        !isControlMode && (
          <div
            className="absolute inset-0 bg-black bg-opacity-50 flex items-center justify-center cursor-pointer transition-opacity duration-300 ease-in-out"
            onClick={handleOverlayClick}
          >
            <div className="text-white text-xl font-semibold">Take Control</div>
          </div>
        )}
    </div>
  );
};

export default BrowserIframe;
