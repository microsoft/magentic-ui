import React, { useEffect } from "react";
import { Input, Form, Divider, Space, Tooltip, Collapse, Typography, List, Row, Flex, Button } from "antd";
import MCPServerForm, { DEFAULT_STDIO_PARAMS } from "./mcpServerForms/MCPServerForm";
import ModelSelector from "../modelSelector/ModelSelector";
import { validateModelConfig } from '../../../validation';
import { Button as MagenticButton } from '../../../../common/Button'
import { MCPAgentConfig } from "./types";
import { ModelConfig } from "../modelSelector/modelConfigForms/types";
import { DEFAULT_OPENAI } from "../modelSelector/modelConfigForms/OpenAIModelConfigForm";

interface MCPAgentFormProps {
  agent: MCPAgentConfig;
  defaultModel?: ModelConfig;
  advanced: boolean;
  idx: number;
  handleAgentChange: (idx: number, updated: MCPAgentConfig) => void;
  removeAgent: (idx: number) => void;
}

const MCPAgentForm: React.FC<MCPAgentFormProps> = ({ agent, defaultModel, advanced, idx, handleAgentChange, removeAgent, }) => {
  const nameError = !agent.name || agent.name.trim() === '';
  const descError = !agent.description || agent.description.trim() === '';
  const hasServer = Array.isArray(agent.mcp_servers) && agent.mcp_servers.length > 0;
  const mcpServerError = !hasServer;
  const modelConfigErrors = validateModelConfig(agent.model_client);
  const modelClientError = modelConfigErrors.length > 0;

  // Remove local servers state, use agent.mcp_servers directly
  const handleServerChange = (serverIdx: number, updated: any) => {
    // No type reset logic here; MCPServerCard will handle type switching and reset
    const updatedServers = agent.mcp_servers.map((s: any, i: number) => (i === serverIdx ? updated : s));
    handleAgentChange(idx, { ...agent, mcp_servers: updatedServers });
  };

  const addServer = () => {
    const newServer = {
      server_name: "",
      server_params: DEFAULT_STDIO_PARAMS,
    };
    const updatedServers = [...(agent.mcp_servers || []), newServer];
    handleAgentChange(idx, { ...agent, mcp_servers: updatedServers });
  };

  const removeServer = (serverIdx: number) => {
    const updatedServers = (agent.mcp_servers || []).filter((_: any, i: number) => i !== serverIdx);
    handleAgentChange(idx, { ...agent, mcp_servers: updatedServers });
  };

  useEffect(() => {
    if (advanced) {
      handleAgentChange(idx, {...agent, model_client: defaultModel ?? DEFAULT_OPENAI})
    }

  }, [defaultModel, advanced])

  // Name input for the collapse header
  return (
    <Collapse defaultActiveKey={["1"]} style={{ flex: 1, flexGrow: 1 }}>
      <Collapse.Panel
        key="1"
        header={
          <Flex align="center" justify="space-between" gap="small">
            <Tooltip title={nameError ? 'Name is required' : ''} open={nameError ? undefined : false}>
              <Input
                placeholder="Enter the agent's name."
                value={agent.name}
                status={nameError ? 'error' : ''}
                onChange={e => handleAgentChange(idx, { ...agent, name: e.target.value })}
                onClick={(e) => e.stopPropagation()}
              />
            </Tooltip>
            <Button
              danger
              onClick={(e) => { e.stopPropagation(); removeAgent(idx); }}
              style={{ float: "right" }}
            >
              Remove
            </Button>
          </Flex>
        }
      >
        <Form layout="vertical">
          {advanced &&
            <>
              <Tooltip title={modelClientError ? 'Errors in Model' : ''} open={modelClientError ? undefined : false}>
                <Form.Item
                  label="Model"
                  required
                  validateStatus={modelClientError ? 'error' : ''}
                  style={modelClientError ? { border: '1px solid #ff4d4f', borderRadius: 4, padding: 4 } : {}}
                >
                  <ModelSelector
                    value={agent.model_client}
                    onChange={modelClient => handleAgentChange(idx, { ...agent, model_client: modelClient })}
                  />
                </Form.Item>
              </Tooltip>
            </>
          }
          <Tooltip title={descError ? 'Description is required' : ''} open={descError ? undefined : false}>
            <Form.Item label="Description" required>
              <Input.TextArea
                value={agent.description}
                placeholder="Describe what this agent can do. The orchestrator will use this description to determine when to hand off to this agent."
                status={descError ? 'error' : ''}
                onChange={e => handleAgentChange(idx, { ...agent, description: e.target.value })}
                autoSize={{ minRows: 2, maxRows: 4 }}
              />
            </Form.Item>
          </Tooltip>
{/*           <Collapse>
            <Collapse.Panel key="1" header={<Typography>Optional Properties</Typography>}>
              <Form.Item label="System Message">
                <Input.TextArea
                  value={agent.system_message}
                  placeholder="Set this agent's LLM System Message."
                  onChange={e => handleAgentChange(idx, { ...agent, system_message: e.target.value })}
                  autoSize={{ minRows: 2, maxRows: 4 }}
                />
              </Form.Item>
              <Form.Item label="Model Context Token Limit (optional)">
                <Input
                  type="number"
                  placeholder="Specify a maximum context length for this agent's memory."
                  value={agent.model_context_token_limit ?? ""}
                  onChange={e => handleAgentChange(idx, { ...agent, model_context_token_limit: e.target.value ? Number(e.target.value) : undefined })}
                />
              </Form.Item>
              <Form.Item label="Tool Call Summary Format (optional)">
                <Input
                  value={agent.tool_call_summary_format ?? ""}
                  onChange={e => handleAgentChange(idx, { ...agent, tool_call_summary_format: e.target.value })}
                />
              </Form.Item>
            </Collapse.Panel>
          </Collapse> */}

          <Divider orientation="left" style={{ margin: "0px" }}>MCP Servers</Divider>
          <Flex vertical gap="small">
            <Tooltip title={mcpServerError ? 'At least one MCP Server is required' : ''} open={mcpServerError ? undefined : false}>
              <List
                style={{
                  border: mcpServerError ? '1px solid #ff4d4f' : 'none'
                }}
                dataSource={agent.mcp_servers || []}
                renderItem={(server: any, serverIdx: number) => (
                  <List.Item key={serverIdx} style={{ width: "100%" }}>
                    <MCPServerForm
                      server={server}
                      idx={serverIdx}
                      handleServerChange={handleServerChange}
                      removeServer={removeServer}
                    />
                  </List.Item>
                )}
                locale={{ emptyText: 'No MCP Servers. Click "Add MCP Server" to create one.' }}
              />
            </Tooltip>
            <Divider orientation="left" style={{ margin: "0px" }}>
              <MagenticButton onClick={addServer} variant="primary">
                + Add MCP Server
              </MagenticButton>
            </Divider>
          </Flex>
        </Form>
      </Collapse.Panel>
    </Collapse>
  );
};

export default MCPAgentForm;
