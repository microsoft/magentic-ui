import React, { useCallback } from "react";
import { Input, message } from "antd";
import { useTranslation } from "react-i18next";

const { TextArea } = Input;

interface JsonFormProps {
  value: string;
  onValueChanged: (value: string) => void;
}

const JsonForm: React.FC<JsonFormProps> = ({ value, onValueChanged }) => {
  const { t } = useTranslation();
  const validateAndParseJson = (content: string) => {
    try {
      const parsed = JSON.parse(content);
      if (!parsed.server_name) {
        throw new Error(t("mcpConfig.missingServerName"));
      }

      return parsed;
    } catch (error) {
      throw new Error(t("mcpConfig.invalidJsonConfig", { error: error instanceof Error ? error.message : t("common.error") }));
    }
  };

  const handleFileRead = useCallback((file: File) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const content = e.target?.result as string;
        const parsed = validateAndParseJson(content);
        // Format the JSON nicely for editing
        const formattedJson = JSON.stringify(parsed, null, 2);
        // Update the value through the controlled state
        onValueChanged(formattedJson);
        message.success(t("mcpConfig.jsonLoaded"));
      } catch (error) {
        console.error("File read error:", error);
        message.error(error instanceof Error ? error.message : t("mcpConfig.jsonParseFailed"));
      }
    };
    reader.readAsText(file);
  }, [onValueChanged]);

  const handleTextareaDrop = useCallback((e: React.DragEvent<HTMLTextAreaElement>) => {
    e.preventDefault();
    e.stopPropagation();

    const files = e.dataTransfer.files;
    if (files.length > 0) {
      const file = files[0];
      if (file.type === 'application/json' || file.name.endsWith('.json')) {
        handleFileRead(file);
      } else {
        message.error(t("mcpConfig.invalidJsonFile"));
      }
    }
  }, [handleFileRead]);

  const handleTextareaDragOver = useCallback((e: React.DragEvent<HTMLTextAreaElement>) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  return (
    <div className="space-y-2">
      {/* JSON Editor */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          {t("mcpConfig.jsonConfiguration")}
        </label>
        <TextArea
          rows={6}
          value={value}
          placeholder={`{
            "server_name": "my-server",
            "server_params": {
              "type": "StdioServerParams",
              "command": "npx",
              "args": ["@modelcontextprotocol/server-filesystem"],
              "read_timeout_seconds": 5
            }
          }`}
          onChange={(e) => onValueChanged(e.target.value)}
          onDrop={handleTextareaDrop}
          onDragOver={handleTextareaDragOver}
          className="cursor-text"
        />
        <p className="text-sm text-gray-500 mt-1">
          {t("mcpConfig.jsonDragDropHint")}
        </p>
      </div>
    </div>
  );
};

export default JsonForm;
