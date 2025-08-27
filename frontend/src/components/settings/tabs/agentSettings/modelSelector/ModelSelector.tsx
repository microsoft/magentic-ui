import React from "react";
import { Select, Collapse, Flex } from "antd";
import {
  OpenAIModelConfigForm,
  AzureModelConfigForm,
  OllamaModelConfigForm,
} from "./modelConfigForms";
import { ModelConfig, ModelConfigFormProps } from "./modelConfigForms/types";

// Import the default configs from each form
import { DEFAULT_OPENAI } from "./modelConfigForms/OpenAIModelConfigForm";
import { DEFAULT_AZURE } from "./modelConfigForms/AzureModelConfigForm";
import { DEFAULT_OLLAMA } from "./modelConfigForms/OllamaModelConfigForm";

interface ModelSelectorProps {
  onChange: (m: ModelConfig) => void;
  value?: ModelConfig;
}

export const PROVIDERS = {
  openai: DEFAULT_OPENAI.provider,
  azure: DEFAULT_AZURE.provider,
  ollama: DEFAULT_OLLAMA.provider
}

// Map each model value to its config form, label, and initial config value
export const PROVIDER_FORM_MAP: Record<string, { label: string, defaultValue: ModelConfig, presets: Record<string, ModelConfig>, form: React.FC<ModelConfigFormProps> }> = {
  [DEFAULT_OPENAI.provider]: {
    label: "OpenAI",
    defaultValue: { ...DEFAULT_OPENAI },
    form: OpenAIModelConfigForm,
    presets: {
      "OpenRouter": {
        ...DEFAULT_OPENAI,
        config: {
          ...DEFAULT_OPENAI.config,
          base_url: "https://openrouter.ai/api/v1"
        }
      },
      "o3-2025-04-16": {
        ...DEFAULT_OPENAI,
        config: {
          ...DEFAULT_OPENAI.config,
          model: "o3-2025-04-16"
        }
      },
      "o3-mini-2025-01-31": {
        ...DEFAULT_OPENAI,
        config: {
          ...DEFAULT_OPENAI.config,
          model: "o3-mini-2025-01-31"
        }
      },
      "o4-mini-2025-04-16": {
        ...DEFAULT_OPENAI,
        config: {
          ...DEFAULT_OPENAI.config,
          model: "o4-mini-2025-04-16"
        }
      },
      "gpt-4.1-2025-04-14": {
        ...DEFAULT_OPENAI,
        config: {
          ...DEFAULT_OPENAI.config,
          model: "gpt-4.1-2025-04-14"
        }
      },
      "gpt-4.1-mini-2025-04-14": {
        ...DEFAULT_OPENAI,
        config: {
          ...DEFAULT_OPENAI.config,
          model: "gpt-4.1-mini-2025-04-14"
        }
      },
      "gpt-4.1-nano-2025-04-14": {
        ...DEFAULT_OPENAI,
        config: {
          ...DEFAULT_OPENAI.config,
          model: "gpt-4.1-nano-2025-04-14"
        }
      },
      "gpt-4o-2024-08-06": {
        ...DEFAULT_OPENAI,
        config: {
          ...DEFAULT_OPENAI.config,
          model: "gpt-4o-2024-08-06"
        }
      },
      "gpt-4o-mini-2024-07-18": {
        ...DEFAULT_OPENAI,
        config: {
          ...DEFAULT_OPENAI.config,
          model: "gpt-4o-mini-2024-07-18"
        }
      },
      "gpt-5-2025-08-07": {
        ...DEFAULT_OPENAI,
        config: {
          ...DEFAULT_OPENAI.config,
          model: "gpt-5-2025-08-07",
          model_info: {
            vision: true,
            function_calling: true,
            json_output: true,
            family: "unknown",
            structured_output: true,
            multiple_system_messages: false,
          }
        }
      },
      "gpt-5-mini-2025-08-07": {
        ...DEFAULT_OPENAI,
        config: {
          ...DEFAULT_OPENAI.config,
          model: "gpt-5-mini-2025-08-07",
          model_info: {
            vision: true,
            function_calling: true,
            json_output: true,
            family: "unknown",
            structured_output: true,
            multiple_system_messages: false,
          }
        }
      },
      "gpt-5-nano-2025-08-07": {
        ...DEFAULT_OPENAI,
        config: {
          ...DEFAULT_OPENAI.config,
          model: "gpt-5-nano-2025-08-07",
          model_info: {
            vision: true,
            function_calling: true,
            json_output: true,
            family: "unknown",
            structured_output: true,
            multiple_system_messages: false,
          }
        }
      }
    }
  },
  [DEFAULT_AZURE.provider]: {
    label: "Azure AI Foundry",
    defaultValue: { ...DEFAULT_AZURE },
    form: AzureModelConfigForm,
    presets: { [DEFAULT_AZURE.config.model]: { ...DEFAULT_AZURE } }
  },
  [DEFAULT_OLLAMA.provider]: {
    label: "Ollama",
    defaultValue: { ...DEFAULT_OLLAMA },
    form: OllamaModelConfigForm,
    presets: { [DEFAULT_OLLAMA.config.model]: { ...DEFAULT_OLLAMA } }
  },
};

