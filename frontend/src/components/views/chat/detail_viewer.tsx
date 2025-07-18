import React, { useState, useRef, lazy, Suspense } from "react";
import {
  ChevronLeft,
  ChevronRight,
  Maximize2,
  MousePointerClick,
  X,
} from "lucide-react";
import { ClickableImage } from "../atoms";
import BrowserIframe from "./DetailViewer/browser_iframe";
import BrowserModal from "./DetailViewer/browser_modal";
import FullscreenOverlay from "./DetailViewer/fullscreen_overlay"; // Import our new component
import { IPlan } from "../../types/plan";
import { useSettingsStore } from "../../store";
import { RcFile } from "antd/es/upload";
// Define VNC component props type
interface VncScreenProps {
  url: string;
  scaleViewport?: boolean;
  background?: string;
  style?: React.CSSProperties;
  ref?: React.Ref<any>;
}
// Lazy load the VNC component
const VncScreen = lazy<React.ComponentType<VncScreenProps>>(() =>
  // @ts-ignore
  import("react-vnc").then((module) => ({ default: module.VncScreen }))
);

interface DetailViewerProps {
  images: string[];
  imageTitles: string[];
  onMinimize: () => void;
  onToggleExpand: () => void;
  isExpanded: boolean;
  currentIndex: number;
  onIndexChange: (index: number) => void;
  novncPort?: string;
  onPause?: () => void;
  runStatus?: string;
  activeTab?: TabType;
  onTabChange?: (tab: TabType) => void;
  detailViewerContainerId?: string;
  onInputResponse?: (
    response: string,
    files: RcFile[],
    accepted?: boolean,
    plan?: IPlan
  ) => void;
}

type TabType = "screenshots" | "live";

