import { ModelConfig } from "../tabs/agentSettings/modelSelector/modelConfigForms/types";
import { DEFAULT_OPENAI } from "../tabs/agentSettings/modelSelector/modelConfigForms/OpenAIModelConfigForm";
import { PROVIDER_FORM_MAP } from "../tabs/agentSettings/modelSelector/ModelSelector";

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

export interface ConfigWithModels {
  default_model?: ModelConfig;
  model_client_configs?: Record<string, ModelConfig>;
}

export const initializeDefaultModel = (config: ConfigWithModels): ModelConfig | undefined => {
  // If we have a stored default_model, use it
  if (config.default_model) {
    return config.default_model;
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
