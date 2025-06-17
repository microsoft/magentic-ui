import React, { } from "react";
import MCPAgentForm from "./MCPAgentForm";
import { List, Divider, Flex } from "antd";
import { Button as MagenticButton } from "../../../../common/Button";
import { MCPAgentConfig } from "./types";
import { DEFAULT_OPENAI } from "../modelSelector/modelConfigForms/OpenAIModelConfigForm";
import { Typography } from "antd";
import { SettingsTabProps } from "../../../types";
import { ModelConfig } from "../modelSelector/modelConfigForms/types";

const DEFAULT_AGENT: MCPAgentConfig = {
  name: "",
  description: "",
  system_message: "",
  mcp_servers: [],
  model_context_token_limit: undefined,
  tool_call_summary_format: "{tool_name}({arguments}): {result}",
  model_client: DEFAULT_OPENAI,
};

export interface MCPAgentsSettingsProps extends SettingsTabProps {
  defaultModel: ModelConfig | undefined;
  advanced: boolean;
}

const MCPAgentsSettings: React.FC<MCPAgentsSettingsProps> = ({ config, handleUpdateConfig, defaultModel, advanced }) => {
  const value = config?.mcp_agent_configs || [];

  const handleAgentChange = (idx: number, updated: MCPAgentConfig) => {
    const updatedAgents = value.map((a, i) => (i === idx ? updated : a));
    handleUpdateConfig({ mcp_agent_configs: [...updatedAgents] });
  };

  const addAgent = () => {
    handleUpdateConfig({ mcp_agent_configs: [...value, { ...DEFAULT_AGENT }] });
  };

  const removeAgent = (idx: number) => {
    const updatedAgents = value.filter((_, i) => i !== idx);
    handleUpdateConfig({ mcp_agent_configs: [...updatedAgents] });
  };

  return (
    <Flex vertical gap="large">
      <Typography.Text>
        Extend Magentic-UI's capabilities by adding custom agents that connect to local or remote Model Context Protocol (MCP) Servers!
      </Typography.Text>
      <Typography.Text>
        Any number of agents are supported, and each agent requires at least one MCP Server.
      </Typography.Text>
      <Typography.Text italic type="warning">
        These settings will be applied to all new sessions until you remove agents from this list.
      </Typography.Text>
      <Divider size="small" />
      <List
        dataSource={value}
        renderItem={(agent, idx) => {
          return (
            <List.Item key={idx}>
              <MCPAgentForm
                agent={agent}
                advanced={advanced}
                defaultModel={defaultModel}
                idx={idx}
                handleAgentChange={handleAgentChange}
                removeAgent={removeAgent}
              />
            </List.Item>
          );
        }}
        locale={{ emptyText: 'No MCP Agents. Click "Add MCP Agent" to create one.' }}
      />
      <Divider orientation="left">
        <MagenticButton onClick={addAgent} variant="primary">
          + Add MCP Agent
        </MagenticButton>
      </Divider>
    </Flex>
  );
};

export default MCPAgentsSettings;
