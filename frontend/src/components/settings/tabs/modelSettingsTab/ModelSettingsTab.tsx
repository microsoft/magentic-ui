import React from "react";
import { Tooltip, Typography, Flex } from "antd";
import { InfoCircleOutlined } from "@ant-design/icons";
import ModelSelector, { PROVIDER_FORM_MAP } from "./modelSelector/ModelSelector";
import { DEFAULT_OPENAI } from "./modelSelector/modelConfigForms/OpenAIModelConfigForm";
import { SettingsTabProps } from "../../types";

export const MODEL_CLIENT_CONFIGS = {
  "orchestrator": { value: "orchestrator", label: "Orchestrator", defaultValue: DEFAULT_OPENAI },
  "web_surfer": { value: "web_surfer", label: "Web Surfer", defaultValue: DEFAULT_OPENAI },
  "coder": { value: "coder", label: "Coder", defaultValue: DEFAULT_OPENAI },
  "file_surfer": { value: "file_surfer", label: "File Surfer", defaultValue: DEFAULT_OPENAI },
  "action_guard": { value: "action_guard", label: "Action Guard", defaultValue: PROVIDER_FORM_MAP[DEFAULT_OPENAI.provider].presets["gpt-4.1-nano-2025-04-14"] },
};

type ModelClientKey = keyof typeof MODEL_CLIENT_CONFIGS;

const ModelSettingsTab: React.FC<SettingsTabProps> = ({
  config,
  handleUpdateConfig,
}) => {
  // Handler for individual model config changes
  const handleSingleModelConfigChange = (key: ModelClientKey, value: any) => {
    handleUpdateConfig({
      model_client_configs: {
        ...config.model_client_configs,
        [key]: value,
      },
    });
  };

  return (
    <Flex vertical gap="large" justify="start">
      <Flex gap="small" justify="start" align="center">
        <Typography.Text>Select LLM for Each Client</Typography.Text>
        <Tooltip title="Update the model configuration for each agent client (orchestrator, coder, web surfer, file surfer, action guard)">
          <InfoCircleOutlined className="text-secondary hover:text-primary cursor-help" />
        </Tooltip>
      </Flex>
      {Object.values(MODEL_CLIENT_CONFIGS).map(({ value, label, defaultValue }) => (
        <Flex key={value} vertical gap="small">
          <Typography.Text>{label}</Typography.Text>
          <ModelSelector
            onChange={(modelValue: any) => handleSingleModelConfigChange(value as ModelClientKey, modelValue)}
            value={config.model_client_configs?.[value as ModelClientKey] ?? defaultValue}
          />
        </Flex>
      ))}
    </Flex>
  );
};

export default ModelSettingsTab;
