import React, { useState, useEffect, memo } from "react";
import {
  File,
  FileTextIcon,
  ImageIcon,
  FileIcon,
  Code,
  X,
  Download,
} from "lucide-react";
import MarkdownRenderer from "./markdownrender";
import { ClickableImage } from "../views/atoms";
import { AgentMessageConfig } from "../types/datamodel";
import { getServerUrl } from "../utils";

// Types
type FileType = "image" | "code" | "text" | "pdf";

interface FileInfo {
  path: string;
  name: string;
  extension: string;
  type: FileType | "unknown";
  short_path?: string;
}

interface FileModalProps {
  isOpen: boolean;
  onClose: () => void;
  file: FileInfo | null;
  content: string | null;
}

interface FileCardProps {
  file: FileInfo;
  onFileClick: (file: FileInfo) => void;
}

interface RenderFileProps {
  message: AgentMessageConfig;
}

// File type to icon mapping
const FILE_ICONS: Record<string, React.ElementType> = {
  image: ImageIcon,
  code: Code,
  text: FileTextIcon,
  pdf: FileIcon,
  unknown: File,
};

// Add a mapping of file extensions to file types
const FILE_EXTENSIONS_MAP: Record<string, FileType> = {
  // Images
  jpg: "image",
  jpeg: "image",
  png: "image",
  gif: "image",
  svg: "image",
  webp: "image",

  // Code
  js: "code",
  jsx: "code",
  ts: "code",
  tsx: "code",
  py: "code",
  java: "code",
  c: "code",
  cpp: "code",
  cs: "code",
  go: "code",
  rb: "code",
  php: "code",
  html: "code",
  css: "code",
  scss: "code",
  json: "code",
  xml: "code",
  yaml: "code",
  yml: "code",

  // Text
  txt: "text",
  md: "text",
  markdown: "text",
  csv: "text",
  log: "text",

  // PDF
  pdf: "pdf",
};

// Modal component for displaying file content
const FileModal: React.FC<FileModalProps> = ({
  isOpen,
  onClose,
  file,
  content,
}) => {
  const [isFullScreen, setIsFullScreen] = useState<boolean>(false);
  const modalRef = React.useRef<HTMLDivElement>(null);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [processedContent, setProcessedContent] = useState<string | null>(null);

  useEffect(() => {
    // Add escape key handler
    const handleEscKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    // Add the event listener when the modal is open
    if (isOpen) {
      document.addEventListener("keydown", handleEscKey);
    }

    // Clean up the event listener
    return () => {
      document.removeEventListener("keydown", handleEscKey);
    };
  }, [isOpen, onClose]);

  useEffect(() => {
    if (file) {
      const fileUrl =
        getServerUrl().replace("/api", "") +
        `/${file.short_path || file.path || file.name}`;
      setDownloadUrl(fileUrl);
    } else {
      setDownloadUrl(null);
    }
  }, [file, content]);

  // Process content in a non-blocking way
  useEffect(() => {
    if (!content || !file) {
      setProcessedContent(null);
      return;
    }

    setIsLoading(true);

    try {
      let finalContent = content;

      // Only process text/code files
      if (file.type === "text" || file.type === "code") {
        // For very large files, we truncate early to prevent processing overhead
        const maxLength = 5000; // 5000 characters
        if (content.length > maxLength) {
          // Only process the first chunk to avoid unnecessary string operations
          finalContent =
            content.slice(0, maxLength) +
            "\n\n... Content truncated. File is too large to display completely. Please download the file to view all content ...";
        }
      }

      setProcessedContent(finalContent);
    } catch (error) {
      console.error("Error processing file content:", error);
      setProcessedContent(
        "Error processing file content. The file may be too large to display."
      );
    } finally {
      setIsLoading(false);
    }
  }, [content, file]);

  if (!isOpen || !file) return null;

  const toggleFullScreen = (): void => {
    setIsFullScreen(!isFullScreen);
  };

  // Handle click outside the modal content
  const handleBackdropClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  const renderContent = (): React.ReactNode => {
    // Show loading state
    if (isLoading) {
      return (
        <div className="flex flex-col items-center justify-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
          <p className="mt-4 text-gray-600">Loading file content...</p>
        </div>
      );
    }

    // If file is an image, display the image
    if (file.type === "image") {
      return (
        <div className="flex flex-col items-center">
          <ClickableImage
            src={content || ""}
            alt={file.name}
            className="max-w-full max-h-[70vh] object-contain"
          />
        </div>
      );
    }

    // For text or code files, render content with markdown
    else if (file.type === "text" || file.type === "code") {
      return (
        <div className="flex flex-col">
          {isLoading ? (
            <div className="flex flex-col items-center justify-center h-64">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
              <p className="mt-4 text-gray-600">Processing large file...</p>
            </div>
          ) : processedContent === null ? (
            <div className="p-4 text-gray-500">No content available</div>
          ) : (
            <MarkdownRenderer
              content={processedContent}
              fileExtension={file.extension}
            />
          )}
        </div>
      );
    }

    // For PDF files, use an iframe with the direct URL
    else if (file.type === "pdf") {
      return (
        <div className="flex flex-col">
          <iframe
            src={content || ""}
            title={file.name}
            className="w-full h-[70vh]"
            frameBorder="0"
          />
        </div>
      );
    }

    // For unknown file types, show a message
    return (
      <div className="p-4 text-center">
        <p>Unable to preview this file type.</p>
        <p>Filename: {file.name}</p>
      </div>
    );
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50"
      onClick={handleBackdropClick}
    >
      <div
        ref={modalRef}
        className={`bg-white rounded-lg shadow-lg overflow-hidden ${
          isFullScreen ? "fixed inset-0" : "max-w-4xl w-full max-h-[85vh]"
        }`}
      >
        {/* Header */}
        <div className="flex justify-between items-center p-4 border-b">
          <h3 className="text-lg font-medium text-black">{file.name}</h3>
          <div className="flex gap-2">
            {/* Download button */}
            {downloadUrl && (
              <a
                href={downloadUrl}
                download={file.name}
                className="p-1 rounded-full hover:bg-gray-200 text-black flex items-center justify-center"
                title="Download file"
                onClick={(e) => e.stopPropagation()}
              >
                <Download size={18} />
              </a>
            )}
            {/* <button
              onClick={toggleFullScreen}
              className="p-1 rounded-full hover:bg-gray-200 text-black"
              title={isFullScreen ? "Exit fullscreen" : "Fullscreen"}
            >
              {isFullScreen ? <Minimize2 size={18} /> : <Maximize2 size={18} />}
            </button> */}
            <button
              onClick={onClose}
              className="p-1 rounded-full hover:bg-gray-200 text-black"
              title="Close"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Content */}
        <div
          className={`p-4 overflow-auto text-black ${
            isFullScreen ? "h-[calc(90vh-64px)]" : "max-h-[70vh]"
          }`}
        >
          {renderContent()}
        </div>
      </div>
    </div>
  );
};

