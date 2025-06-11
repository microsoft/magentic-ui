import React, { useEffect } from "react";
import { Input, Form, Divider, Space, Card, Tooltip, Collapse, Typography, List } from "antd";
import MCPServerCard from "./MCPServerCard";
import ModelSelector from "../ModelConfigSettings/ModelSelector";
import { ModelConfig } from "../ModelConfigSettings/ModelConfigForms/ModelConfigForms";
import { Button } from "../../../common/Button";
import { validateModelConfig } from '../../validation';

interface MCPAgentConfig {
  name: string;
  description: string;
  model_client: ModelConfig;
  mcp_servers: any[];
  system_message?: string;
  model_context_token_limit?: number;
  tool_call_summary_format?: string;
}

interface MCPAgentCardProps {
  agent: MCPAgentConfig;
  idx: number;
  handleAgentChange: (idx: number, updated: MCPAgentConfig) => void;
  removeAgent: (idx: number) => void;
}

const MCPAgentCard: React.FC<MCPAgentCardProps> = ({ agent, idx, handleAgentChange, removeAgent, }) => {
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
      server_params: { type: "StdioServerParams", command: "npx", args: [], read_timeout_seconds: 5 },
    };
    const updatedServers = [...(agent.mcp_servers || []), newServer];
    handleAgentChange(idx, { ...agent, mcp_servers: updatedServers });
  };

  const removeServer = (serverIdx: number) => {
    const updatedServers = (agent.mcp_servers || []).filter((_: any, i: number) => i !== serverIdx);
    handleAgentChange(idx, { ...agent, mcp_servers: updatedServers });
  };

  // Name input for the collapse header
  const nameInput = (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <Tooltip title={nameError ? 'Name is required' : ''} open={nameError ? undefined : false}>
        <Input
          placeholder="Agent Name"
          value={agent.name}
          status={nameError ? 'error' : ''}
          onChange={e => handleAgentChange(idx, { ...agent, name: e.target.value })}
          style={{ width: 200 }}
          size="small"
          onClick={(e) => e.stopPropagation()}
        />
      </Tooltip>
      <Button variant="danger" onClick={(e) => { e.stopPropagation(); removeAgent(idx); }}>
        Remove
      </Button>
    </div>
  );

  return (
    <Card style={{ width: "100%", background: "transparent", border: "none" }}>
      <Collapse defaultActiveKey={["1"]}>
        <Collapse.Panel header={nameInput} key="1" style={{ border: 'none', background: 'transparent' }}>
          <Form layout="vertical">
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
            <Collapse>
              <Collapse.Panel key="1" header={<Typography>Optional Properties</Typography>}>
                <Form.Item label="System Message">
                  <Input.TextArea
                    value={agent.system_message}
                    onChange={e => handleAgentChange(idx, { ...agent, system_message: e.target.value })}
                    autoSize={{ minRows: 2, maxRows: 4 }}
                  />
                </Form.Item>
                <Form.Item label="Model Context Token Limit (optional)">
                  <Input
                    type="number"
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
            </Collapse>

            <Divider orientation="left">MCP Servers</Divider>
            <Tooltip title={mcpServerError ? 'At least one MCP Server is required' : ''} open={mcpServerError ? undefined : false}>
              <Space
                direction="vertical"
                // size="small"
                style={{
                  width: '100%',
                  background: 'transparent',
                  border: mcpServerError ? '1px solid #ff4d4f' : 'none'
                }}
              >
                <Button onClick={addServer} variant="primary">
                  Add MCP Server
                </Button>
                <List
                  style={{ width: "100%" }}
                  dataSource={agent.mcp_servers || []}
                  renderItem={(server: any, serverIdx: number) => (
                    <List.Item key={serverIdx} style={{ width: "100%" }}>
                      <MCPServerCard
                        server={server}
                        idx={serverIdx}
                        handleServerChange={handleServerChange}
                        removeServer={removeServer}
                      />
                    </List.Item>
                  )}
                />
              </Space>
            </Tooltip>
          </Form>
        </Collapse.Panel>
      </Collapse>
    </Card>
  );
};

export default MCPAgentCard;
