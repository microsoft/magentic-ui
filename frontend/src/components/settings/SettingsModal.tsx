import React, { useCallback } from "react";
import { useTranslation } from "react-i18next";
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
  const { t } = useTranslation();
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
            // Merge backend settings with frontend defaults
            const { config: defaultConfig } = useSettingsStore.getState();
            const mergedConfig = { ...defaultConfig, ...settings };

            // Always use the merged config since we provide proper defaults
            updateConfig(mergedConfig);
            setOriginalConfig(mergedConfig);
          } catch (error) {
            message.error(
              t('settings.failedToLoadSettings') + ", Error: " + error
            );
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
        message.success(t('settings.updatedSettings'));
      } catch (error) {
        message.error(t('settings.failedToSaveSettings'));
        console.error("Failed to save settings:", error);
        return;
      }
    }

    onClose();
  }, [config, originalConfig, user?.email, onClose]);

  const tabItems = {
    "general": {
      label: t('settings.general'),
      children: (
        <>
        <Typography.Text strong>{t('generalSettings.title')}</Typography.Text>
        <Divider />
        <GeneralSettings
          darkMode={darkMode as "dark" | "light" | "spirits"}
          setDarkMode={setDarkMode as (mode: "dark" | "light" | "spirits") => void}
          config={config}
          handleUpdateConfig={handleUpdateConfig}
          />
        </>
      ),
    },
    "agents": {
      label: t('settings.agents'),
      children: (
        <>
        <Typography.Text strong>{t('agentSettings.title')}</Typography.Text>
        <Divider />
        <AgentSettingsTab
          config={config}
          handleUpdateConfig={handleUpdateConfig}
          />
        </>
      ),
    },
    "advanced_config": {
      label: t('settings.advanced'),
      children: (
        <>
        <Typography.Text strong>{t('advancedSettings.title')}</Typography.Text>
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
              {t('settings.resetToDefaults')}
            </Button>
            {hasChanges && (
                <Typography.Text italic type="warning">
                  {t('settings.settingsChangesWarning')}
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
