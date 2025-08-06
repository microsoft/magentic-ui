import React from "react";
import { Divider, Tooltip, Select, Flex, Switch } from "antd";
import { InfoCircleOutlined, MoonFilled, SunFilled, StarFilled, GlobalOutlined } from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import { appContext } from "../../../../hooks/provider";
import AllowedWebsitesList from "./AllowedWebsitesList";

interface GeneralSettingsProps {
  config: any;
  darkMode: string;
  setDarkMode: (mode: string) => void;
  handleUpdateConfig: (changes: any) => void;
}

const GeneralSettings: React.FC<GeneralSettingsProps> = ({
  config,
  darkMode,
  setDarkMode,
  handleUpdateConfig,
}) => {
  const { t } = useTranslation();
  const { language, setLanguage } = React.useContext(appContext);

  const getLanguageIcon = () => {
    return <GlobalOutlined className="w-4 h-4" />;
  };

  return (
    <Flex vertical gap="small">
      {/* Dark Mode Toggle */}
      <Flex align="center" justify="space-between">
        <span>
          {darkMode === "dark" ? "Dark Mode" : "Light Mode"}
</span>
        <button
          onClick={() => setDarkMode(darkMode === "dark" ? "light" : "dark")}
        >
          {darkMode === "dark" ? (
            <MoonFilled className="w-6 h-6" />
              ) : (
                <SunFilled className="w-6 h-6" />
              )}
        </button>
        <span>{t('language.language')}</span>
        <Select
          value={language}
          onChange={setLanguage}
          style={{ width: 150 }}
          options={[
            { 
              value: "zh-CN", 
              label: (
                <Flex align="center" gap="small">
                  {getLanguageIcon()}
                  {t('language.zh-CN')}
                </Flex>
              )
            },
            { 
              value: "en-US", 
              label: (
                <Flex align="center" gap="small">
                  {getLanguageIcon()}
                  {t('language.en-US')}
                </Flex>
              )
            },
          ]}
        />
      </Flex>

      <Divider style={{ margin: "0px" }} />

      {/* Basic Settings */}
      <Flex vertical gap="small">
                  <Flex align="center" justify="space-between" wrap>
            <Flex align="center" justify="start" gap="small">
              {t('generalSettings.approvalPolicy')}
              <Tooltip title={t('generalSettings.approvalPolicyTooltip')}>
                <InfoCircleOutlined className="text-secondary hover:text-primary cursor-help" />
              </Tooltip>
            </Flex>
            <Select
              value={config.approval_policy}
              onChange={(value) => handleUpdateConfig({ approval_policy: value })}
              options={[
                { value: "never", label: t('generalSettings.approvalPolicyNever') },
                { value: "auto-conservative", label: t('generalSettings.approvalPolicyAutoConservative') },
                { value: "always", label: t('generalSettings.approvalPolicyAlways') },
              ]}
            />
          </Flex>

        <Divider style={{ margin: "0px" }} />

        <AllowedWebsitesList
          config={config}
          handleUpdateConfig={handleUpdateConfig}
        />

        <Divider style={{ margin: "0px" }} />
        <Flex vertical gap="small">
          <Flex align="center" justify="space-between" wrap gap="large">
            <Flex align="center" justify="start" gap="small" wrap>
              {t('generalSettings.allowReplans')}
              <Tooltip title={t('generalSettings.allowReplansTooltip')}>
                <InfoCircleOutlined className="text-secondary hover:text-primary cursor-help" />
              </Tooltip>
            </Flex>
            <Switch
              checked={config.allow_for_replans}
              checkedChildren={t('common.on')}
              unCheckedChildren={t('common.off')}
              onChange={(checked) => handleUpdateConfig({ allow_for_replans: checked })}
            />
          </Flex>
          <Divider style={{ margin: "0px" }} />
          <Flex align="center" justify="space-between" wrap gap="large">
            <Flex align="center" justify="start" gap="small" wrap>
              {t('generalSettings.browserHeadless')}
              <Tooltip title={t('generalSettings.browserHeadlessTooltip')}>
                <InfoCircleOutlined className="text-secondary hover:text-primary cursor-help" />
              </Tooltip>
            </Flex>
            <Switch
              checked={config.browser_headless}
              checkedChildren={t('common.on')}
              unCheckedChildren={t('common.off')}
              onChange={(checked) =>
                handleUpdateConfig({ browser_headless: checked })
              }
            />
          </Flex>
          <Divider style={{ margin: "0px" }} />

          <Flex align="center" justify="space-between" wrap gap="small">
            <Flex align="center" gap="small">
              {t('generalSettings.retrieveRelevantPlans')}
              <Tooltip title={t('generalSettings.retrieveRelevantPlansTooltip')}>
                <InfoCircleOutlined className="text-secondary hover:text-primary cursor-help" />
              </Tooltip>
            </Flex>
            <Select
              value={config.retrieve_relevant_plans}
              onChange={(value) => handleUpdateConfig({ retrieve_relevant_plans: value })}
              options={[
                { value: "never", label: t('generalSettings.retrieveRelevantPlansNever') },
                { value: "hint", label: t('generalSettings.retrieveRelevantPlansHint') },
                { value: "reuse", label: t('generalSettings.retrieveRelevantPlansReuse') },
              ]}
            />
          </Flex>
        </Flex>
      </Flex>
    </Flex>
  );
};

export default GeneralSettings;
