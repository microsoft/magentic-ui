import { useState, useEffect } from "react";
import { ModelConfig } from "../tabs/agentSettings/modelSelector/modelConfigForms/types";
import { initializeDefaultModel } from "../utils/modelUtils";
import { useSettingsStore } from "../../store";

export const useDefaultModel = () => {
    const { config } = useSettingsStore();
    const [defaultModel, setDefaultModel] = useState<ModelConfig | undefined>(
        initializeDefaultModel(config)
    );

    useEffect(() => {
        setDefaultModel(initializeDefaultModel(config));
    }, [config]);

    return { defaultModel, setDefaultModel };
};
