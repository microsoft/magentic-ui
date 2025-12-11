import React, { useState, useContext } from "react";
import { message, Spin, Tooltip, Modal } from "antd";
import { useTranslation } from "react-i18next";
import { appContext } from "../../../hooks/provider";
import { PlanAPI, ScriptAPI } from "../../views/api";
import { CodeBracketIcon, DocumentArrowDownIcon, BookmarkIcon, PlayIcon } from "@heroicons/react/24/outline";

interface ExportScriptButtonProps {
  sessionId: number;
  messageId: number;
  userId?: string;
  onSuccess?: (script: string) => void;
}

export const ExportScriptButton: React.FC<ExportScriptButtonProps> = ({
  sessionId,
  messageId,
  userId,
  onSuccess,
}) => {
  const [isExporting, setIsExporting] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [scriptContent, setScriptContent] = useState("");
  const [scriptTask, setScriptTask] = useState("");
  const [scriptData, setScriptData] = useState<any>(null);
  const [isSaved, setIsSaved] = useState(false);
  const [savedScriptId, setSavedScriptId] = useState<number | null>(null);
  const { t } = useTranslation();
  const { user, darkMode } = useContext(appContext);
  const planAPI = new PlanAPI();
  const scriptAPI = new ScriptAPI();

  const effectiveUserId = userId || user?.email;

  const handleExportScript = async () => {
    if (!sessionId || !effectiveUserId) {
      message.error(t("exportScriptButton.missingSessionOrUser"));
      return;
    }

    try {
      setIsExporting(true);
      message.loading({
        content: t("exportScriptButton.generatingScript"),
        key: "exportScript",
      });

      const response = await planAPI.exportScript(sessionId, effectiveUserId);

      if (response && response.status) {
        message.success({
          content: t("exportScriptButton.scriptGeneratedSuccessfully"),
          key: "exportScript",
          duration: 2,
        });

        setScriptContent(response.data.script);
        setScriptTask(response.data.task || "Playwright Script");
        setScriptData(response.data.script_data);
        setShowModal(true);

        if (onSuccess && response.data?.script) {
          onSuccess(response.data.script);
        }
      } else {
        throw new Error(response?.message || t("exportScriptButton.failedToGenerateScript"));
      }
    } catch (error) {
      console.error("Error generating script:", error);
      message.error({
        content: `${t("exportScriptButton.failedToGenerateScript")}: ${
          error instanceof Error ? error.message : t("exportScriptButton.unknownError")
        }`,
        key: "exportScript",
      });
    } finally {
      setIsExporting(false);
    }
  };

  const handleSaveToLibrary = async () => {
    if (!scriptData || !effectiveUserId) {
      message.error(t("exportScriptButton.missingSessionOrUser"));
      return;
    }

    try {
      message.loading({
        content: t("exportScriptButton.savingToLibrary"),
        key: "saveScript",
      });

      const savedScript = await scriptAPI.createScript({
        task: scriptData.task,
        start_url: scriptData.start_url,
        actions: scriptData.actions,
        viewport_width: scriptData.viewport_width,
        viewport_height: scriptData.viewport_height,
        session_id: sessionId,
      }, effectiveUserId);

      message.success({
        content: t("exportScriptButton.savedToLibrary"),
        key: "saveScript",
        duration: 2,
      });

      setIsSaved(true);
      setSavedScriptId(savedScript.id || null);
    } catch (error) {
      console.error("Error saving script:", error);
      message.error({
        content: `${t("exportScriptButton.failedToSave")}: ${
          error instanceof Error ? error.message : t("exportScriptButton.unknownError")
        }`,
        key: "saveScript",
      });
    }
  };

  const handleDownload = () => {
    const blob = new Blob([scriptContent], { type: "text/x-python" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `playwright_script_${sessionId}.py`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    message.success(t("exportScriptButton.scriptDownloaded"));
  };

  const handleCopyToClipboard = () => {
    navigator.clipboard.writeText(scriptContent);
    message.success(t("exportScriptButton.copiedToClipboard"));
  };

  // If exporting, show spinner
  if (isExporting) {
    return (
      <Tooltip title={t("exportScriptButton.generatingPlaywrightScript")}>
        <button
          disabled
          className={`inline-flex items-center px-3 py-1.5 rounded-md transition-colors ${
            darkMode === "dark"
              ? "bg-purple-800/30 text-purple-400 border border-purple-700"
              : "bg-purple-100 text-purple-800 border border-purple-200"
          } cursor-wait`}
        >
          <Spin size="small" className="mr-2" />
          <span className="text-sm font-medium">{t("exportScriptButton.generating")}</span>
        </button>
      </Tooltip>
    );
  }

  // Default state - ready to export
  return (
    <>
      <Tooltip title={t("exportScriptButton.exportPlaywrightScript")}>
        <button
          onClick={handleExportScript}
          disabled={!sessionId || !effectiveUserId}
          className={`inline-flex items-center px-3 py-1.5 rounded-md transition-colors ${
            darkMode === "dark"
              ? "bg-purple-700/20 text-purple-400 border border-purple-400/50 hover:bg-purple-700/30 hover:border-purple-700"
              : "bg-purple-50 text-purple-800 border border-purple-200 hover:bg-purple-100 hover:border-purple-300"
          } ${
            !sessionId || !effectiveUserId
              ? "opacity-50 cursor-not-allowed"
              : "cursor-pointer"
          }`}
        >
          <CodeBracketIcon
            className={`h-4 w-4 mr-1.5 ${
              darkMode === "dark" ? "text-purple-400" : "text-purple-800"
            }`}
          />
          <span className="text-sm font-medium">{t("exportScriptButton.exportScript")}</span>
        </button>
      </Tooltip>

      <Modal
        title={
          <div className="flex items-center gap-2">
            <CodeBracketIcon className="h-5 w-5" />
            <span>{scriptTask}</span>
          </div>
        }
        open={showModal}
        onCancel={() => setShowModal(false)}
        width={800}
        footer={[
          <button
            key="copy"
            onClick={handleCopyToClipboard}
            className={`px-4 py-2 rounded-md mr-2 ${
              darkMode === "dark"
                ? "bg-gray-700 text-gray-200 hover:bg-gray-600"
                : "bg-gray-200 text-gray-800 hover:bg-gray-300"
            }`}
          >
            {t("exportScriptButton.copyToClipboard")}
          </button>,
          <button
            key="save"
            onClick={handleSaveToLibrary}
            disabled={isSaved}
            className={`px-4 py-2 rounded-md mr-2 ${
              isSaved
                ? darkMode === "dark"
                  ? "bg-green-800/30 text-green-400 border border-green-700 cursor-default"
                  : "bg-green-100 text-green-700 border border-green-200 cursor-default"
                : darkMode === "dark"
                  ? "bg-blue-600 text-white hover:bg-blue-500"
                  : "bg-blue-600 text-white hover:bg-blue-700"
            }`}
          >
            <BookmarkIcon className="h-4 w-4 inline mr-1" />
            {isSaved ? t("exportScriptButton.savedToLibrary") : t("exportScriptButton.saveToLibrary")}
          </button>,
          <button
            key="download"
            onClick={handleDownload}
            className={`px-4 py-2 rounded-md ${
              darkMode === "dark"
                ? "bg-purple-600 text-white hover:bg-purple-500"
                : "bg-purple-600 text-white hover:bg-purple-700"
            }`}
          >
            <DocumentArrowDownIcon className="h-4 w-4 inline mr-1" />
            {t("exportScriptButton.downloadScript")}
          </button>,
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
            {scriptContent}
          </pre>
        </div>
      </Modal>
    </>
  );
};

export default ExportScriptButton;
