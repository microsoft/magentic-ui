import React from "react";
import {
  StopCircle,
  MessageSquare,
  Loader2,
  AlertTriangle,
  PauseCircle,
  HelpCircle,
  CheckCircle,
  Clock,
} from "lucide-react";
import { InputRequest, UIRunStatus } from "../types/datamodel";

export const getStatusIcon = (
  status: UIRunStatus,
  errorMessage?: string,
  stopReason?: string,
  inputRequest?: InputRequest,
  isSentinelSleeping?: boolean,
) => {
  switch (status) {
    case "active":
      // Check if we're in a sentinel sleeping state
      if (isSentinelSleeping) {
        return (
          <div className="mr-1 inline-block">
            <Clock size={20} className="mr-1 inline-block text-blue-600" />
            <span className="ml-1 mr-2 inline-block">Sleeping</span>
          </div>
        );
      }
      return (
        <div className="mr-1 inline-block">
          <Loader2
            size={20}
            className="mr-1 inline-block animate-spin text-accent"
          />
          <span className="ml-1 mr-2 inline-block">Processing</span>
        </div>
      );
    case "awaiting_input":
      const Icon =
        inputRequest?.input_type === "approval" ? HelpCircle : MessageSquare;
      return (
        <div className="mb-2 flex items-center text-sm">
          {inputRequest?.input_type === "approval" ? (
            <div>
              <div className="flex items-center">
                <span>
                  <span className="font-semibold">Approval Request:</span>{" "}
                  {inputRequest.prompt || "Waiting for approval"}
                </span>
              </div>
            </div>
          ) : (
            <>
              <MessageSquare
                size={20}
                className="mr-2 flex-shrink-0 text-accent"
              />
              <span className="flex-1">Waiting for your input</span>
            </>
          )}
        </div>
      );
    case "complete":
      return (
        <div className="mb-2 text-sm">
          <AlertTriangle size={20} className="mr-2 inline-block text-red-500" />
          {errorMessage || "An error occurred"}
        </div>
      );
    case "error":
      return (
        <div className="mb-2 text-sm">
          <AlertTriangle size={20} className="mr-2 inline-block text-red-500" />
          {errorMessage || "An error occurred"}
        </div>
      );
    case "stopped":
      return (
        <div className="mb-2 mt-4 text-sm">
          <StopCircle size={20} className="mr-2 inline-block text-red-500" />
          Task was stopped: {stopReason}
        </div>
      );
    case "pausing":
      return (
        <div className="mb-2 text-sm">
          <Loader2
            size={20}
            className="mr-2 inline-block animate-spin text-accent"
          />
          <span className="ml-1 mr-2 inline-block">Pausing</span>
        </div>
      );
    case "paused":
      return (
        <div className="mb-2 text-sm">
          <PauseCircle size={20} className="mr-2 inline-block text-accent" />
          <span className="ml-1 mr-2 inline-block">Paused</span>
        </div>
      );
    case "resuming":
      return (
        <div className="mb-2 text-sm">
          <Loader2
            size={20}
            className="mr-2 inline-block animate-spin text-accent"
          />
          <span className="ml-1 mr-2 inline-block">Resuming</span>
        </div>
      );
    default:
      return null;
  }
};

// SessionRunStatusIndicator: for sidebar session status
export const SessionRunStatusIndicator: React.FC<{
  status?: UIRunStatus;
}> = ({ status }) => {
  switch (status) {
    case "awaiting_input":
      return <div className="h-2 w-2 animate-pulse rounded-full bg-red-500" />;
    case "active":
      return <Loader2 className="h-3 w-3 animate-spin text-accent" />;
    case "final_answer_awaiting_input":
      return <CheckCircle className="h-3 w-3 text-green-500" />;
    case "final_answer_stopped":
      return <CheckCircle className="h-3 w-3 text-green-500" />;
    case "error":
      return <AlertTriangle className="h-3 w-3 text-red-500" />;
    default:
      return null;
  }
};