// ImageThumbnail component to display image previews
const ImageThumbnail = memo<{ file: FileInfo }>(({ file }) => {
  const [thumbnailUrl, setThumbnailUrl] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [hasError, setHasError] = useState<boolean>(false);

  useEffect(() => {
    const loadThumbnail = async () => {
      try {
        setIsLoading(true);
        const fileUrl =
          getServerUrl().replace("/api", "") +
          `/${file.short_path || file.path || file.name}`;

        setThumbnailUrl(fileUrl);
        setIsLoading(false);
      } catch (error) {
        console.error("Failed to load thumbnail:", error);
        setHasError(true);
        setIsLoading(false);
      }
    };

    if (file.type === "image") {
      loadThumbnail();
    }
  }, [file]);

  if (isLoading) {
    return (
      <div className="w-full h-20 flex items-center justify-center bg-gray-50">
        <div className="animate-pulse bg-gray-200 w-8 h-8 rounded"></div>
      </div>
    );
  }

  if (hasError) {
    return (
      <div className="w-full h-20 flex items-center justify-center bg-gray-50">
        <ImageIcon className="w-8 h-8 text-blue-500" />
      </div>
    );
  }

  return (
    <div className="w-full h-20 bg-gray-50 flex items-center justify-center overflow-hidden">
      <img
        src={thumbnailUrl}
        alt={file.name}
        className="w-full h-full object-contain"
        onError={() => setHasError(true)}
      />
    </div>
  );
});

ImageThumbnail.displayName = "ImageThumbnail";

// Add this new component for the download button
const DownloadButton = memo<{ file: FileInfo }>(({ file }) => {
  const handleDownload = (e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent opening the modal

    const fileUrl =
      getServerUrl().replace("/api", "") +
      `/${file.short_path || file.path || file.name}`;

    // Create a temporary anchor element
    const link = document.createElement("a");
    link.href = fileUrl;
    link.download = file.name; // Set the download filename
    link.target = "_blank"; // Open in new tab to prevent page navigation
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <button
      onClick={handleDownload}
      className="absolute top-2 right-2 p-1.5 rounded-full bg-white/90 hover:bg-white shadow-md opacity-0 group-hover:opacity-100 transition-opacity duration-200"
      title="Download file"
    >
      <Download size={16} className="text-gray-700" />
    </button>
  );
});

