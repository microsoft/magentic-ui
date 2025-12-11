import React, { useState, useContext } from "react";
import { Card, Modal, Tooltip, Button, message } from "antd";
import { PlayCircle, Clock, Trash2, Download, Code, Globe } from "lucide-react";
import { useTranslation } from "react-i18next";
import { appContext } from "../../../hooks/provider";
import { ScriptAPI } from "../../views/api";
import { getRelativeTimeString } from "../../views/atoms";

export interface IScript {
  id?: number;
  user_id?: string;
  task?: string;
  start_url?: string;
  actions?: Array<{
    action_type: string;
    selector?: string;
    value?: string;
    description: string;
    wait_after?: number;
  }>;
  viewport_width?: number;
  viewport_height?: number;
  session_id?: number;
  run_count?: number;
  created_at?: string;
  updated_at?: string;
}

interface ScriptCardProps {
  script: IScript;
  onRunScript?: (script: IScript) => void;
  onDeleteScript?: (scriptId: number) => void;
}

const ScriptCard: React.FC<ScriptCardProps> = ({
  script,
  onRunScript,
  onDeleteScript,
}) => {
  const { t } = useTranslation();
  const { darkMode } = useContext(appContext);
  const [isHovering, setIsHovering] = useState(false);
  const [showCodeModal, setShowCodeModal] = useState(false);
  const [pythonCode, setPythonCode] = useState<string>("");
  const [isLoadingCode, setIsLoadingCode] = useState(false);
  const scriptAPI = new ScriptAPI();

  const handleDelete = async (e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();

    if (!script.id || !script.user_id) {
      console.error("Missing required IDs");
      return;
    }

    if (window.confirm(t("scripts.confirmDelete"))) {
      try {
        await scriptAPI.deleteScript(script.id, script.user_id);
        if (onDeleteScript) {
          onDeleteScript(script.id);
        }
      } catch (error) {
        console.error("Failed to delete script:", error);
        message.error(t("scripts.errorOccurred"));
      }
    }
  };

  const handleDownloadPython = async (e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();

    if (!script.id || !script.user_id) {
      return;
    }

    try {
      const response = await scriptAPI.getScriptAsPython(script.id, script.user_id);
      const blob = new Blob([response.python_code], { type: "text/x-python" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = response.filename || `script_${script.id}.py`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      message.success(t("exportScriptButton.scriptDownloaded"));
    } catch (error) {
      console.error("Failed to download Python script:", error);
      message.error(t("scripts.errorOccurred"));
    }
  };

  const handleShowCode = async () => {
    if (!script.id || !script.user_id) {
      return;
    }

    try {
      setIsLoadingCode(true);
      const response = await scriptAPI.getScriptAsPython(script.id, script.user_id);
      setPythonCode(response.python_code);
      setShowCodeModal(true);
    } catch (error) {
      console.error("Failed to load Python code:", error);
      message.error(t("scripts.errorOccurred"));
    } finally {
      setIsLoadingCode(false);
    }
  };

  const actionsCount = script.actions?.length || 0;

  return (
    <>
      <Card
        key={script.id}
        title={
          <div className="flex justify-between items-center">
            <span
              className="truncate max-w-[80%]"
              title={script.task || "Untitled Script"}
            >
              {script.task || "Untitled Script"}
            </span>
            {isHovering && (
              <div className="flex items-center ml-2">
                <Tooltip title={t("scripts.downloadPython")}>
                  <button
                    className="bg-transparent border-none cursor-pointer mr-2"
                    onClick={handleDownloadPython}
                    aria-label={t("scripts.downloadPython")}
                  >
                    <Download className="h-5 w-5 transition-colors" />
                  </button>
                </Tooltip>
                <Tooltip title={t("scripts.deleteScript")}>
                  <button
                    className="bg-transparent border-none cursor-pointer"
                    onClick={handleDelete}
                    aria-label={t("scripts.deleteScript")}
                  >
                    <Trash2 className="h-5 w-5 transition-colors" />
                  </button>
                </Tooltip>
              </div>
            )}
          </div>
        }
        className="shadow-md hover:shadow-lg transition-shadow duration-200 flex flex-col"
        onMouseEnter={() => setIsHovering(true)}
        onMouseLeave={() => setIsHovering(false)}
        actions={[
          <div key="run" className="flex items-center justify-center h-full">
            <Tooltip title={t("scripts.runScript")}>
              <Button
                type="text"
                className="cursor-pointer flex items-center justify-center font-semibold transition-colors"
                onClick={() => {
                  if (onRunScript) onRunScript(script);
                }}
              >
                <PlayCircle className="h-4 w-4 mr-1" />
                {t("scripts.runScript")}
              </Button>
            </Tooltip>
          </div>,
          <div key="code" className="flex items-center justify-center h-full">
            <Tooltip title={t("exportScriptButton.exportScript")}>
              <Button
                type="text"
                className="cursor-pointer flex items-center justify-center font-semibold transition-colors"
                onClick={handleShowCode}
                loading={isLoadingCode}
              >
                <Code className="h-4 w-4 mr-1" />
                {t("exportScriptButton.exportScript")}
              </Button>
            </Tooltip>
          </div>,
        ]}
      >
        <div className="flex flex-col flex-grow justify-between">
          <div>
            <div className="mb-2 flex items-center text-sm">
              <Globe className="h-4 w-4 mr-1" />
              <span className="truncate" title={script.start_url}>
                {script.start_url || "No URL"}
              </span>
            </div>

            <div className="mb-4">
              <p className="text-sm">{t("scripts.actionsCount", { count: actionsCount })}</p>
            </div>

            <div className="space-y-2 min-h-[60px]">
              {script.actions?.slice(0, 3).map((action, idx) => (
                <div
                  key={idx}
                  className="text-xs border-l-2 border-gray-200 pl-2 truncate"
                  title={action.description}
                >
                  <span className="font-medium">{action.action_type}:</span>{" "}
                  {action.description || action.selector || action.value}
                </div>
              ))}
              {actionsCount > 3 && (
                <div className="text-xs text-secondary">
                  +{actionsCount - 3} more actions
                </div>
              )}
            </div>
          </div>

          <div className="mt-4 text-xs flex items-center justify-between">
            <div className="flex items-center">
              {script.created_at && (
                <>
                  <Clock className="h-3 w-3 mr-1" />
                  {getRelativeTimeString(script.created_at)}
                </>
              )}
            </div>
            {script.run_count !== undefined && script.run_count > 0 && (
              <div className="text-secondary">
                {t("scripts.runCount")}: {script.run_count}
              </div>
            )}
          </div>
        </div>
      </Card>

      <Modal
        title={
          <div className="flex items-center gap-2">
            <Code className="h-5 w-5" />
            <span>{script.task || "Script"}</span>
          </div>
        }
        open={showCodeModal}
        onCancel={() => setShowCodeModal(false)}
        width={800}
        footer={[
          <Button key="close" onClick={() => setShowCodeModal(false)}>
            {t("common.close")}
          </Button>,
          <Button
            key="download"
            type="primary"
            onClick={handleDownloadPython}
          >
            <Download className="h-4 w-4 inline mr-1" />
            {t("scripts.downloadPython")}
          </Button>,
        ]}
      >
        <div className="max-h-[60vh] overflow-auto">
          <pre
            className={`p-4 rounded-md text-sm font-mono ${
              darkMode === "dark"
                ? "bg-gray-900 text-gray-100"
                : "bg-gray-100 text-gray-900"
            }`}
          >
            {pythonCode}
          </pre>
        </div>
      </Modal>
    </>
  );
};

export default ScriptCard;
