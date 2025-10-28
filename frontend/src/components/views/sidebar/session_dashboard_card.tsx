import React from "react";
import {
  Clock4,
  CircleCheck,
  Hand,
  TriangleAlert,
  CornerDownRight,
} from "lucide-react";
import type { Session, SidebarRunStatus } from "../../types/datamodel";
import { SessionActionsMenu } from "./session_actions_menu";
import { Button } from "../../common/Button";

// Status color definitions
const STATUS_COLOR = {
  PLANNING: "#6A7282", // Gray
  RUNNING: "#2B7FFF", // Blue
  PAUSED: "#FF6900", // Orange
  ERROR: "#FB2C36", // Red
  COMPLETED: "#00C950", // Green
} as const;

// Map SidebarRunStatus to status colors
const STATUS_COLORS: Record<SidebarRunStatus, string> = {
  created: STATUS_COLOR.PLANNING,
  active: STATUS_COLOR.RUNNING,
  awaiting_input: STATUS_COLOR.PAUSED,
  paused: STATUS_COLOR.PAUSED,
  pausing: STATUS_COLOR.PAUSED,
  timeout: STATUS_COLOR.ERROR,
  error: STATUS_COLOR.ERROR,
  stopped: STATUS_COLOR.ERROR,
  final_answer_awaiting_input: STATUS_COLOR.COMPLETED,
  final_answer_stopped: STATUS_COLOR.COMPLETED,
  complete: STATUS_COLOR.COMPLETED,
  resuming: STATUS_COLOR.RUNNING,
  connected: STATUS_COLOR.RUNNING,
};

interface SessionDashboardCardProps {
  session: Session;
  isActive: boolean;
  isCurrent: boolean;
  isLoading?: boolean;
  status?: SidebarRunStatus;
  onSelect: () => void;
  onEdit: () => void;
  onStop: () => void;
  onDelete: () => void;
}

