import React from "react";
import {
  StopCircle,
  MessageSquare,
  Loader2,
  AlertTriangle,
  PauseCircle,
  HelpCircle,
  CheckCircle,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { Run, InputRequest } from "../types/datamodel";

export const getStatusIcon = (
  status: Run["status"],
  errorMessage?: string,
  stopReason?: string,
  inputRequest?: InputRequest
) => {
  const { t } = useTranslation();
  switch (status) {
    case "active":
      return (
        <div className="inline-block mr-1">
          <Loader2
            size={20}
            className="inline-block mr-1 text-accent animate-spin"
          />
          <span className="inline-block mr-2 ml-1 ">{t("statusIcon.processing")}</span>
        </div>
      );
    case "awaiting_input":
      const Icon =
        inputRequest?.input_type === "approval" ? HelpCircle : MessageSquare;
      return (
        <div className="flex items-center text-sm mb-2">
          {inputRequest?.input_type === "approval" ? (
            <div>
              <div className="flex items-center">
                <span>
                  <span className="font-semibold">{t("statusIcon.approvalRequest")}:</span>{" "}
                  {inputRequest.prompt || t("statusIcon.waitingForApproval")}
                </span>
              </div>
            </div>
          ) : (
            <>
              <MessageSquare
                size={20}
                className="flex-shrink-0 mr-2 text-accent"
              />
              <span className="flex-1">{t("statusIcon.waitingForInput")}</span>
            </>
          )}
        </div>
      );
    case "complete":
      return (
        <div className="text-sm mb-2">
          <AlertTriangle size={20} className="inline-block mr-2 text-red-500" />
          {errorMessage || t("statusIcon.errorOccurred")}
        </div>
      );
    case "error":
      return (
        <div className="text-sm mb-2">
          <AlertTriangle size={20} className="inline-block mr-2 text-red-500" />
          {errorMessage || t("statusIcon.errorOccurred")}
        </div>
      );
    case "stopped":
      return (
        <div className="text-sm mb-2 mt-4">
          <StopCircle size={20} className="inline-block mr-2 text-red-500" />
          {t("statusIcon.taskStopped")}: {stopReason}
        </div>
      );
    case "pausing":
      return (
        <div className="text-sm mb-2">
          <Loader2
            size={20}
            className="inline-block mr-2 text-accent animate-spin"
          />
          <span className="inline-block mr-2 ml-1">{t("statusIcon.pausing")}</span>
        </div>
      );
    case "paused":
      return (
        <div className="text-sm mb-2">
          <PauseCircle size={20} className="inline-block mr-2 text-accent" />
          <span className="inline-block mr-2 ml-1">{t("statusIcon.paused")}</span>
        </div>
      );
    case "resuming":
      return (
        <div className="text-sm mb-2">
          <Loader2
            size={20}
            className="inline-block mr-2 text-accent animate-spin"
          />
          <span className="inline-block mr-2 ml-1">{t("statusIcon.resuming")}</span>
        </div>
      );
    default:
      return null;
  }
};

// SessionRunStatusIndicator: for sidebar session status
export const SessionRunStatusIndicator: React.FC<{
  status?: Run["status"] | "final_answer_awaiting_input";
}> = ({ status }) => {
  switch (status) {
    case "awaiting_input":
      return <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />;
    case "active":
      return <Loader2 className="w-3 h-3 animate-spin text-accent" />;
    case "final_answer_awaiting_input":
      return <CheckCircle className="w-3 h-3 text-green-500" />;
    case "error":
      return <AlertTriangle className="w-3 h-3 text-red-500" />;
    default:
      return null;
  }
};
