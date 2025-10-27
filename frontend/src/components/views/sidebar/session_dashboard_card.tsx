import React from "react";
import { Dropdown, Menu } from "antd";
import {
  Edit,
  Trash2,
  StopCircle,
  MoreVertical,
  Clock4,
  CircleCheck,
  Hand,
  TriangleAlert,
  CornerDownRight,
} from "lucide-react";
import type { Session, RunStatus } from "../../types/datamodel";
import { SessionRunStatusIndicator } from "../statusicon";
import LearnPlanButton from "../../features/Plans/LearnPlanButton";
import { Button } from "../../common/Button";

// Status color definitions
const STATUS_COLOR = {
  PLANNING: "#6A7282", // Gray
  RUNNING: "#2B7FFF", // Blue
  PAUSED: "#FF6900", // Orange
  ERROR: "#FB2C36", // Red
  COMPLETED: "#00C950", // Green
} as const;

// Map RunStatus to status colors
const STATUS_COLORS: Record<RunStatus, string> = {
  created: STATUS_COLOR.PLANNING,
  active: STATUS_COLOR.RUNNING,
  awaiting_input: STATUS_COLOR.PAUSED,
  paused: STATUS_COLOR.PAUSED,
  pausing: STATUS_COLOR.PAUSED,
  timeout: STATUS_COLOR.ERROR,
  error: STATUS_COLOR.ERROR,
  stopped: STATUS_COLOR.ERROR,
  complete: STATUS_COLOR.COMPLETED,
  resuming: STATUS_COLOR.RUNNING,
  connected: STATUS_COLOR.RUNNING,
};

interface SessionDashboardCardProps {
  session: Session;
  isActive: boolean;
  isCurrent: boolean;
  isLoading?: boolean;
  status?: RunStatus;
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
  // Placeholder data - will be replaced with real data from Session object
  const elapsedTime = "9:00";
  const currentStep = 3;
  const totalSteps = 5;
  const actionCount = 35;
  const progressPercentage = (currentStep / totalSteps) * 100;
  const currentStepDescription = "Look into existing code to...";
  const currentActionDescription = "Needs clarification: Framework...";
  const additionalStatusMessage =
    status === "awaiting_input" ? "Waiting for your input" : null;

  const statusColor = STATUS_COLORS[status];
  const isCompleted = status === "complete";
  const isPlanning = status === "created";
  const isError =
    status === "error" || status === "stopped" || status === "timeout";
  const errorMessage = isError ? "Multiple failures - may need help" : null;

  // Format elapsed time (placeholder function)
  const formatElapsedTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

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
        <div className="mb-2 space-y-1">
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
          <div className="flex items-start gap-1 pl-2.5 text-xs leading-4 text-[#99A1AF]">
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
        <div className="mb-2 space-y-1">
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
        <Dropdown
          trigger={["click"]}
          overlay={
            <Menu>
              <Menu.Item
                key="edit"
                onClick={(e) => {
                  e.domEvent.stopPropagation();
                  onEdit();
                }}
              >
                <Edit className="-mt-0.5 mr-1.5 inline-block h-4 w-4" /> Edit
              </Menu.Item>
              <Menu.Item
                key="stop"
                onClick={(e) => {
                  e.domEvent.stopPropagation();
                  if (isActive) onStop();
                }}
                disabled={!isActive}
                danger
              >
                <StopCircle className="-mt-0.5 mr-1.5 inline-block h-4 w-4" />{" "}
                Disconnect
              </Menu.Item>
              <Menu.Item
                key="delete"
                onClick={(e) => {
                  e.domEvent.stopPropagation();
                  onDelete();
                }}
                danger
              >
                <Trash2 className="-mt-0.5 mr-1.5 inline-block h-4 w-4" />{" "}
                Delete
              </Menu.Item>
              <Menu.Item
                key="learn-plan"
                onClick={(e) => e.domEvent.stopPropagation()}
              >
                <LearnPlanButton
                  sessionId={Number(session.id)}
                  messageId={-1}
                />
              </Menu.Item>
            </Menu>
          }
          placement="bottomRight"
        >
          <Button
            variant="tertiary"
            size="sm"
            icon={<MoreVertical className="h-4 w-4" />}
            onClick={(e) => e.stopPropagation()}
            className="h-6 min-w-[24px] !p-0"
          />
        </Dropdown>
      </div>
    </div>
  );
};
