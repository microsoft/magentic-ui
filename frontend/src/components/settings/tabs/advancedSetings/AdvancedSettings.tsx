import React, { useEffect } from "react";
import MonacoEditor from "@monaco-editor/react";
import yaml from "js-yaml";
import { Button, Tooltip, Flex, Typography, Alert } from "antd";
import { message } from "antd";
import { UploadOutlined } from "@ant-design/icons";
import { validateAll } from "../../validation";
import { useTranslation } from "react-i18next";

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
  const { t } = useTranslation();
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
          throw new Error(t('advancedSettings.unsupportedFileType'));
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
          message.error(t('advancedSettings.failedToParseFile'));
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
      <Typography.Text strong>{t('advancedSettings.title')}</Typography.Text>
      <Typography.Text type="secondary">
        {t('advancedSettings.advancedConfiguration')}
      </Typography.Text>
      <Flex gap="large" justify="start" align="center">
        <Button
          icon={<UploadOutlined />}
          onClick={() => fileInputRef.current?.click()}
        >
          {t('advancedSettings.upload')}
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
          {t('advancedSettings.applyChanges')}
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
          {t('advancedSettings.discardChanges')}
        </Button>
        {errors.length > 0 && (
          <Tooltip
            title={
              <div>
                {errors.map((err, idx) => (
                  <div key={idx} style={{ whiteSpace: 'pre-wrap', color: 'white' }}>{err}</div>
                ))}
              </div>
            }
            color="red"
            placement="right"
          >
            <span style={{ display: 'flex', alignItems: 'center', color: 'red', cursor: 'pointer' }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginLeft: 4 }}>
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <circle cx="12" cy="16" r="1" />
              </svg>
              <span style={{ marginLeft: 4, fontSize: 12 }}>
                {t('advancedSettings.errorCount', { count: errors.length })}
              </span>
            </span>
          </Tooltip>
        )}
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
