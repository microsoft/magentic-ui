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
  Spin,
  Tabs,
  Typography,
} from "antd";
import { validateAll } from "./validation";

interface SettingsMenuProps {
  isOpen: boolean;
  onClose: () => void;
}

const SettingsModal: React.FC<SettingsMenuProps> = ({ isOpen, onClose }) => {
  const { darkMode, setDarkMode, user } = React.useContext(appContext);
  const [isEmailModalOpen, setIsEmailModalOpen] = React.useState(false);
  const [hasChanges, setHasChanges] = React.useState(false);
  const [isLoading, setIsLoading] = React.useState(false);
  const [originalConfig, setOriginalConfig] = React.useState<any>(null);

  const { config, updateConfig, resetToDefaults } = useSettingsStore();

  React.useEffect(() => {
    if (isOpen) {
      setHasChanges(false);
      setIsLoading(true);

      // Load settings when modal opens
      const loadSettings = async () => {
        if (user?.email) {
          try {
            const settings = await settingsAPI.getSettings(user.email);
            const errors = validateAll(settings);
            if (errors.length > 0) {
              message.error("Failed to load settings. Using defaults.");
              resetToDefaults();
              setOriginalConfig(null);
            } else {
              updateConfig(settings);
              setOriginalConfig(settings);
            }
          } catch (error) {
            message.error("Failed to load settings. Using defaults.");
            resetToDefaults();
            setOriginalConfig(null);
          }
        }
        setIsLoading(false);
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
    const validationErrors = validateAll(config);
    if (validationErrors.length > 0) {
      const errors = validationErrors.join("\n");
      message.error(errors);
      return;
    }

    // Only save if there are actual changes
    const hasActualChanges =
      originalConfig &&
      JSON.stringify(config) !== JSON.stringify(originalConfig);

    if (hasActualChanges && user?.email) {
      try {
        await settingsAPI.updateSettings(user.email, config);
        message.success("Updated settings!");
      } catch (error) {
        message.error("Failed to save settings");
        console.error("Failed to save settings:", error);
        return;
      }
    }

    onClose();
  }, [config, originalConfig, user?.email, onClose]);

  const tabItems = {
    general: {
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
    agents: {
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
    advanced_config: {
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
  };

  return (
    <>
      <Modal
        open={isOpen}
        style={{ maxHeight: 800, overflow: "auto" }}
        onCancel={handleClose}
        closable={true}
        width={800}
        height={800}
        footer={[
          <Flex gap="large" justify="start" align="center">
            <Button
              key="reset"
              onClick={handleResetDefaults}
              disabled={isLoading}
            >
              Reset to Defaults
            </Button>
            {hasChanges && (
              <Typography.Text italic type="warning">
                Warning: Settings changes will only apply when you create a new
                session
              </Typography.Text>
            )}
          </Flex>,
        ]}
      >
        {isLoading ? (
          <Flex justify="center" align="center" style={{ height: "400px" }}>
            <Spin size="large" />
          </Flex>
        ) : (
          <Tabs
            tabPosition="left"
            items={Object.entries(tabItems).map(
              ([key, { label, children }]) => ({ key, label, children })
            )}
          />
        )}
      </Modal>
      <SignInModal
        isVisible={isEmailModalOpen}
        onClose={() => setIsEmailModalOpen(false)}
      />
    </>
  );
};

export default SettingsModal;
