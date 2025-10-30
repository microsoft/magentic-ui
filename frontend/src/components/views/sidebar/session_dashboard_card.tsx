import React from "react";
import {
  CircleCheck,
  Hand,
  TriangleAlert,
  CornerDownRight,
  LoaderCircle,
} from "lucide-react";
import type { Session, UIRunStatus, InputRequest } from "../../types/datamodel";
import { SessionActionsMenu } from "./session_actions_menu";

// Status color definitions
const STATUS_COLOR_CODE = {
  GRAY: "#6A7282",
  GREEN: "#00C950",
  ORANGE: "#FF6900",
  RED: "#FB2C36",
} as const;

// Map UIRunStatus to status colors
const STATUS_COLORS: Record<UIRunStatus, string> = {
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
  status?: UIRunStatus;
  inputRequest?: InputRequest;
  errorMessage?: string;
  currentStep?: number;
  totalSteps?: number;
  currentStepTitle?: string;
  currentInstruction?: string;
  finalAnswer?: string;
  stopReason?: string;
  onSelect: (session: Session) => void;
  onEdit: (session: Session) => void;
  onStop: (sessionId: number) => void;
  onDelete: (sessionId: number) => void;
}

const SessionDashboardCardComponent: React.FC<SessionDashboardCardProps> = ({
  session,
  isActive,
  isCurrent,
  isLoading = false,
  status = "created",
  errorMessage,
  currentStep,
  totalSteps,
  currentStepTitle,
  currentInstruction,
  finalAnswer,
  stopReason,
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

  // Calculate progress states
  const hasPlan = totalSteps !== undefined && totalSteps > 0;
  const isPlanExecuting = currentStep !== undefined && currentStep >= 0;
  const hasProgress = hasPlan && isPlanExecuting;

  // Display step as "Step 0/5" when plan exists but not yet started executing
  const displayStep = isPlanExecuting ? currentStep + 1 : 0;

  // Ensure progress doesn't overflow - if currentStep exceeds totalSteps, cap at 100%
  const safeCurrentStep = hasProgress
    ? Math.min(currentStep, totalSteps - 1)
    : 0;
  const progressPercentage = hasProgress
    ? ((safeCurrentStep + 1) / totalSteps) * 100
    : 0;

  // Use actual data when available
  const inputPrompt =
    status === "awaiting_input"
      ? hasProgress
        ? "Waiting for your input"
        : "Review and approve the plan"
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
      onClick={() => !isLoading && onSelect(session)}
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

      {/* Progress bars - show when we have a plan (even if not started) and not completed */}
      {!isPlanning && !isCompleted && hasPlan && (
        <div className="relative mb-2">
          {/* Background progress bar (gray) */}
          <div className="h-1 w-full rounded-sm bg-[#4B4B4B]" />

          {/* Active progress bar with animated current step */}
          {hasProgress && (
            <>
              {/* Completed portion - rounded on left side only */}
              <div
                className="absolute left-0 top-0 h-1 bg-magenta-800"
                style={{
                  width: `${(safeCurrentStep / totalSteps) * 100}%`,
                  borderTopLeftRadius: "0.125rem",
                  borderBottomLeftRadius: "0.125rem",
                }}
              />

              {/* Currently executing step - animated stripes, rounded on right side only */}
              <div
                className="absolute top-0 h-1 overflow-hidden"
                style={{
                  left: `${(safeCurrentStep / totalSteps) * 100}%`,
                  width: `${(1 / totalSteps) * 100}%`,
                  borderTopRightRadius: "0.125rem",
                  borderBottomRightRadius: "0.125rem",
                }}
              >
                <div
                  className="h-full bg-magenta-800"
                  style={{
                    backgroundImage: `repeating-linear-gradient(
                      45deg,
                      transparent,
                      transparent 3px,
                      rgba(255, 255, 255, 0.2) 4px,
                      rgba(255, 255, 255, 0.2) 8px
                    )`,
                    backgroundSize: "12px 100%",
                    animation: "progress-stripes 0.8s linear infinite",
                  }}
                />
              </div>
            </>
          )}
        </div>
      )}

      {/* Step details - show when we have a plan */}
      {!isPlanning && !isCompleted && hasPlan && (
        <div
          className={`space-y-1 ${inputPrompt || displayErrorMessage ? "mb-2" : ""}`}
        >
          {/* Step count */}
          <div className="text-xs leading-4 text-[#99A1AF]">
            Step {displayStep}/{totalSteps}
          </div>

          {/* Current step description - only show if executing */}
          {isPlanExecuting && currentStepTitle && (
            <div className="truncate text-xs font-semibold leading-4 text-[#99A1AF]">
              {currentStepTitle}
            </div>
          )}

          {/* Current instruction with icon - only show if executing */}
          {isPlanExecuting && currentInstruction && (
            <div className="flex items-start gap-1 text-xs leading-4 text-[#99A1AF]">
              <CornerDownRight className="mt-0.5 h-3 w-3 flex-shrink-0" />
              <span className="truncate">{currentInstruction}</span>
            </div>
          )}
        </div>
      )}

      {/* Completed state - show progress bar and final info */}
      {isCompleted && hasPlan && (
        <>
          {/* Progress bar - fully filled */}
          <div className="relative mb-2">
            <div className="h-1 w-full rounded-sm bg-[#4B4B4B]" />
            <div className="absolute left-0 top-0 h-1 w-full rounded-sm bg-magenta-800" />
          </div>

          {/* Completion details */}
          <div className="space-y-1">
            {/* Step count */}
            <div className="text-xs leading-4 text-[#99A1AF]">
              Step {totalSteps}/{totalSteps}
            </div>

            {/* Completed status */}
            <div className="text-xs font-semibold leading-4 text-[#99A1AF]">
              Completed
            </div>

            {/* Final answer or stop reason */}
            {(finalAnswer || stopReason) && (
              <div className="flex items-start gap-1 text-xs leading-4 text-[#99A1AF]">
                <CornerDownRight className="mt-0.5 h-3 w-3 flex-shrink-0" />
                <span className="truncate">
                  {finalAnswer
                    ? finalAnswer.length > 50
                      ? `${finalAnswer.substring(0, 50)}...`
                      : finalAnswer
                    : stopReason}
                </span>
              </div>
            )}
          </div>
        </>
      )}

      {/* Planning state message */}
      {isPlanning && (
        <div className="text-xs leading-4 text-[#99A1AF]">
          Type a task to get started
        </div>
      )}

      {/* Additional status message - for awaiting_input and other statuses */}
      {inputPrompt && !isError && (
        <div
          className="flex items-center gap-1.5 text-xs leading-4"
          style={{ color: statusColor }}
        >
          <Hand className="h-3 w-3 flex-shrink-0" />
          <span className="truncate">{inputPrompt}</span>
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
          onEdit={() => onEdit(session)}
          onStop={() => session.id && onStop(session.id)}
          onDelete={() => session.id && onDelete(session.id)}
        />
      </div>
    </div>
  );
};

export const SessionDashboardCard = React.memo(SessionDashboardCardComponent);
