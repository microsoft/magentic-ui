import React from "react";
import { MoonIcon, SunIcon } from "@heroicons/react/24/outline";
import { Divider, Tooltip, Select } from "antd";
import { InfoCircleOutlined } from "@ant-design/icons";
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
  return (
    <div className="space-y-6 px-4">
      {/* Dark Mode Toggle */}
      <div className="flex items-center justify-between">
        <span className="text-primary">
          {darkMode === "dark" ? "Dark Mode" : "Light Mode"}
        </span>
        <button
          onClick={() => setDarkMode(darkMode === "dark" ? "light" : "dark")}
          className="text-secondary hover:text-primary"
        >
          {darkMode === "dark" ? (
            <MoonIcon className="h-6 w-6" />
          ) : (
            <SunIcon className="h-6 w-6" />
          )}
        </button>
      </div>

      <Divider />

      {/* Basic Settings */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <span className="flex items-center gap-2">
            Action Approval Policy
            <Tooltip title="Controls when approval is required before taking actions">
              <InfoCircleOutlined className="text-secondary hover:text-primary cursor-help" />
            </Tooltip>
          </span>
          <Select
            value={config.approval_policy}
            onChange={(value) => handleUpdateConfig({ approval_policy: value })}
            style={{ width: 200 }}
            options={[
              { value: "never", label: "Never require approval" },
              { value: "auto-conservative", label: "AI based judgement" },
              { value: "always", label: "Always require approval" },
            ]}
          />
        </div>

        <Divider />

        <AllowedWebsitesList
          config={config}
          handleUpdateConfig={handleUpdateConfig}
        />
      </div>
    </div>
  );
};

export default GeneralSettings;