export const SessionDashboardCard: React.FC<SessionDashboardCardProps> = ({
  session,
  isActive,
  isCurrent,
  isLoading = false,
  status = "created",
  onSelect,
  onEdit,
  onStop,
  onDelete,
}) => {
  const statusColor = STATUS_COLORS[status];
  const isCompleted =
    status === "complete" ||
    status === "final_answer_stopped" ||
    status === "final_answer_awaiting_input";
  const isPlanning = status === "created";
  const isError =
    status === "error" || status === "stopped" || status === "timeout";

  // State to trigger re-render every second
  const [currentTime, setCurrentTime] = React.useState(new Date());

  // Update time every second
  React.useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(new Date());
    }, 1000);

    return () => clearInterval(timer);
  }, []);

  // ============================================================================
  // REAL DATA: Calculated from actual Session data
  // ============================================================================

  // Calculate elapsed time from session creation
  const formatElapsedTime = (): string => {
    if (!session.created_at) return "0:00";

    try {
      // Use currentTime state instead of creating new Date() each time
      const now = currentTime;

      // Ensure the created_at string is in proper ISO format with timezone
      // Backend might return format like "2025-10-28T00:12:34" without timezone
      let createdAtStr = session.created_at;

      // If the string doesn't have timezone info (Z or +/-), assume it's UTC
      if (
        !createdAtStr.includes("Z") &&
        !createdAtStr.includes("+") &&
        !createdAtStr.includes("-", 10)
      ) {
        // Add 'Z' to indicate UTC
        createdAtStr = createdAtStr + "Z";
      }

      const created = new Date(createdAtStr);

      // Check if date is valid
      if (isNaN(created.getTime())) {
        console.warn("Invalid created_at date:", session.created_at);
        return "0:00";
      }

      const diffMs = now.getTime() - created.getTime();

      // If negative, the created_at is in the future (likely timezone issue)
      if (diffMs < 0) {
        console.warn("Negative time difference:", {
          now: now.toISOString(),
          created: session.created_at,
          createdParsed: created.toISOString(),
          diffMs,
        });
        return "0:00";
      }

      const diffSecs = Math.floor(diffMs / 1000);
      const totalMins = Math.floor(diffSecs / 60);
      const totalHours = Math.floor(totalMins / 60);
      const days = Math.floor(totalHours / 24);

      const secs = diffSecs % 60;
      const mins = totalMins % 60;
      const hours = totalHours % 24;

      // For times >= 24 hours, show text format (e.g., "2 days 5 hrs")
      if (days > 0) {
        const dayText = days === 1 ? "day" : "days";
        return `${days} ${dayText} ${totalHours % 24} hrs`;
      }

      // For times >= 1 hour, show H:MM:SS format (e.g., "1:23:45")
      if (totalHours > 0) {
        return `${totalHours}:${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
      }

      // For times < 1 hour, show MM:SS format (e.g., "23:45")
      return `${totalMins}:${secs.toString().padStart(2, "0")}`;
    } catch (error) {
      console.error("Error calculating elapsed time:", error);
      return "0:00";
    }
  };

  const elapsedTime = formatElapsedTime();

  // ============================================================================
  // PLACEHOLDER DATA: For features not yet tracked by backend
  // ============================================================================
  // TODO: Replace with actual data when backend provides:
  // - Step tracking (currentStep, totalSteps, stepDescription)
  // - Action count from Run messages
  // - Detailed error messages from Run.error_message
  // - Progress calculation based on completed steps
  // ============================================================================

  const currentStep = 3;
  const totalSteps = 5;
  const actionCount = 35;
  const progressPercentage = (currentStep / totalSteps) * 100;
  const currentStepDescription = "Look into existing code to...";
  const currentActionDescription = "Needs clarification: Framework...";

  const additionalStatusMessage =
    status === "awaiting_input" ? "Waiting for your input" : null;
  const errorMessage = isError ? "Multiple failures - may need help" : null;

  return (
    <div
      className={`group relative w-full rounded-[10px] p-3 ${
        isLoading ? "pointer-events-none opacity-50" : "cursor-pointer"
      } ${
        isCurrent
          ? "bg-[#1F1A2E] outline outline-1 -outline-offset-1 outline-magenta-800"
          : "hover:bg-hover bg-[#252525] outline outline-1 -outline-offset-1 outline-[#333333]"
      }`}
      onClick={() => !isLoading && onSelect()}
    >
      {/* Header: Status dot + Title + Time/Completed */}
      <div className="mb-2 flex items-start justify-between">
        <div className="flex min-w-0 flex-1 items-center gap-2">
          {/* Status indicator dot */}
          <div
            className="h-2 w-2 flex-shrink-0 rounded-full"
            style={{ backgroundColor: statusColor }}
          />
          {/* Session title */}
          <div
            className={`min-w-0 flex-1 truncate text-sm leading-5 text-white ${
              isCurrent ? "font-semibold" : "font-normal"
            }`}
          >
            {session.name}
          </div>
        </div>

        {/* Right side: Time or Completed status */}
        <div className="flex flex-shrink-0 items-center gap-1 text-xs leading-4">
          {isCompleted ? (
            <>
              <CircleCheck
                className="h-3 w-3"
                style={{ color: STATUS_COLOR.COMPLETED }}
              />
              <span style={{ color: STATUS_COLOR.COMPLETED }}>Completed</span>
            </>
          ) : !isPlanning ? (
            <>
              <Clock4 className="h-3 w-3 text-[#85B5FF]" />
              <span className="text-[#85B5FF]">{elapsedTime}</span>
            </>
          ) : null}
        </div>
      </div>

      {/* Progress bars - only show when not planning and not completed */}
      {!isPlanning && !isCompleted && (
        <div className="relative mb-2">
          {/* Background progress bar */}
          <div className="h-1 w-full rounded-sm bg-[#4B4B4B]" />
          {/* Active progress bar */}
          <div
            className="absolute left-0 top-0 h-1 rounded-sm bg-magenta-800"
            style={{ width: `${progressPercentage}%` }}
          />
        </div>
      )}

      {/* Step details - show when running, paused, or error */}
      {!isPlanning && !isCompleted && (
        <div
          className={`space-y-1 ${additionalStatusMessage || errorMessage ? "mb-2" : ""}`}
        >
          {/* Step count and action count */}
          <div className="flex items-center justify-between text-xs leading-4 text-[#99A1AF]">
            <span>
              Step {currentStep}/{totalSteps}
            </span>
            <span>{actionCount} actions</span>
          </div>

          {/* Current step description */}
          <div className="truncate text-xs font-semibold leading-4 text-[#99A1AF]">
            {currentStepDescription}
          </div>

          {/* Current action description with icon */}
          <div className="flex items-start gap-1 text-xs leading-4 text-[#99A1AF]">
            <CornerDownRight className="mt-0.5 h-3 w-3 flex-shrink-0" />
            <span className="truncate">
              {isError
                ? "Error: API rate limit exceeded"
                : currentActionDescription}
            </span>
          </div>
        </div>
      )}

      {/* Completed step details */}
      {isCompleted && (
        <div className="space-y-1">
          {/* Step count and action count */}
          <div className="flex items-center justify-between text-xs leading-4 text-[#99A1AF]">
            <span>
              Step {totalSteps}/{totalSteps}
            </span>
            <span>{actionCount} actions</span>
          </div>

          {/* Completed status */}
          <div className="text-xs font-semibold leading-4 text-[#99A1AF]">
            Completed
          </div>

          {/* Final action description with icon */}
          <div className="flex items-start gap-1 pl-2.5 text-xs leading-4 text-[#99A1AF]">
            <CornerDownRight className="mt-0.5 h-3 w-3 flex-shrink-0" />
            <span className="truncate">Meeting scheduled for 2pm PST</span>
          </div>
        </div>
      )}

      {/* Planning state message */}
      {isPlanning && (
        <div className="text-xs leading-4 text-[#99A1AF]">
          Start chatting to make a plan
        </div>
      )}

      {/* Additional status message - only for awaiting_input */}
      {additionalStatusMessage && !isError && (
        <div
          className="flex items-center gap-1.5 text-xs leading-4"
          style={{ color: STATUS_COLOR.PAUSED }}
        >
          <Hand className="h-3 w-3 flex-shrink-0" />
          <span>{additionalStatusMessage}</span>
        </div>
      )}

      {/* Error message - only for error states */}
      {isError && errorMessage && (
        <div className="flex items-center justify-between">
          <div
            className="flex items-center gap-1.5 text-xs leading-4"
            style={{ color: STATUS_COLOR.ERROR }}
          >
            <TriangleAlert className="h-3 w-3 flex-shrink-0" />
            <span>{errorMessage}</span>
          </div>
        </div>
      )}

      {/* Dropdown menu (hidden, appears on hover) - positioned absolutely */}
      <div className="absolute bottom-2 right-2 opacity-0 transition-opacity group-hover:opacity-100">
        <SessionActionsMenu
          sessionId={Number(session.id)}
          isActive={isActive}
          onEdit={onEdit}
          onStop={onStop}
          onDelete={onDelete}
        />
      </div>
    </div>
  );
};