const DetailViewer: React.FC<DetailViewerProps> = ({
  images,
  imageTitles,
  onMinimize,
  currentIndex,
  onIndexChange,
  novncPort,
  onPause,
  runStatus,
  activeTab: controlledActiveTab,
  onTabChange,
  detailViewerContainerId,
  onInputResponse,
}) => {
  const [internalActiveTab, setInternalActiveTab] = useState<TabType>("live");
  const activeTab = controlledActiveTab ?? internalActiveTab;
  const [viewMode, setViewMode] = useState<"iframe" | "novnc">("iframe");
  const vncRef = useRef();

  const [isModalOpen, setIsModalOpen] = useState(false);

  // Add state for fullscreen control mode
  const [isControlMode, setIsControlMode] = useState(false);
  const browserIframeId = "browser-iframe-container";

  // State for tracking if control was handed back from modal
  const [showControlHandoverForm, setShowControlHandoverForm] = useState(false);

  const config = useSettingsStore((state) => state.config);

  // Handle take control action
  const handleTakeControl = () => {
    setIsControlMode(true);
  };

  // Exit control mode
  const exitControlMode = () => {
    setIsControlMode(false);
  };

  // Modal control handlers
  const handleModalControlHandover = () => {
    // Show the feedback form overlay in DetailViewer
    setIsControlMode(true);
    setShowControlHandoverForm(true);
  };

  // Add keyboard navigation
  React.useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "ArrowLeft") {
        handlePrevious();
      } else if (event.key === "ArrowRight") {
        handleNext();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [currentIndex]);

  const handlePrevious = () => {
    const newIndex = currentIndex > 0 ? currentIndex - 1 : images.length - 1;
    onIndexChange(newIndex);
  };

  const handleNext = () => {
    const newIndex = currentIndex < images.length - 1 ? currentIndex + 1 : 0;
    onIndexChange(newIndex);
  };

  const handleTabChange = (tab: TabType) => {
    if (onTabChange) {
      onTabChange(tab);
    } else {
      setInternalActiveTab(tab);
    }
  };

  const handleMaximizeClick = () => {
    setIsModalOpen(true);
  };

  const renderScreenshotsTab = () => (
    <>
      <div className="flex flex-col h-[65vh] w-full">
        {images.length === 0 ? (
          <div className="flex-1 w-full flex items-center justify-center">
            <p>No screenshots</p>
          </div>
        ) : (
          <>
            <div className="relative flex-1 flex items-center justify-center overflow-y-auto">
              <div className="w-full h-full flex flex-col items-center justify-center">
                {/* Pill navigation overlay */}
                <div className="absolute border top-4 left-1/2 transform -translate-x-1/2 z-10 bg-secondary rounded-full px-3 py-1 flex items-center justify-center gap-4 shadow-md">
                  <button
                    onClick={handlePrevious}
                    className="text-primary hover:text-opacity-80 transition-colors"
                  >
                    <ChevronLeft size={18} />
                  </button>

                  <p className="text-sm text-primary">
                    {currentIndex + 1} / {images.length}
                  </p>

                  <button
                    onClick={handleNext}
                    className="text-primary hover:text-opacity-80 transition-colors"
                  >
                    <ChevronRight size={18} />
                  </button>
                </div>

                <ClickableImage
                  src={images[currentIndex]}
                  alt={imageTitles[currentIndex]}
                  className="max-w-full max-h-full object-contain rounded"
                  expandedClassName="object-contain max-h-[80vh] max-w-[90vw] w-auto h-auto"
                />
              </div>
            </div>
          </>
        )}
      </div>
    </>
  );

  const renderLiveTab = React.useMemo(() => {
    if (!novncPort) {
      return (
        <div className="flex-1 w-full h-full min-h-0 flex items-center justify-center">
          <p>Waiting for browser session to start...</p>
        </div>
      );
    }

    // Use server_url from config if set, otherwise default to localhost
    const serverHost = config.server_url || "localhost";

    return (
      <div className="flex-1 w-full h-full flex flex-col">
        {viewMode === "iframe" ? (
          <BrowserIframe
            novncPort={novncPort}
            style={{
              height: "100%",
              flex: "1 1 auto",
            }}
            className="w-full flex-1"
            showDimensions={true}
            onPause={onPause}
            runStatus={runStatus}
            quality={7}
            viewOnly={false}
            scaling="local"
            showTakeControlOverlay={!isControlMode}
            onTakeControl={handleTakeControl}
            isControlMode={isControlMode}
            serverUrl={serverHost}
          />
        ) : (
          <div
            className="relative w-full h-full flex flex-col"
            onMouseEnter={() => {}} // Moved overlay to BrowserIframe
            onMouseLeave={() => {}} // Moved overlay to BrowserIframe
          >
            <Suspense fallback={<div>Loading VNC viewer...</div>}>
              <VncScreen
                url={`ws://${serverHost}:${novncPort}`}
                scaleViewport
                background="#000000"
                style={{
                  width: "100%",
                  height: "100%",
                  flex: "1 1 auto",
                  alignSelf: "flex-start",
                  display: "flex",
                  flexDirection: "column",
                }}
                ref={vncRef}
              />
            </Suspense>
          </div>
        )}
      </div>
    );
  }, [novncPort, viewMode, runStatus, onPause, isControlMode, config.server_url]);

  return (
    <>
      <div
        className="bg-tertiary rounded-lg shadow-lg p-4 h-full flex flex-col relative overflow-hidden"
        id={detailViewerContainerId}
      >
        {/* Tabs and Controls */}
        <div className="flex justify-between items-center mb-4 border-b flex-shrink-0">
          <div className="flex">
            <button
              className={`px-6 py-2 font-medium rounded-t-lg transition-colors ${
                activeTab === "screenshots"
                  ? "bg-secondary text-primary border-2 border-b-0 border-primary"
                  : "text-secondary hover:text-primary hover:bg-secondary/10"
              }`}
              onClick={() => handleTabChange("screenshots")}
            >
              Screenshots
            </button>
            <button
              className={`px-6 py-2 font-medium rounded-t-lg transition-colors ${
                activeTab === "live"
                  ? "bg-secondary text-primary border-2 border-b-0 border-primary"
                  : "text-secondary hover:text-primary hover:bg-secondary/10"
              }`}
              onClick={() => handleTabChange("live")}
            >
              Live View
            </button>
          </div>

          <div className="flex gap-2">
            {isControlMode && (
              <div className="flex items-center gap-2 px-2 rounded-2xl bg-magenta-800 text-white">
                <MousePointerClick size={16} />
                <span>You have control</span>
              </div>
            )}
            <button
              onClick={handleMaximizeClick}
              className="p-1 hover:bg-gray-100 rounded-full transition-colors"
              title="Open in full screen"
            >
              <Maximize2 size={20} />
            </button>
            {!isControlMode && (
              <button
                onClick={onMinimize}
                className="p-1 hover:bg-gray-100 rounded-full transition-colors"
              >
                <X size={20} />
              </button>
            )}
          </div>
        </div>

        <div className="flex-1 flex flex-col min-h-0">
          {activeTab === "screenshots" ? renderScreenshotsTab() : renderLiveTab}
        </div>
      </div>

      <BrowserModal
        isOpen={isModalOpen}
        onClose={() => {
          setIsModalOpen(false);
        }}
        novncPort={novncPort}
        title="Browser View"
        onPause={onPause}
        runStatus={runStatus}
        onControlHandover={handleModalControlHandover}
        isControlMode={isControlMode}
        onTakeControl={handleTakeControl}
      />

      {/* Fullscreen Control Mode Overlay */}
      <FullscreenOverlay
        isVisible={isControlMode}
        onClose={() => {
          exitControlMode();
          setShowControlHandoverForm(false);
        }}
        targetElementId={detailViewerContainerId}
        zIndex={50}
        onInputResponse={onInputResponse}
        runStatus={runStatus}
      />
    </>
  );
};

export default DetailViewer;