DownloadButton.displayName = "DownloadButton";

// Update the FileCard component
const FileCard = memo<FileCardProps>(({ file, onFileClick }) => {
  const IconComponent = FILE_ICONS[file.type] || FILE_ICONS.unknown;

  if (file.type === "image") {
    return (
      <div
        className="group relative flex flex-col overflow-hidden rounded-lg border border-gray-200 hover:border-blue-500 shadow-sm hover:shadow-md cursor-pointer transition-all"
        onClick={() => onFileClick(file)}
      >
        <ImageThumbnail file={file} />
        <div className="p-2 bg-white border-t w-full">
          <span className="text-xs truncate w-full block" title={file.name}>
            {file.name}
          </span>
        </div>
        <DownloadButton file={file} />
      </div>
    );
  }

  return (
    <div
      className="group relative flex flex-col items-center p-3 rounded-lg border border-gray-200 hover:border-blue-500 cursor-pointer transition-colors shadow-sm hover:shadow-md"
      onClick={() => onFileClick(file)}
    >
      <IconComponent className="w-8 h-8 mb-2 text-blue-500" />
      <span className="text-xs text-center truncate w-full" title={file.name}>
        {file.name}
      </span>
      <DownloadButton file={file} />
    </div>
  );
});

FileCard.displayName = "FileCard";

// Main RenderFile component
const RenderFile: React.FC<RenderFileProps> = ({ message }) => {
  const [files, setFiles] = useState<FileInfo[]>([]);
  const [selectedFile, setSelectedFile] = useState<FileInfo | null>(null);
  const [fileContent, setFileContent] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);

  useEffect(() => {
    // Extract file information from the message metadata
    if (message?.metadata?.type === "file" && message?.metadata?.files) {
      try {
        const parsedFiles = JSON.parse(message.metadata.files);

        // Process files to ensure correct type detection
        const processedFiles = Array.isArray(parsedFiles)
          ? parsedFiles.map((file) => {
              // If the file already has a valid type, keep it
              if (["image", "code", "text", "pdf"].includes(file.type)) {
                return file;
              }

              // Otherwise, try to determine type from extension
              const extension = file.extension?.toLowerCase() || "";
              const detectedType = FILE_EXTENSIONS_MAP[extension] || "unknown";

              return {
                ...file,
                type: detectedType,
              };
            })
          : [];

        setFiles(processedFiles);
      } catch (error) {
        console.error("Failed to parse files:", error);
        setFiles([]);
      }
    }
  }, [message]);

  const handleFileClick = (file: FileInfo): void => {
    setSelectedFile(file);
    setIsModalOpen(true);
    setFileContent(null); // Reset content before loading new file

    // Construct the proper URL path for web access
    const fileUrl =
      getServerUrl().replace("/api", "") +
      `/${file.short_path || file.path || file.name}`;

    // For images and PDFs, just use the URL directly
    if (file.type === "image" || file.type === "pdf") {
      setFileContent(fileUrl);
      return;
    }

    // For text/code files, fetch asynchronously without blocking
    if (file.type === "text" || file.type === "code") {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 2000); // 2 second timeout

      fetch(fileUrl, { signal: controller.signal })
        .then((response) => {
          if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
          }
          return response.text();
        })
        .then((text) => {
          setFileContent(text);
        })
        .catch((error) => {
          if (error.name === "AbortError") {
            console.error("Request timed out");
            setFileContent(
              "Error: Request timed out. The file may be too large or the server is not responding."
            );
          } else {
            console.error("Failed to load file content:", error);
            setFileContent(`Error loading file: ${error.message}`);
          }
        })
        .finally(() => {
          clearTimeout(timeoutId);
        });
    } else {
      // For other file types, use the URL
      setFileContent(fileUrl);
    }
  };

  const closeModal = (): void => {
    setIsModalOpen(false);
    setSelectedFile(null);
    setFileContent(null);
  };

  // If no files or not a file message, return null
  if (!files.length || message?.metadata?.type !== "file") {
    return null;
  }

  return (
    <div className="mt-4">
      <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-6 gap-2">
        {files.map((file, index) => (
          <FileCard key={index} file={file} onFileClick={handleFileClick} />
        ))}
      </div>

      <FileModal
        isOpen={isModalOpen}
        onClose={closeModal}
        file={selectedFile}
        content={fileContent}
      />
    </div>
  );
};

// Add window.fs typings
declare global {
  interface Window {
    fs: {
      readFile: (path: string) => Promise<ArrayBuffer>;
    };
  }
}

export default RenderFile;
