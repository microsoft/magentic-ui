import React, { useCallback, useState } from "react";
import { appContext } from "../../hooks/provider";
import SignInModal from "../signin";
import { useSettingsStore } from "../store";
import { settingsAPI } from "../views/api";
import GeneralSettings from "./tabs/GeneralSettings/GeneralSettings";
import AdvancedSettings from "./tabs/AdvancedSettings/AdvancedSettings";
import ModelConfigSettings from "./tabs/ModelConfigSettings/ModelConfigSettings";
import MCPAgentsSettings from "./tabs/MCPAgentsSettings/MCPAgentsSettings";
import AdvancedConfigEditor from "./tabs/AdvancedConfigEditor/AdvancedConfigEditor";
import {
  Button,
  message,
  Modal,
  Select,
  Tabs,
} from "antd";
import { validateAll } from "./validation";

const { Option } = Select;

interface SettingsMenuProps {
  isOpen: boolean;
  onClose: () => void;
}

const SettingsMenu: React.FC<SettingsMenuProps> = ({ isOpen, onClose }) => {
  const { darkMode, setDarkMode, user } = React.useContext(appContext);
  const [isEmailModalOpen, setIsEmailModalOpen] = React.useState(false);
  const [hasChanges, setHasChanges] = React.useState(false);

  const { config, updateConfig, resetToDefaults } = useSettingsStore();

  React.useEffect(() => {
    if (isOpen) {
      setHasChanges(false);

      // Load settings when modal opens
      const loadSettings = async () => {
        if (user?.email) {
          try {
            const settings = await settingsAPI.getSettings(user.email);
            const errors = validateAll(settings)
            if (errors.length > 0) {
              message.error("Failed to load settings. Using defaults.");
              resetToDefaults();
            }
            else {
              updateConfig(settings);
            }
          } catch (error) {
            message.error("Failed to load settings. Using defaults.")
            resetToDefaults();
          }
        }
      };
      loadSettings();
    }
  }, [isOpen, user?.email]);

  const handleUpdateConfig = async (changes: any) => {
    updateConfig(changes);
    setHasChanges(true);
  };

  const handleResetDefaults = async () => {
    resetToDefaults();
    setHasChanges(true);
  };

  const handleClose = useCallback(async () => {
    // Check all validation states before saving
    const validationErrors = validateAll(config)
    if (validationErrors.length > 0) {
      const errors = validationErrors.join("\n");
      message.error(errors);
    }
    else {
      // Save to database
      if (user?.email) {
        try {
          await settingsAPI.updateSettings(user.email, config);
          message.success("Updated settings!")
        } catch (error) {
          message.error("Failed to save settings");
          console.error("Failed to save settings:", error);
        }
      }
      
      onClose();
    }

  }, [config, settingsAPI, message]);

  const tabItems = {
    "general": {
      label: "General",
      children: (
        <GeneralSettings
          darkMode={darkMode}
          setDarkMode={setDarkMode}
          config={config}
          handleUpdateConfig={handleUpdateConfig}
        />
      ),
    },
    "advanced": {
      label: "Advanced",
      children: (
        <AdvancedSettings
          config={config}
          handleUpdateConfig={handleUpdateConfig}
        />
      ),
    },
    "model": {
      label: "Model Configuration",
      children: (
        <ModelConfigSettings
          config={config}
          handleUpdateConfig={handleUpdateConfig}
        />
      ),
    },
    "mcp_agents": {
      label: "MCP Agents",
      children: (
        <MCPAgentsSettings
          value={config.mcp_agent_configs ?? []}
          onChange={(changes) => handleUpdateConfig({ mcp_agent_configs: changes })}
        />
      ),
    },
    "advanced_config": {
      label: "Advanced Config",
      children: (
        <AdvancedConfigEditor
          config={config}
          darkMode={darkMode}
          handleUpdateConfig={handleUpdateConfig}
        />
      ),
    },
  }

  return (
    <>
      <Modal
        open={isOpen}
        onCancel={handleClose}
        closable={true}
        footer={[
          <div key="footer" className="mt-12 space-y-2">
            {hasChanges && (
              <div className="text-secondary text-sm italic">
                Warning: Settings changes will only apply when you create a new session
              </div>
            )}
            <div className="flex gap-2 justify-end">
              <Button key="reset" onClick={handleResetDefaults}>
                Reset to Defaults
              </Button>
            </div>
          </div>,
        ]}
        width="80%"
        style={{ maxWidth: "900px" }}
      >
        <div className="mt-12 space-y-4">
          <Tabs
            tabPosition="left"
            items={Object.entries(tabItems).map(([key, {label, children}]) => ({key, label, children}))}
          />
        </div>
      </Modal>
      <SignInModal
        isVisible={isEmailModalOpen}
        onClose={() => setIsEmailModalOpen(false)}
      />
    </>
  );
};

export default SettingsMenu;
