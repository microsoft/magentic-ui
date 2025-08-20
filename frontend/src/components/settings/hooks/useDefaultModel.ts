import { useState, useEffect } from "react";
import { ModelConfig } from "../tabs/agentSettings/modelSelector/modelConfigForms/types";
import { initializeDefaultModel } from "../utils/modelUtils";
import { useSettingsStore } from "../../store";
import { settingsAPI } from "../../views/api";

/**
 * Hook to get the default model, prioritizing config file over UI settings
 *
 * When --config is provided and contains complete model client configurations,
 * it uses orchestrator_client as the default model (same logic as teammanager.py).
 * Otherwise, it falls back to UI settings.
 */
export const useDefaultModel = () => {
  const { config } = useSettingsStore();
  const [defaultModel, setDefaultModel] = useState<ModelConfig | undefined>(
    initializeDefaultModel(config)
  );

  useEffect(() => {
    const fetchConfigInfo = async () => {
      try {
        const configInfo = await settingsAPI.getConfigInfo();

        // Check if config file has complete model client configurations
        if (configInfo?.has_config_file && configInfo?.config_content) {
          const configContent = configInfo.config_content;

          const hasCompleteConfig =
            configContent.orchestrator_client &&
            configContent.web_surfer_client &&
            configContent.coder_client &&
            configContent.file_surfer_client &&
            configContent.action_guard_client;

          if (hasCompleteConfig) {
            setDefaultModel(configContent.orchestrator_client);
            return;
          }
        }
      } catch (error) {
        console.warn("Failed to fetch config file info:", error);
      }
    };

    fetchConfigInfo();
  }, []);

  return { defaultModel, setDefaultModel };
};
