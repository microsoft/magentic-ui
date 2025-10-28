import React from "react";
import {
  CircleCheck,
  Hand,
  TriangleAlert,
  CornerDownRight,
  LoaderCircle,
} from "lucide-react";
import type {
  Session,
  SidebarRunStatus,
  InputRequest,
} from "../../types/datamodel";
import { SessionActionsMenu } from "./session_actions_menu";

// Status color definitions
const STATUS_COLOR_CODE = {
  GRAY: "#6A7282",
  GREEN: "#00C950",
  ORANGE: "#FF6900",
  RED: "#FB2C36",
} as const;

// Map SidebarRunStatus to status colors
const STATUS_COLORS: Record<SidebarRunStatus, string> = {
  created: STATUS_COLOR_CODE.GRAY,
  active: STATUS_COLOR_CODE.GREEN,
  awaiting_input: STATUS_COLOR_CODE.ORANGE,
  paused: STATUS_COLOR_CODE.ORANGE,
  pausing: STATUS_COLOR_CODE.ORANGE,
  timeout: STATUS_COLOR_CODE.RED,
  error: STATUS_COLOR_CODE.RED,
  stopped: STATUS_COLOR_CODE.RED,
  final_answer_awaiting_input: STATUS_COLOR_CODE.GREEN,
  final_answer_stopped: STATUS_COLOR_CODE.GREEN,
  complete: STATUS_COLOR_CODE.GREEN,
  resuming: STATUS_COLOR_CODE.GREEN,
  connected: STATUS_COLOR_CODE.GREEN,
};

interface SessionDashboardCardProps {
  session: Session;
  isActive: boolean;
  isCurrent: boolean;
  isLoading?: boolean;
  status?: SidebarRunStatus;
  inputRequest?: InputRequest;
  errorMessage?: string;
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
  inputRequest,
  errorMessage,
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
  const isActiveRunning =
    status === "active" || status === "resuming" || status === "connected";

  // ============================================================================
  // REAL DATA: Calculated from actual Session data
  // ============================================================================
  // TODO: Replace with actual data when backend provides:
  // - Step tracking (currentStep, totalSteps, stepDescription)
  // - Action count from Run messages
  // - Progress calculation based on completed steps
  // ============================================================================

  const currentStep = 3;
  const totalSteps = 5;
  const actionCount = 35;
  const progressPercentage = (currentStep / totalSteps) * 100;
  const currentStepDescription = "Look into existing code to...";
  const currentActionDescription = "Needs clarification: Framework...";

  // Use actual data when available
  const additionalStatusMessage =
    status === "awaiting_input"
      ? inputRequest?.prompt || "Waiting for your input2"
      : null;
  const displayErrorMessage = isError
    ? errorMessage || "An error occurred"
    : null;

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

        {/* Right side: Active indicator or Completed status */}
        <div className="flex flex-shrink-0 items-center gap-1 text-xs leading-5">
          {isCompleted ? (
            <>
              <CircleCheck className="h-3 w-3" style={{ color: statusColor }} />
              <span style={{ color: statusColor }}>Completed</span>
            </>
          ) : isActiveRunning ? (
            <LoaderCircle className="-mb-5 h-3 w-3 animate-spin text-[#85B5FF]" />
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
          {/* Step count */}
          <div className="text-xs leading-4 text-[#99A1AF]">
            Step {currentStep}/{totalSteps}
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
          {/* Step count */}
          <div className="text-xs leading-4 text-[#99A1AF]">
            Step {totalSteps}/{totalSteps}
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
          Enter a message to get started
        </div>
      )}

      {/* Additional status message - only for awaiting_input */}
      {additionalStatusMessage && !isError && (
        <div
          className="flex items-center gap-1.5 text-xs leading-4"
          style={{ color: statusColor }}
        >
          <Hand className="h-3 w-3 flex-shrink-0" />
          <span className="truncate">{additionalStatusMessage}</span>
        </div>
      )}

      {/* Error message - only for error states */}
      {isError && displayErrorMessage && (
        <div className="flex items-center justify-between">
          <div
            className="flex items-center gap-1.5 text-xs leading-4"
            style={{ color: statusColor }}
          >
            <TriangleAlert className="h-3 w-3 flex-shrink-0" />
            <span className="truncate">{displayErrorMessage}</span>
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
