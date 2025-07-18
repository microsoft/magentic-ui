import React, { useEffect, useState } from "react";
import FeedbackForm from "./FeedbackForm";
import { RcFile } from "antd/es/upload";
import { IPlan } from "../../../types/plan";

interface FullscreenOverlayProps {
  isVisible: boolean;
  onClose: () => void;
  targetElementId?: string; // ID of element to exclude from overlay
  children?: React.ReactNode;
  zIndex?: number;
  onInputResponse?: (
    response: string,
    files: RcFile[],
    accepted?: boolean,
    plan?: IPlan
  ) => void;
  runStatus?: string;
}

const FullscreenOverlay: React.FC<FullscreenOverlayProps> = ({
  isVisible,
  onClose,
  targetElementId,
  children,
  zIndex = 1000,
  onInputResponse,
  runStatus,
}) => {
  const [userFeedback, setUserFeedback] = useState("");

  // Lock body scroll and intercept all events
  useEffect(() => {
    if (isVisible) {
      document.body.style.overflow = "hidden";

      // Event handler to capture and stop all events
      const captureEvents = (e: Event) => {
        if (targetElementId) {
          // Check if the event target is inside our target element
          const targetElement = document.getElementById(targetElementId);
          if (
            targetElement &&
            (e.target === targetElement ||
              targetElement.contains(e.target as Node))
          ) {
            // Allow events within the target element
            return;
          }

          // Allow events from our feedback form
          if ((e.target as HTMLElement).closest(".feedback-form")) {
            return;
          }
        }

        // ADDED: Allow events from modal-root (where the portal renders)
        const modalRoot = document.getElementById("modal-root");
        if (
          modalRoot &&
          (e.target === modalRoot || modalRoot.contains(e.target as Node))
        ) {
          return;
        }

        // Stop all other events from propagating
        e.stopPropagation();
        e.preventDefault();
      };

      // Capture all these events
      const eventsToCapture = [
        "click",
        "mousedown",
        "mouseup",
        "mousemove",
        "touchstart",
        "touchend",
        "touchmove",
        "keydown",
        "keyup",
        "keypress",
        "wheel",
        "scroll",
      ];

      // Add event listeners with capture phase
      eventsToCapture.forEach((eventName) => {
        document.addEventListener(eventName, captureEvents, { capture: true });
      });

      // Clean up
      return () => {
        document.body.style.overflow = "";
        eventsToCapture.forEach((eventName) => {
          document.removeEventListener(eventName, captureEvents, {
            capture: true,
          });
        });
      };
    }
  }, [isVisible, targetElementId]);

  // Apply styles to target element
  useEffect(() => {
    if (isVisible && targetElementId) {
      const targetEl = document.getElementById(targetElementId);
      if (targetEl) {
        // Save original styles
        const originalPosition = targetEl.style.position;
        const originalZIndex = targetEl.style.zIndex;
        // Apply new styles
        targetEl.style.position = "relative";
        targetEl.style.zIndex = `${zIndex + 1}`;
        // Clean up function to restore original styles
        return () => {
          targetEl.style.position = originalPosition;
          targetEl.style.zIndex = originalZIndex;
        };
      }
    }
  }, [isVisible, targetElementId, zIndex]);

  const handleSubmitFeedback = () => {
    onClose();

    if (onInputResponse) {
      if (runStatus === "awaiting_input") {
        const feedbackToSend =
          userFeedback.trim() === "" ? "Resume" : userFeedback;
        onInputResponse(feedbackToSend, [], true);
      }
    }

    setUserFeedback("");
  };

  if (!isVisible) return null;

  return (
    <div
      id="fullscreen-overlay"
      className="fixed inset-0 bg-black bg-opacity-50"
      style={{ zIndex }}
      aria-label="Control Mode Active"
    >
      {/* Feedback Form Component */}
      <FeedbackForm
        userFeedback={userFeedback}
        setUserFeedback={setUserFeedback}
        onSubmit={handleSubmitFeedback}
      />

      {children}
    </div>
  );
};

export default FullscreenOverlay;
