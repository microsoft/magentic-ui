import React, { useEffect, useLayoutEffect, useRef } from "react";

interface AutoResizeTextareaProps
  extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  value: string;
  onChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => void;
  className: string;
  minHeight?: string;
  maxHeight?: string;
}

const AutoResizeTextarea: React.FC<AutoResizeTextareaProps> = ({
  value,
  onChange,
  className,
  minHeight = "30px",
  maxHeight = "120px",
  ...props
}) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const observerRef = useRef<ResizeObserver | null>(null);

  const adjustHeight = () => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    // Reset height to get the correct scrollHeight measurement
    textarea.style.height = minHeight;

    // Convert min and max heights to numbers for comparison
    const minHeightPx = parseInt(minHeight);
    const maxHeightPx = parseInt(maxHeight);

    // Set the height to match content, bounded by min and max heights
    const desiredHeight = Math.min(
      Math.max(minHeightPx, textarea.scrollHeight),
      maxHeightPx
    );
    textarea.style.height = `${desiredHeight}px`;

    // Add scrollbar if content exceeds maxHeight
    textarea.style.overflowY =
      textarea.scrollHeight > maxHeightPx ? "auto" : "hidden";
  };

  // Initial height adjustment using useLayoutEffect to prevent flash
  useLayoutEffect(() => {
    adjustHeight();
  }, []);

  // Adjust height when value changes
  useEffect(() => {
    adjustHeight();
  }, [value]);

  // Setup resize observer and window resize handler
  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    // Create resize observer
    observerRef.current = new ResizeObserver(() => {
      adjustHeight();
    });

    // Observe both the textarea and its parent element
    observerRef.current.observe(textarea);
    if (textarea.parentElement) {
      observerRef.current.observe(textarea.parentElement);
    }

    // Handle window resize
    const handleResize = () => adjustHeight();
    window.addEventListener("resize", handleResize);

    // Setup intersection observer for visibility changes
    const intersectionObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            adjustHeight();
          }
        });
      },
      { threshold: 0.1 }
    );

    intersectionObserver.observe(textarea);

    return () => {
      window.removeEventListener("resize", handleResize);
      if (observerRef.current) {
        observerRef.current.disconnect();
      }
      intersectionObserver.disconnect();
    };
  }, []);

  return (
    <textarea
      ref={textareaRef}
      value={value}
      onChange={onChange}
      className={className}
      style={{
        minHeight,
        maxHeight,
        overflowY: "auto",
        resize: "none",
        ...props.style,
      }}
      {...props}
    />
  );
};

export default AutoResizeTextarea;
