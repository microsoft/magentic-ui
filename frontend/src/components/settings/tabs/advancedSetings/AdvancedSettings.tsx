import React, { useEffect } from "react";
import MonacoEditor from "@monaco-editor/react";
import yaml from "js-yaml";
import { Button, Flex, Alert } from "antd";
import { message } from "antd";
import { UploadOutlined } from "@ant-design/icons";
import { validateAll } from "../../validation";

interface AdvancedConfigEditorProps {
  config: any;
  darkMode?: string;
  handleUpdateConfig: (changes: any) => void;
}

const AdvancedConfigEditor: React.FC<AdvancedConfigEditorProps> = ({
  config,
  darkMode,
  handleUpdateConfig,
}) => {
  const [errors, setErrors] = React.useState<string[]>([]);
  const [editorValue, setEditorValue] = React.useState(
    config ? yaml.dump(config) : ""
  );
  const [hasUnsavedChanges, setHasUnsavedChanges] = React.useState(false);
  const fileInputRef = React.useRef<HTMLInputElement>(null);
  const validationTimeoutRef = React.useRef<NodeJS.Timeout>();

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      const text = e.target?.result as string;
      let parsed;
      try {
        if (file.name.endsWith(".json")) {
          parsed = JSON.parse(text);
        } else if (file.name.endsWith(".yaml") || file.name.endsWith(".yml")) {
          parsed = yaml.load(text);
        } else {
          throw new Error("Unsupported file type");
        }
        if (parsed && typeof parsed === "object") {
          const errors = validateAll(parsed);
          if (errors.length > 0) {
            message.error(errors.join("\n"));
            return;
          }
          setEditorValue(yaml.dump(parsed));
        }
      } catch (e) {
        message.error("Failed to parse uploaded file.");
      }
    };
    reader.readAsText(file);
    // Reset input so same file can be uploaded again if needed
    event.target.value = "";
  };

  useEffect(() => {
    const yamlConfig = config ? yaml.dump(config) : "";
    if (yamlConfig !== editorValue) {
      setEditorValue(yamlConfig);
      setHasUnsavedChanges(false);
    }
  }, [config]);

  return (
    <Flex vertical gap="large">
      <Flex gap="large" justify="start" align="center">
        <Button
          icon={<UploadOutlined />}
          onClick={() => fileInputRef.current?.click()}
        >
          Upload
          <input
            ref={fileInputRef}
            type="file"
            accept=".json,.yaml,.yml"
            style={{ display: "none" }}
            onChange={handleFileUpload}
          />
        </Button>
        <Button
          type="primary"
          disabled={errors.length > 0 || !hasUnsavedChanges}
          onClick={() => {
            try {
              const parsed = yaml.load(editorValue);
              const validationErrors = validateAll(parsed);
              if (validationErrors.length === 0) {
                handleUpdateConfig(parsed);
                setHasUnsavedChanges(false);
                message.success("Settings updated successfully");
              }
            } catch (e) {
              message.error("Invalid YAML format");
            }
          }}
        >
          Apply Changes
        </Button>
        <Button
          danger
          disabled={!hasUnsavedChanges}
          onClick={() => {
            setEditorValue(config ? yaml.dump(config) : "");
            setErrors([]);
            setHasUnsavedChanges(false);
          }}
        >
          Discard Changes
        </Button>
      </Flex>

      <div
        style={{
          padding: 2,
          border: errors.length > 0 ? "2px solid red" : "none",
          borderRadius: errors.length > 0 ? 6 : undefined,
        }}
      >
        <MonacoEditor
          theme={darkMode === "dark" ? "vs-dark" : "light"}
          value={editorValue}
          onChange={(value) => {
            setEditorValue(value || "");
            setHasUnsavedChanges(true);

            // Clear existing timeout
            if (validationTimeoutRef.current) {
              clearTimeout(validationTimeoutRef.current);
            }

            // Set new timeout to validate after user stops typing
            validationTimeoutRef.current = setTimeout(() => {
              try {
                const parsed = yaml.load(value || "");
                const validationErrors = validateAll(parsed);
                setErrors(validationErrors);
              } catch (e) {
                setErrors([`${e}`]);
              }
            }, 500); // 0.5 second delay for validation
          }}
          language="yaml"
          options={{
            fontFamily: "monospace",
            minimap: { enabled: false },
            wordWrap: "on",
            scrollBeyondLastLine: false,
          }}
          height="500px"
        />
      </div>

      {errors.length > 0 && (
        <Alert
          message="Configuration Errors"
          description={
            <div>
              {errors.map((err, idx) => (
                <div key={idx} style={{ marginBottom: 4 }}>
                  {err}
                </div>
              ))}
            </div>
          }
          type="error"
          showIcon
          closable
          onClose={() => setErrors([])}
        />
      )}
    </Flex>
  );
};

export default AdvancedConfigEditor;
