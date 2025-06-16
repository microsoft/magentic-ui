import React, { useEffect, useState } from "react";
import ReactDOM from "react-dom";
import { X } from "lucide-react";
import BrowserIframe from "./browser_iframe";
import { Button } from "antd";
interface BrowserModalProps {
  isOpen: boolean;
  onClose: () => void;
  novncPort?: string;
  title?: string;
  onPause?: () => void;
  runStatus?: string;
  onControlHandover?: () => void;
  isControlMode?: boolean;
  onTakeControl?: () => void;
}

const BrowserModal: React.FC<BrowserModalProps> = (props) => {
  const {
    isOpen,
    onClose,
    novncPort,
    title = "Browser View",
    onPause,
    runStatus,
    onControlHandover,
    isControlMode = false,
    onTakeControl,
  } = props;
  const [modalRoot, setModalRoot] = useState<HTMLElement | null>(null);
  const modalIframeId = "modal-browser-iframe";

  useEffect(() => {
    // Look for existing modal root
    let root = document.getElementById("modal-root");

    // Create it if it doesn't exist
    if (!root) {
      root = document.createElement("div");
      root.id = "modal-root";
      document.body.appendChild(root);
    }

    setModalRoot(root);

    // Clean up function
    return () => {
      if (
        root &&
        root.parentNode &&
        !document.getElementById("modal-root")?.childElementCount
      ) {
        root.parentNode.removeChild(root);
      }
    };
  }, []);

  // Handle giving back control
  const handleGiveBackControl = () => {
    // Close the modal first
    onClose();

    // Then trigger the control handover in parent component (DetailViewer)
    if (onControlHandover) {
      onControlHandover();
    }
  };

  // Don't render until we have a modal root
  if (!isOpen || !modalRoot) return null;

  const modalContent = (
    <>
      <div
        className="fixed inset-0 flex items-center justify-center bg-black bg-opacity-75"
        style={{ zIndex: 100 }}
      >
        <div className="bg-tertiary rounded-lg shadow-xl w-[95vw] h-[95vh] flex flex-col">
          {/* Header - Modified to use grid approach */}
          <div className="grid grid-cols-3 items-center px-6 py-3 border-b border-primary/20">
            {/* Left column */}
            <div className="flex items-center">
              <h2 className="text-lg font-semibold text-primary">{title}</h2>
            </div>

            {/* Center column */}
            <div className="flex justify-center">
              {isControlMode && (
                <Button
                  type="primary"
                  block
                  onClick={handleGiveBackControl}
                  className="font-medium shadow-md flex justify-center items-center"
                  size="large"
                >
                  Give control back to Magentic-UI 
                </Button>
              )}
            </div>

            {/* Right column */}
            <div className="flex justify-end">
              <button
                onClick={onClose}
                className="p-1 hover:bg-gray-100 rounded-full transition-colors"
              >
                <X size={20} />
              </button>
            </div>
          </div>

          {/* Content - Make sure this uses full height */}
          <div className="flex-grow p-2 h-full overflow-hidden">
            <div id={modalIframeId} className="h-full">
              <BrowserIframe
                novncPort={novncPort}
                className="h-full"
                showDimensions={true}
                onPause={onPause}
                runStatus={runStatus}
                quality={9}
                viewOnly={false}
                scaling="remote"
                showTakeControlOverlay={!isControlMode}
                onTakeControl={onTakeControl}
                isControlMode={isControlMode}
              />
            </div>
          </div>
        </div>
      </div>
    </>
  );

  return ReactDOM.createPortal(modalContent, modalRoot);
};

export default BrowserModal;
