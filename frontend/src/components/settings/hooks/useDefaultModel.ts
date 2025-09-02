import { useState, useEffect } from "react";
import { ModelConfig } from "../tabs/agentSettings/modelSelector/modelConfigForms/types";
import { initializeDefaultModel } from "../utils/modelUtils";
import { useSettingsStore } from "../../store";
import { settingsAPI } from "../../views/api";

/**
 * Hook to get the default model, prioritizing config file over UI settings
 *
 * When --config is provided, it uses the default model from the config file.
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

        // Check if config file exists and has content
        if (configFileInfo?.has_config_file && configFileInfo?.config_content) {
          const configFileData = configFileInfo.config_content;
          const modelFromConfigFile = initializeDefaultModel(configFileData);
          setDefaultModel(modelFromConfigFile);
          return;
        }

        // Fall back to UI settings if no config file
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
