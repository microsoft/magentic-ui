import React from "react";
import { Tooltip, Space, Row, Col, Typography } from "antd";
import { InfoCircleOutlined } from "@ant-design/icons";
import ModelSelector, { PROVIDER_FORM_MAP } from "./ModelSelector";
import { DEFAULT_OPENAI } from "./ModelConfigForms/OpenAIModelConfigForm";

export const MODEL_CLIENT_KEYS = [
  "orchestrator",
  "web_surfer",
  "coder",
  "file_surfer",
  "action_guard"
];

const MODEL_CLIENT_CONFIGS = [
  { value: "orchestrator", label: "Orchestrator", defaultValue: DEFAULT_OPENAI },
  { value: "web_surfer", label: "Web Surfer", defaultValue: DEFAULT_OPENAI },
  { value: "coder", label: "Coder", defaultValue: DEFAULT_OPENAI },
  { value: "file_surfer", label: "File Surfer", defaultValue: DEFAULT_OPENAI },
  { value: "action_guard", label: "Action Guard", defaultValue: PROVIDER_FORM_MAP[DEFAULT_OPENAI.provider].presets["gpt-4.1-nano-2025-04-14"] },
];

interface ModelConfigSettingsProps {
  config: any;
  handleUpdateConfig: (changes: any) => void;
}

const ModelConfigSettings: React.FC<ModelConfigSettingsProps> = ({
  config,
  handleUpdateConfig,
}) => {
  // Handler for individual model config changes
  const handleSingleModelConfigChange = (key: string, value: any) => {
    handleUpdateConfig({
      model_client_configs: {
        ...config.model_client_configs,
        [key]: value,
      },
    });
  };

  return (
    <Space direction="vertical" size={16} style={{ width: "100%", height: "100%", flexGrow: 1, display: 'flex', flexDirection: 'column' }}>
      <Space direction="vertical" size={8} style={{ width: "100%" }}>
        <Row align="middle" justify="space-between" style={{ width: "100%" }}>
          <Col>
            <Space align="center" size={8}>
              Model Configuration
              <Tooltip
                title={
                  <>
                    <p>Changes require a new session to take effect.</p>
                  </>
                }
              >
                <InfoCircleOutlined className="text-secondary hover:text-primary cursor-help" />
              </Tooltip>
            </Space>
          </Col>
        </Row>
        <Row align="middle" gutter={8}>
          <Col flex="auto">
            <Space direction="vertical" size={4} style={{ width: "100%" }}>
              <Space align="center" size={8}>
                <Typography.Text type="secondary" className="text-sm">Select LLM for Each Client</Typography.Text>
                <Tooltip title="Update the model configuration for each agent client (orchestrator, coder, web surfer, file surfer, action guard)">
                  <InfoCircleOutlined className="text-primary hover:text-primary cursor-help" />
                </Tooltip>
              </Space>
              {MODEL_CLIENT_CONFIGS.map(({ value, label, defaultValue }) => (
                <div key={value} style={{ marginBottom: 8 }}>
                  <Typography.Text style={{ marginRight: 8, fontWeight: 500 }}>{label}</Typography.Text>
                  <ModelSelector
                    onChange={(modelValue: any) => handleSingleModelConfigChange(value, modelValue)}
                    value={config.model_client_configs?.[value] ?? defaultValue}
                  />
                </div>
              ))}
            </Space>
          </Col>
        </Row>
      </Space>
    </Space>
  );
};

export default ModelConfigSettings;
