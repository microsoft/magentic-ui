import React, { useEffect } from "react";
import MonacoEditor from "@monaco-editor/react";
import yaml from "js-yaml";
import { Button, Tooltip, Flex } from "antd";
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
  const [editorValue, setEditorValue] = React.useState(config ? yaml.dump(config) : "");
  const fileInputRef = React.useRef<HTMLInputElement>(null);

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
      setEditorValue(yamlConfig)
    }
  }, [config])

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
            style={{ display: 'none' }}
            onChange={handleFileUpload}
          />
        </Button>
        <Button
          danger
          onClick={() => {
            setEditorValue(config ? yaml.dump(config) : "");
            setErrors(validateAll(config));
          }}
        >
          Discard Changes
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
                {errors.length} error{errors.length > 1 ? 's' : ''}
              </span>
            </span>
          </Tooltip>
        )}
      </Flex>
      <div style={{
        padding: 2,
        border: errors.length > 0 ? "2px solid red" : "none",
        borderRadius: errors.length > 0 ? 6 : undefined,
      }}>
        <MonacoEditor
          theme={darkMode === "dark" ? "vs-dark" : "light" }
          value={editorValue}
          onChange={value => {
            setEditorValue(value || "")
            try {
              const parsed = yaml.load(value || "");
              const errors = validateAll(parsed);
              setErrors(errors); // Always update errors, even if empty
              if (errors.length === 0) {
                handleUpdateConfig(parsed)
              }
            } catch (e) {
              setErrors([`${e}`])
            }
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
    </Flex>
  );
};

export default AdvancedConfigEditor;
