import React, { useEffect, useState } from "react";
import { Tooltip, Typography, Flex, Collapse, Switch, Alert } from "antd";
import ModelSelector, {
  PROVIDER_FORM_MAP,
} from "./modelSelector/ModelSelector";
import { DEFAULT_OPENAI } from "./modelSelector/modelConfigForms/OpenAIModelConfigForm";
import { SettingsTabProps } from "../../types";
import { ModelConfig } from "./modelSelector/modelConfigForms/types";
import MCPAgentsSettings from "./mcpAgentsSettings/MCPAgentsSettings";
import { SwitchChangeEventHandler } from "antd/es/switch";
import { settingsAPI } from "../../../views/api";
import { Prism, SyntaxHighlighterProps } from "react-syntax-highlighter";
import { tomorrow } from "react-syntax-highlighter/dist/esm/styles/prism";

const SyntaxHighlighter = Prism as any as React.FC<SyntaxHighlighterProps>;

export const MODEL_CLIENT_CONFIGS = {
  orchestrator: {
    value: "orchestrator",
    label: "Orchestrator",
    defaultValue: DEFAULT_OPENAI,
  },
  web_surfer: {
    value: "web_surfer",
    label: "Web Surfer",
    defaultValue: DEFAULT_OPENAI,
  },
  coder: { value: "coder", label: "Coder", defaultValue: DEFAULT_OPENAI },
  file_surfer: {
    value: "file_surfer",
    label: "File Surfer",
    defaultValue: DEFAULT_OPENAI,
  },
  action_guard: {
    value: "action_guard",
    label: "Action Guard",
    defaultValue:
      PROVIDER_FORM_MAP[DEFAULT_OPENAI.provider].presets[
      "gpt-4.1-nano-2025-04-14"
      ],
  },
};

type ModelClientKey = keyof typeof MODEL_CLIENT_CONFIGS;

const AgentSettingsTab: React.FC<SettingsTabProps> = ({
  config,
  handleUpdateConfig,
}) => {
  const [advanced, setAdvanced] = useState<boolean>(
    (config as any).advanced_agent_settings ?? false
  );
  const [hasConfigFile, setHasConfigFile] = useState<boolean>(false);
  const [configFilePath, setConfigFilePath] = useState<string | null>(null);
  const [configContent, setConfigContent] = useState<any>(null);

  // Initialize defaultModel from config or detect common model
  const initializeDefaultModel = () => {
    // If we have a stored default_model, use it
    if ((config as any).default_model) {
      return (config as any).default_model;
    }

    // Otherwise, try to detect if all agents use the same model
    const configs = config.model_client_configs;
    if (configs) {
      const firstConfig = configs[Object.keys(MODEL_CLIENT_CONFIGS)[0]];
      const allSame = Object.values(MODEL_CLIENT_CONFIGS).every(({ value }) => {
        const agentConfig = configs[value];
        return (
          agentConfig &&
          JSON.stringify(agentConfig) === JSON.stringify(firstConfig)
        );
      });

      if (allSame && firstConfig) {
        return firstConfig;
      }
    }

    return undefined;
  };

  const [defaultModel, setDefaultModel] = useState<ModelConfig | undefined>(
    initializeDefaultModel()
  );

  // Handler for individual model config changes
  const handleEachModelConfigChange = (key: ModelClientKey, value: any) => {
    handleUpdateConfig({
      model_client_configs: {
        ...config.model_client_configs,
        [key]: value,
      },
    });
  };

  useEffect(() => {
    if (defaultModel) {
      // Set all model_client_configs to defaultModel
      const model_client_configs = Object.keys(MODEL_CLIENT_CONFIGS).reduce(
        (prev, key) => {
          prev[key] = defaultModel;
          return prev;
        },
        {} as Record<string, ModelConfig>
      );

      handleUpdateConfig({
        model_client_configs: model_client_configs,
        default_model: defaultModel,
      });
    }
  }, [defaultModel]);

  // Fetch config info on component mount
  useEffect(() => {
    const fetchConfigInfo = async () => {
      try {
        const configInfo = await settingsAPI.getConfigInfo();
        setHasConfigFile(configInfo.has_config_file);
        setConfigFilePath(configInfo.config_file_path);
        setConfigContent(configInfo.config_content);
      } catch (error) {
        console.error("Failed to fetch config info:", error);
      }
    };
    fetchConfigInfo();
  }, []);

  // Handle advanced toggle changes
  const handleAdvancedToggle = (value: boolean) => {
    setAdvanced(value);
    handleUpdateConfig({
      advanced_agent_settings: value,
    });
  };

  const header = advanced
    ? "Set the LLM for each agent."
    : "Set the LLM for all agents.";

  return (
    <Flex vertical gap="small" justify="start">
      {hasConfigFile && (
        <Alert
          message="LLM Configuration Override"
          description={
            <div>
              <Typography.Text>
                Magentic-UI was started with an LLM config file ({configFilePath}).
                LLM configurations set here will be ignored as they are overridden by the config file.
              </Typography.Text>
              {configContent && (
                <Collapse
                  ghost
                  size="small"
                  style={{ marginTop: 8 }}
                  items={[{
                    key: 'config',
                    label: 'Show Config Content',
                    children: (
                      <div style={{ maxHeight: '300px', overflow: 'auto' }}>
                        <SyntaxHighlighter
                          language="json"
                          style={tomorrow}
                          customStyle={{
                            fontSize: '12px',
                            margin: 0,
                          }}
                        >
                          {JSON.stringify(configContent, null, 2)}
                        </SyntaxHighlighter>
                      </div>
                    )
                  }]}
                />
              )}
            </div>
          }
          type="warning"
          showIcon
          closable
        />
      )}
      <Flex gap="small" justify="space-between">
        <Flex gap="small" justify="start" align="center">
          <Typography.Text>{header}</Typography.Text>
        </Flex>
        <Tooltip title="Toggle between Basic and Advanced settings.">
          <Flex gap="small">
            <Typography.Text>Advanced</Typography.Text>
            <Switch value={advanced} onChange={handleAdvancedToggle} />
          </Flex>
        </Tooltip>
      </Flex>

      {/* Simple Config */}
      {!advanced && (
        <Flex>
          <ModelSelector onChange={setDefaultModel} value={defaultModel} />
        </Flex>
      )}

      {/* Advanced Config */}
      {advanced && (
        <>
          {Object.values(MODEL_CLIENT_CONFIGS).map(
            ({ value, label, defaultValue }) => (
              <Flex key={value} vertical gap="small">
                <Typography.Text>{label}</Typography.Text>
                <ModelSelector
                  onChange={(modelValue: any) =>
                    handleEachModelConfigChange(
                      value as ModelClientKey,
                      modelValue
                    )
                  }
                  value={
                    config.model_client_configs?.[value as ModelClientKey] ??
                    defaultValue
                  }
                />
              </Flex>
            )
          )}
        </>
      )}

      <Collapse>
        <Collapse.Panel key={1} header="Custom Agents">
          <MCPAgentsSettings
            config={config}
            defaultModel={defaultModel}
            advanced={advanced}
            handleUpdateConfig={handleUpdateConfig}
          />
        </Collapse.Panel>
      </Collapse>
    </Flex>
  );
};

export default AgentSettingsTab;
