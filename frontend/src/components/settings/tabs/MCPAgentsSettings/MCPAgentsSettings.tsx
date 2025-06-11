import React, { isValidElement, useEffect } from "react";
import MCPAgentCard from "./MCPAgentCard";
import { Space, List, Divider } from "antd";
import { ModelConfig } from "../ModelConfigSettings/ModelConfigForms/ModelConfigForms";
import { Button } from "../../../common/Button";
import { validateMCPAgentsSettings } from '../../validation';

interface McpAgentConfig {
  name: string;
  description: string;
  system_message?: string;
  mcp_servers: any[];
  model_context_token_limit?: number;
  tool_call_summary_format?: string;
  model_client: ModelConfig;
}

interface MCPAgentsSettingsProps {
  value: McpAgentConfig[];
  onChange: (agents: McpAgentConfig[]) => void;
}

const defaultAgent: McpAgentConfig = {
  name: "",
  description: "",
  system_message: "",
  mcp_servers: [],
  model_context_token_limit: undefined,
  tool_call_summary_format: "{tool_name}({arguments}): {result}",
  model_client: {
    provider: "",
    config: { model: "" }
  },
};

const MCPAgentsSettings: React.FC<MCPAgentsSettingsProps> = ({ value, onChange }) => {
  const handleAgentChange = (idx: number, updated: McpAgentConfig) => {
    const updatedAgents = value.map((a, i) => (i === idx ? updated : a));
    onChange(updatedAgents);
  };

  const addAgent = () => {
    onChange([...value, { ...defaultAgent }]);
  };

  const removeAgent = (idx: number) => {
    const updatedAgents = value.filter((_, i) => i !== idx);
    onChange(updatedAgents);
  };

  return (
    <Space direction="vertical" style={{ width: "100%", height: "100%", flexGrow: 1, display: 'flex', flexDirection: 'column' }} size="large">
      <h1>MCP Agents Settings</h1>
      <Button onClick={addAgent} variant="primary">
        + Add MCP Agent
      </Button>
      <List
        dataSource={value}
        style={{ width: "100%", flex: 1, overflow: "auto" }}
        renderItem={(agent, idx) => {
          return (
            <List.Item key={idx} style={{ width: "100%" }}>
              <MCPAgentCard
                agent={agent}
                idx={idx}
                handleAgentChange={handleAgentChange}
                removeAgent={removeAgent}
              />
            </List.Item>
          );
        }}
        locale={{ emptyText: 'No MCP Agents. Click "Add MCP Agent" to create one.' }}
      />
    </Space>
  );
};

export default MCPAgentsSettings;
