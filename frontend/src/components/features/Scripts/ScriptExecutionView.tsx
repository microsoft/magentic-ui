import React, { useState, useEffect, useRef, useContext } from "react";
import { Progress, Button, message } from "antd";
import {
  CheckCircle,
  XCircle,
  Play,
  ArrowLeft,
  ExternalLink,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { appContext } from "../../../hooks/provider";
import { ScriptAPI } from "../../views/api";
import { IScript } from "./ScriptCard";
import BrowserIframe from "../../views/chat/DetailViewer/browser_iframe";
import { useSettingsStore } from "../../store";

interface ActionResult {
  action_index: number;
  action_type: string;
  description: string;
  status: "pending" | "running" | "success" | "failed" | "skipped";
  error?: string;
  screenshot?: string;
}

interface ScriptExecutionViewProps {
  script: IScript;
  sessionId?: number | null;
  onBack: () => void;
}

const ScriptExecutionView: React.FC<ScriptExecutionViewProps> = ({
  script,
  sessionId,
  onBack,
}) => {
  const { t } = useTranslation();
  const { user } = useContext(appContext);
  const userId = user?.email || "default";
  const scriptAPI = new ScriptAPI();
  const config = useSettingsStore((state) => state.config);

  const [status, setStatus] = useState<
    "idle" | "connecting" | "running" | "completed" | "stopped" | "error"
  >("idle");
  const [currentAction, setCurrentAction] = useState<number>(-1);
  const [totalActions, setTotalActions] = useState<number>(0);
  const [actionResults, setActionResults] = useState<ActionResult[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [vncPort, setVncPort] = useState<string | null>(null);
  const [finalScreenshot, setFinalScreenshot] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string>("");

  const wsRef = useRef<WebSocket | null>(null);
  const actionListRef = useRef<HTMLDivElement | null>(null);
  const statusRef = useRef(status); // Track latest status for closures

  // Keep statusRef in sync with status
  useEffect(() => {
    statusRef.current = status;
  }, [status]);

  // Auto-scroll to current action
  useEffect(() => {
    if (actionListRef.current && currentAction >= 0) {
      const actionElement = actionListRef.current.querySelector(
        `[data-action-index="${currentAction}"]`
      );
      if (actionElement) {
        actionElement.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    }
  }, [currentAction]);

  useEffect(() => {
    if (script?.id) {
      startExecution();
    }

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [script?.id]);

  const startExecution = () => {
    if (!script?.id) return;

    setStatus("connecting");
    setCurrentAction(-1);
    setTotalActions(script.actions?.length || 0);
    setActionResults([]);
    setError(null);
    setVncPort(null);
    setFinalScreenshot(null);
    setStatusMessage(t("scripts.connectingToBrowser"));

    const wsUrl = scriptAPI.getExecuteWebSocketUrl(script.id, userId, sessionId || undefined);
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setStatus("running");
      setStatusMessage(t("scripts.executionStarted"));
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleMessage(data);
      } catch (e) {
        console.error("Failed to parse WebSocket message:", e);
      }
    };

    ws.onerror = (event) => {
      console.error("WebSocket error:", event);
      setError(t("scripts.connectionError"));
      setStatus("error");
    };

    ws.onclose = () => {
      // Use statusRef to get the latest status value
      if (statusRef.current === "running") {
        // Unexpected close
        setStatus("error");
        setError(t("scripts.connectionClosed"));
      }
    };
  };

  const handleMessage = (data: any) => {
    switch (data.type) {
      case "script_execution_start":
        setTotalActions(data.data.total_actions);
        setStatusMessage(
          t("scripts.executingScript", { task: data.data.task })
        );
        break;

      case "script_status":
        setStatusMessage(data.message);
        break;

      case "vnc_info":
        setVncPort(data.data.vnc_port?.toString());
        break;

      case "action_start":
        setCurrentAction(data.data.action_index);
        setStatusMessage(
          t("scripts.executingAction", {
            current: data.data.action_index + 1,
            total: data.data.total_actions,
            description: data.data.description,
          })
        );
        // Add pending action
        setActionResults((prev) => [
          ...prev,
          {
            action_index: data.data.action_index,
            action_type: "",
            description: data.data.description,
            status: "running",
          },
        ]);
        break;

      case "action_complete":
        // Update action result
        setActionResults((prev) =>
          prev.map((ar) =>
            ar.action_index === data.data.action_index
              ? {
                  ...ar,
                  action_type: data.data.action_type,
                  status: data.data.status,
                  error: data.data.error,
                  screenshot: data.data.screenshot,
                }
              : ar
          )
        );
        break;

      case "script_execution_complete":
        setStatus("completed");
        setFinalScreenshot(data.data.final_screenshot);
        if (data.data.success) {
          setStatusMessage(t("scripts.executionCompleted"));
          message.success(t("scripts.scriptExecutedSuccessfully"));
        } else {
          setStatusMessage(
            t("scripts.executionFailed", { error: data.data.error })
          );
          message.error(
            t("scripts.scriptExecutionFailed", { error: data.data.error })
          );
        }
        break;

      case "script_execution_error":
        setStatus("error");
        setError(data.error);
        setStatusMessage(t("scripts.executionError", { error: data.error }));
        break;

      case "error":
        setStatus("error");
        setError(data.error);
        break;
    }
  };

  const handleStop = () => {
    if (wsRef.current) {
      // Send stop signal to backend before closing
      try {
        wsRef.current.send(JSON.stringify({ type: "stop" }));
      } catch (e) {
        console.error("Failed to send stop signal:", e);
      }
      // Update status to stopped (distinct from completed)
      setStatus("stopped");
      setStatusMessage(t("scripts.executionStopped"));
      // Close WebSocket after sending stop signal
      wsRef.current.close();
      wsRef.current = null;
    }
  };

  const completedActions = actionResults.filter(
    (ar) => ar.status === "success"
  ).length;
  const progressPercent =
    totalActions > 0 ? Math.round((completedActions / totalActions) * 100) : 0;

  // Get server URL for browser iframe
  const serverHost = config.server_url || "localhost";

  return (
    <div className="h-full flex flex-col bg-primary">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b bg-secondary">
        <div className="flex items-center gap-3">
          <Button
            type="text"
            icon={<ArrowLeft className="h-5 w-5" />}
            onClick={onBack}
          />
          <div className="flex items-center gap-2">
            <Play className="h-5 w-5 text-primary" />
            <span className="text-lg font-medium text-primary">
              {script?.task || t("scripts.executeScript")}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {vncPort && (
            <Button
              type="default"
              onClick={() =>
                window.open(
                  `http://${serverHost}:${vncPort}/vnc.html`,
                  "_blank"
                )
              }
              icon={<ExternalLink className="h-4 w-4" />}
            >
              {t("scripts.openLiveView")}
            </Button>
          )}
          {status === "running" && (
            <Button type="default" onClick={handleStop} danger>
              {t("common.stop")}
            </Button>
          )}
        </div>
      </div>

      {/* Progress bar */}
      <div className="px-4 py-2 bg-tertiary border-b">
        <div className="text-sm text-secondary mb-1">{statusMessage}</div>
        <Progress
          percent={progressPercent}
          status={
            status === "error"
              ? "exception"
              : status === "completed"
              ? "success"
              : status === "stopped"
              ? "normal"
              : "active"
          }
          strokeColor={
            status === "running"
              ? "#1890ff"
              : status === "stopped"
              ? "#faad14"
              : undefined
          }
          size="small"
        />
        <div className="text-xs text-secondary mt-1">
          {completedActions} / {totalActions} {t("scripts.actionsCompleted")}
        </div>
      </div>

      {/* Main content area */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left panel - Action list */}
        <div className="w-[40%] border-r flex flex-col">
          <div className="p-3 bg-secondary border-b">
            <h3 className="text-sm font-medium text-primary">
              {t("scripts.actionList")}
            </h3>
          </div>
          <div
            ref={actionListRef}
            className="flex-1 overflow-y-auto p-2 space-y-1"
          >
            {/* Show all script actions */}
            {script.actions?.map((action: any, idx: number) => {
              const result = actionResults.find((ar) => ar.action_index === idx);
              const actionStatus = result?.status || "pending";
              const isActive = currentAction === idx;

              return (
                <div
                  key={idx}
                  data-action-index={idx}
                  className={`flex items-start gap-2 p-2 rounded-md transition-colors ${
                    isActive
                      ? "bg-blue-50 border border-blue-200"
                      : actionStatus === "success"
                      ? "bg-green-50"
                      : actionStatus === "failed"
                      ? "bg-red-50"
                      : "bg-tertiary hover:bg-secondary"
                  }`}
                >
                  {/* Status icon */}
                  <div className="flex-shrink-0 mt-0.5">
                    {actionStatus === "success" && (
                      <CheckCircle className="h-4 w-4 text-green-500" />
                    )}
                    {actionStatus === "failed" && (
                      <XCircle className="h-4 w-4 text-red-500" />
                    )}
                    {actionStatus === "running" && (
                      <div className="h-4 w-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                    )}
                    {actionStatus === "pending" && (
                      <div className="h-4 w-4 border-2 border-gray-300 rounded-full" />
                    )}
                    {actionStatus === "skipped" && (
                      <div className="h-4 w-4 bg-gray-300 rounded-full" />
                    )}
                  </div>

                  {/* Action content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-secondary font-mono">
                        #{idx + 1}
                      </span>
                      <span className="text-xs font-medium text-primary">
                        {action.action_type || result?.action_type}
                      </span>
                    </div>
                    <p className="text-sm text-primary truncate">
                      {action.description || result?.description}
                    </p>
                    {result?.error && (
                      <p className="text-xs text-red-500 mt-1 truncate">
                        {result.error}
                      </p>
                    )}
                  </div>
                </div>
              );
            })}

            {/* Error message */}
            {error && (
              <div className="bg-red-50 border border-red-200 rounded-md p-3 text-red-700 text-sm">
                {error}
              </div>
            )}
          </div>
        </div>

        {/* Right panel - Browser view */}
        <div className="flex-1 flex flex-col bg-tertiary">
          <div className="p-3 bg-secondary border-b flex items-center justify-between">
            <h3 className="text-sm font-medium text-primary">
              {t("scripts.browserView")}
            </h3>
            {vncPort && (
              <span className="text-xs text-secondary">
                VNC: {serverHost}:{vncPort}
              </span>
            )}
          </div>
          <div className="flex-1 p-2">
            {vncPort ? (
              <BrowserIframe
                novncPort={vncPort}
                style={{ height: "100%", borderRadius: "8px" }}
                className="w-full h-full"
                showDimensions={true}
                quality={7}
                viewOnly={false}
                scaling="local"
                showTakeControlOverlay={false}
                serverUrl={serverHost}
              />
            ) : (status === "completed" || status === "stopped") && finalScreenshot ? (
              <div className="h-full flex flex-col">
                <div className="text-sm text-secondary mb-2">
                  {t("scripts.finalResult")}
                </div>
                <div className="flex-1 overflow-auto rounded-lg border">
                  <img
                    src={`data:image/png;base64,${finalScreenshot}`}
                    alt="Final screenshot"
                    className="w-full h-auto"
                  />
                </div>
              </div>
            ) : (
              <div className="h-full flex items-center justify-center text-secondary">
                <div className="text-center">
                  <Play className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p>{t("scripts.waitingForBrowser")}</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ScriptExecutionView;
