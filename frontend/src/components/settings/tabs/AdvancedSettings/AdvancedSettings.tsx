import React from "react";
import { Switch, Select, Tooltip } from "antd";
import { InfoCircleOutlined } from "@ant-design/icons";

interface AdvancedSettingsProps {
  config: any;
  handleUpdateConfig: (changes: any) => void;
}

const AdvancedSettings: React.FC<AdvancedSettingsProps> = ({ config, handleUpdateConfig }) => {
  return (
    <div className="flex flex-col flex-grow h-full space-y-4 px-4">
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-2">
          Allow Replans
          <Tooltip title="When enabled, Magentic-UI will automatically replan if the current plan is not working or you change the original request">
            <InfoCircleOutlined className="text-secondary hover:text-primary cursor-help" />
          </Tooltip>
        </span>
        <Switch
          checked={config.allow_for_replans}
          checkedChildren="ON"
          unCheckedChildren="OFF"
          onChange={(checked) => handleUpdateConfig({ allow_for_replans: checked })}
        />
      </div>
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-2">
          Retrieve Relevant Plans
          <Tooltip title="Controls how Magentic-UI retrieves and uses relevant plans from previous sessions">
            <InfoCircleOutlined className="text-secondary hover:text-primary cursor-help" />
          </Tooltip>
        </span>
        <Select
          value={config.retrieve_relevant_plans}
          onChange={(value) => handleUpdateConfig({ retrieve_relevant_plans: value })}
          style={{ width: 200 }}
          options={[
            { value: "never", label: "No plan retrieval" },
            { value: "hint", label: "Retrieve plans as hints" },
            { value: "reuse", label: "Retrieve plans to use directly" },
          ]}
        />
      </div>
    </div>
  );
};

export default AdvancedSettings;
