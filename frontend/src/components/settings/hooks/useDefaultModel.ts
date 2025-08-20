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
  const { config: uiSettings } = useSettingsStore();
  const [defaultModel, setDefaultModel] = useState<ModelConfig | undefined>(
    initializeDefaultModel(uiSettings)
  );

  useEffect(() => {
    const fetchConfigInfo = async () => {
      try {
        const configFileInfo = await settingsAPI.getConfigInfo();

        // Check if config file has complete model client configurations
        if (configFileInfo?.has_config_file && configFileInfo?.config_content) {
          const configFileData = configFileInfo.config_content;

          const hasCompleteConfigFile =
            configFileData.model_client_configs?.orchestrator &&
            configFileData.model_client_configs?.web_surfer &&
            configFileData.model_client_configs?.coder &&
            configFileData.model_client_configs?.file_surfer &&
            configFileData.model_client_configs?.action_guard;

          if (hasCompleteConfigFile) {
            const modelFromConfigFile = initializeDefaultModel(configFileData);
            setDefaultModel(modelFromConfigFile);
            return;
          }
        }

        // Fall back to UI settings if no complete config file
        const modelFromUISettings = initializeDefaultModel(uiSettings);
        setDefaultModel(modelFromUISettings);
      } catch (error) {
        console.warn("Failed to fetch config file info:", error);
        // Fall back to UI settings on error
        const modelFromUISettings = initializeDefaultModel(uiSettings);
        setDefaultModel(modelFromUISettings);
      }
    };

    fetchConfigInfo();
  }, []);

  return { defaultModel, setDefaultModel };
};
