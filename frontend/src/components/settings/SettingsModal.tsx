import React, { useCallback } from "react";
import { appContext } from "../../hooks/provider";
import SignInModal from "../signin";
import { useSettingsStore } from "../store";
import { settingsAPI } from "../views/api";
import GeneralSettings from "./tabs/GeneralSettings/GeneralSettings";
import AgentSettingsTab from "./tabs/agentSettings/AgentSettingsTab";
import AdvancedConfigEditor from "./tabs/advancedSetings/AdvancedSettings";
import {
  Button,
  Divider,
  Flex,
  message,
  Modal,
  Select,
  Tabs,
  Typography,
} from "antd";
import { validateAll } from "./validation";

const { Option } = Select;

interface SettingsMenuProps {
  isOpen: boolean;
  onClose: () => void;
}

const SettingsModal: React.FC<SettingsMenuProps> = ({ isOpen, onClose }) => {
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
        <>
        <Typography.Text strong>General Settings</Typography.Text>
        <Divider />
        <GeneralSettings
          darkMode={darkMode}
          setDarkMode={setDarkMode}
          config={config}
          handleUpdateConfig={handleUpdateConfig}
          />
        </>
      ),
    },
    "agents": {
      label: "Agent Settings",
      children: (
        <>
        <Typography.Text strong>Agent Settings</Typography.Text>
        <Divider />
        <AgentSettingsTab
          config={config}
          handleUpdateConfig={handleUpdateConfig}
          />
        </>
      ),
    },
    "advanced_config": {
      label: "Advanced Settings",
      children: (
        <>
        <Typography.Text strong>Advanced Settings</Typography.Text>
        <Divider />
        <AdvancedConfigEditor
          config={config}
          darkMode={darkMode}
          handleUpdateConfig={handleUpdateConfig}
          />
        </>
      ),
    },
  }

  return (
    <>
      <Modal
        open={isOpen}
        style={{maxHeight: 800, overflow: 'auto' }}

        onCancel={handleClose}
        closable={true}
        width={800}
        height={800}
        footer={[
          <Flex gap="large" justify="start" align="center">
            <Button key="reset" onClick={handleResetDefaults}>
              Reset to Defaults
            </Button>
            {hasChanges && (
                <Typography.Text italic type="warning">
                  Warning: Settings changes will only apply when you create a new session
                </Typography.Text>
            )}
          </Flex>
        ]}
      >
        <Tabs
          tabPosition="left"
          items={Object.entries(tabItems).map(([key, {label, children}]) => ({key, label, children}))}
        />
      </Modal>
      <SignInModal
        isVisible={isEmailModalOpen}
        onClose={() => setIsEmailModalOpen(false)}
      />
    </>
  );
};

export default SettingsModal;