const ModelSelector: React.FC<ModelSelectorProps> = ({ onChange, value }) => {
  const provider = value?.provider;
  const providerFormEntry = provider ? PROVIDER_FORM_MAP[provider] : undefined;
  const FormComponent = providerFormEntry?.form;

  const config = value?.config;
  let preset = undefined;
  if (providerFormEntry) {
    preset = Object.entries(providerFormEntry.presets)
      .find(([, presetConfig]) => comparePreset(presetConfig.config, config))
    ?.[0]
  }
  preset ??= value?.config?.model;

  // When dropdown changes, update both selectedModel and values
  const handleProviderChange = (provider: string) => {
    if (PROVIDER_FORM_MAP[provider]) {
      onChange(PROVIDER_FORM_MAP[provider].defaultValue);
    }
  };

  const handlePresetChange = (preset: string) => {
    if (providerFormEntry && providerFormEntry.presets[preset]) {
      onChange(providerFormEntry.presets[preset]);
    }
  };

  // --- Hide advanced toggles for OpenAI recognized models (except OpenRouter and GPT-5 models) ---
  let hideAdvancedToggles = false;
  if (
    provider === DEFAULT_OPENAI.provider &&
    providerFormEntry &&
    preset &&
    Object.keys(providerFormEntry.presets).includes(preset) &&
    preset !== 'OpenRouter' &&
    !preset.startsWith('gpt-5')
  ) {
    hideAdvancedToggles = true;
  }

  return (
    <Collapse>
      <Collapse.Panel
        key="1"
        header={
          <Flex gap="small" align="top" justify="start">
            <Select
              options={Object.entries(PROVIDER_FORM_MAP).map(([key, { label }]) => ({ value: key, label }))}
              placeholder="Select a Model provider."
              value={provider}
              onChange={handleProviderChange}
              onClick={(e) => e.stopPropagation()}
              popupMatchSelectWidth={false}
            />
            {
              providerFormEntry &&
              <Select
                options={Object.entries(providerFormEntry.presets).map(([key, { label }]) => ({ value: key, label }))}
                placeholder="Select a Preset"
                value={preset}
                onChange={handlePresetChange}
                onClick={(e) => e.stopPropagation()}
                popupMatchSelectWidth={false}
              />
            }
          </Flex>
        }
      >
        {FormComponent && (
          <FormComponent
            onChange={onChange}
            value={value}
            hideAdvancedToggles={hideAdvancedToggles}
          />
        )}
      </Collapse.Panel>
    </Collapse>
  );
};

// Returns true if every key in 'preset' exists in 'config' and the values are strictly equal (deep for objects)
function comparePreset(preset: any, config: any): boolean {
  if (typeof preset !== "object" || preset === null) return preset === config;
  if (typeof config !== "object" || config === null) return false;
  for (const key of Object.keys(preset)) {
    if (!(key in config)) return false;
    if (!comparePreset(preset[key], config[key])) return false;
  }
  return true;
}

export default ModelSelector;
