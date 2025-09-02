import React, { useState, useEffect } from "react";
import { Modal, Form, Input, Button, message, Tabs, Divider } from "antd";
import {
  // Types
  MCPServerInfo,
  SseServerParams,
  StdioServerParams,
  MCPAgentConfig,

  // Constants
  DEFAULT_SSE_PARAMS,
  DEFAULT_STDIO_PARAMS,
  serverNamePattern,
  agentNamePattern,

  // Type guards
  isSseServerParams,
  isStdioServerParams,

  // Schemas
  NamedMCPServerConfigSchema,

  // Utility functions
  isEmpty,

  // Validation functions
  validateJsonConfig,
  validateNamedMCPServerConfig,
  validateMCPAgentConfig
} from "./types";
import SseServerForm from "./configForms/SseServerForm";
import StdioServerForm from "./configForms/StdioServerForm";
import JsonForm from "./configForms/JsonForm";
import { mcpAPI } from "../../views/api";
import { useDefaultModel } from "../../settings/hooks/useDefaultModel";
import { ModelConfig } from "../../settings/tabs/agentSettings/modelSelector/modelConfigForms/types";
import { DEFAULT_OPENAI } from "../../settings/tabs/agentSettings/modelSelector/modelConfigForms/OpenAIModelConfigForm";

const { TextArea } = Input;

interface McpConfigModalProps {
  isOpen: boolean;
  onClose: () => void;
  server?: MCPServerInfo;
  onSave?: (data: MCPAgentConfig) => void;
  onUpdateConnectionStatus?: (serverName: string, connectionStatus: any) => void;
  existingServerNames?: string[];
}

const McpConfigModal: React.FC<McpConfigModalProps> = ({
  isOpen,
  onClose,
  server,
  onSave,
  onUpdateConnectionStatus,
  existingServerNames = [],
}) => {
  const [activeTab, setActiveTab] = useState("sse");
  const [form] = Form.useForm();
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [testConnectionStatus, setTestConnectionStatus] = useState<{
    isConnected: boolean;
    toolsFound?: number;
  } | null>(null);
  const [resetFlag, setResetFlag] = useState(0);

  // Server configuration state
  const [serverName, setServerName] = useState("");
  const [serverParams, setServerParams] = useState<SseServerParams | StdioServerParams>(DEFAULT_SSE_PARAMS);
  const [formAgentName, setFormAgentName] = useState("");
  const [formAgentDescription, setFormAgentDescription] = useState("");
  const [jsonConfig, setJsonConfig] = useState("");
  const [hasServerNameInteracted, setHasServerNameInteracted] = useState(false);
  const [initialServerName, setInitialServerName] = useState("");

  const { defaultModel } = useDefaultModel();
  const [modelClient, setModelClient] = useState<ModelConfig>(DEFAULT_OPENAI);

  // Reset interaction states when modal opens
  useEffect(() => {
    if (isOpen) {
      // Reset form fields when modal opens
      if (!server) {
        // Adding new server - reset all fields
        setServerName("");
        setInitialServerName("");
        setServerParams(DEFAULT_STDIO_PARAMS);
        setFormAgentName("");
        setFormAgentDescription("");
        setActiveTab("stdio");
        setJsonConfig("");
        setTestConnectionStatus(null);
      }

      // Reset interaction states
      setHasServerNameInteracted(false);
      setResetFlag(prev => prev + 1);

      // Reset form's internal state
      form.resetFields();
    }
  }, [isOpen, server, form]);

  // Track when user has interacted with server name field
  useEffect(() => {
    if (serverName !== initialServerName) {
      setHasServerNameInteracted(true);
    }
  }, [serverName, initialServerName]);

  // Initialize modelClient with defaultModel when available
  React.useEffect(() => {
    if (defaultModel) {
      setModelClient(defaultModel);
    }
  }, [defaultModel]);

  // Reset form when server prop changes
  useEffect(() => {
    if (server) {
      // Editing existing server
      setServerName(server.serverName);
      setInitialServerName(server.serverName);
      setServerParams(server.serverParams);
      setFormAgentName(server.agentName);
      setFormAgentDescription(server.agentDescription);
      setActiveTab(server.serverType === "SseServerParams" ? "sse" : "stdio");
      setJsonConfig("");
      setTestConnectionStatus(null); // Clear test status when editing
    }
  }, [server]);

  // Set server type when tab changes
  const handleTabChange = (newTab: string) => {
    const previousTab = activeTab;
    setActiveTab(newTab);

    if (previousTab === "json" && (newTab === "sse" || newTab === "stdio")) {
      // Parse JSON config when switching from JSON to other tabs
      try {
        if (jsonConfig) {
          const parsed = validateJsonConfig(jsonConfig, NamedMCPServerConfigSchema, "Invalid server configuration");
          setServerName(parsed.server_name);
          setServerParams(parsed.server_params);
        }
      } catch (error) {
        console.error("Failed to parse JSON config:", error);
        // Keep the current config if JSON parsing fails
      }
    } else if (newTab === "json") {
      if (server) {
        // Editing existing server - validate and show current config
        const jsonConfigValue = JSON.stringify(buildServerConfig(), null, 2);
        setJsonConfig(jsonConfigValue);
      } else {
        setJsonConfig("");
      }
    } else if (newTab === "stdio" && previousTab !== "json") {
      setServerParams(DEFAULT_STDIO_PARAMS);
    } else if (newTab === "sse" && previousTab !== "json") {
      setServerParams(DEFAULT_SSE_PARAMS);
    }
  };

  const buildServerConfig = () => {
    let localServerName;
    let localServerParams;

    if (activeTab === "json") {
      const parsed = validateJsonConfig(jsonConfig, NamedMCPServerConfigSchema, "Invalid server configuration");
      localServerName = parsed.server_name;
      localServerParams = parsed.server_params;
    } else {
      localServerName = serverName;
      localServerParams = serverParams;
    }

    const serverConfig = {
      server_name: localServerName,
      server_params: localServerParams
    };

    validateNamedMCPServerConfig(serverConfig);

    // Check for duplicate server name (only when adding new server, not when editing)
    if (!server && existingServerNames.includes(serverName)) {
      throw new Error("Server name already exists");
    }

    return serverConfig;
  };

  const handleSave = async () => {
    try {
      setIsSaving(true);
      const serverConfig = buildServerConfig();

      if (server) {
        // Editing existing server - create complete agent config with updated server
        const serverConfigWithStatus = {
          ...serverConfig,
          connection_status: server.connectionStatus ? {
            is_connected: server.connectionStatus.isConnected,
            tools_found: server.connectionStatus.toolsFound,
          } : undefined,
        };

        const partialAgentConfig = {
          name: formAgentName || server.agentName,
          description: formAgentDescription || server.agentDescription,
          mcp_servers: [serverConfigWithStatus],
        };

        if (onSave) {
          onSave(partialAgentConfig as MCPAgentConfig);
        }
      } else {
        // Adding new server - create complete agent configuration with connection status
        const serverConfigWithStatus = {
          ...serverConfig,
          connection_status: testConnectionStatus ? {
            is_connected: testConnectionStatus.isConnected,
            tools_found: testConnectionStatus.toolsFound,
          } : undefined,
        };

        // For new server - provide complete config with defaults
        const agentConfig: MCPAgentConfig = {
          name: formAgentName || `${serverConfig.server_name}agent`,
          description: formAgentDescription || `Agent using ${serverConfig.server_name}`, // TODO: automatically generate agent description
          system_message: "",
          mcp_servers: [serverConfigWithStatus],
          tool_call_summary_format: "{tool_name}({arguments}): {result}",
          model_client: modelClient,
        };

        // Validate complete agent configuration using Zod
        validateMCPAgentConfig(agentConfig);

        if (onSave) {
          onSave(agentConfig);
        }
      }

      message.success(server ? "Server configuration updated successfully!" : "Server configuration saved successfully!");
      onClose();
    } catch (error) {
      console.error("Save failed:", error);
      message.error(error instanceof Error ? error.message : "Failed to save configuration");
    } finally {
      setIsSaving(false);
    }
  };

  const handleTestConnection = async () => {
    let connectionStatus: any = null;

    try {
      setIsTesting(true);
      const serverConfig = buildServerConfig();

      // Call backend test endpoint using the API class
      const result = await mcpAPI.testMcpServer(serverConfig);

      // Prepare connection status to save
      connectionStatus = {
        isConnected: result.success,
        toolsFound: result.success ? result.details?.tools_found : undefined,
      };

      if (result.success) {
        message.success(`${result.message} (${result.details?.tools_found || 0} tools found)`);
      } else {
        message.error(`${result.message}: ${result.error}`);
      }
    } catch (error) {
      console.error("Test failed:", error);
      message.error(`Test failed: ${error instanceof Error ? error.message : 'Unknown error'}`);

      // Save error status
      connectionStatus = {
        isConnected: false,
        toolsFound: undefined,
      };
    } finally {
      // Update connection status in database if we have a server being edited
      if (server && onUpdateConnectionStatus && connectionStatus) {
        onUpdateConnectionStatus(server.serverName, connectionStatus);
      }
      // For new servers, store the connection status locally
      else if (!server && connectionStatus) {
        setTestConnectionStatus(connectionStatus);
      }
      setIsTesting(false);
    }
  };

  const serverNameError = hasServerNameInteracted && (isEmpty(serverName) || !serverNamePattern.test(serverName));
  const serverNameDuplicateError = !isEmpty(serverName) && existingServerNames.includes(serverName) && (!server || server.serverName !== serverName);
  const agentNameError = !isEmpty(formAgentName) && !agentNamePattern.test(formAgentName);

  const connectionStatus = server ? server.connectionStatus : testConnectionStatus;

  return (
    <Modal
      title={server ? "Edit MCP Server" : "Add MCP Server"}
      open={isOpen}
      onCancel={onClose}
      footer={[
        <div key="status" className="flex items-center gap-2">
          {connectionStatus && (
            <div className={`text-sm ${connectionStatus.isConnected ? 'text-green-600' : 'text-red-600'}`}>
              {connectionStatus.isConnected
                ? `✓ Test found ${connectionStatus.toolsFound || 0} tools`
                : '✗ Test failed'
              }
            </div>
          )}
        </div>,
        <Button key="test" onClick={handleTestConnection} loading={isTesting}>
          Test Connection
        </Button>,
        <Button
          key="save"
          type="primary"
          onClick={handleSave}
          loading={isSaving}
          disabled={serverNameError || serverNameDuplicateError || agentNameError}
        >
          {server ? "Update Server" : "Add Server"}
        </Button>,
      ]}
      width={600}
      className="max-h-[80vh] p-0 overflow-y-auto"
    >
      <Form form={form} layout="vertical">
        <div className="space-y-6 p-6">
          <div>
            <Tabs
              activeKey={activeTab}
              onChange={handleTabChange}
              items={[
                {
                  key: "sse",
                  label: "SSE",
                },
                {
                  key: "stdio",
                  label: "Stdio",
                },
                {
                  key: "json",
                  label: "JSON Config",
                },
              ]}
            />
          </div>

          {activeTab !== "json" && (
            <div className="space-y-4">
              <Form.Item
                label="Server Name"
                required
                validateStatus={serverNameError || serverNameDuplicateError ? 'error' : undefined}
                help={
                  serverNameError ? 'Server Name is required and can only contain letters and numbers.' :
                  serverNameDuplicateError ? 'Server name already exists.' : undefined
                }
              >
                <Input
                  value={serverName}
                  placeholder="Server Name"
                  status={serverNameError || serverNameDuplicateError ? 'error' : undefined}
                  onChange={e => {
                    setServerName(e.target.value);
                  }}
                  maxLength={50}
                  showCount
                />
              </Form.Item>
            </div>
          )}

          <div className="space-y-6">
            {activeTab === "sse" && isSseServerParams(serverParams) && (
              <SseServerForm
                value={serverParams}
                onValueChanged={(value) => setServerParams(value)}
              />
            )}
            {activeTab === "stdio" && isStdioServerParams(serverParams) && (
              <StdioServerForm
                value={serverParams}
                onValueChanged={(value) => setServerParams(value)}
                resetFlag={resetFlag}
              />
            )}
            {activeTab === "json" && (
              <JsonForm value={jsonConfig} onValueChanged={setJsonConfig} />
            )}
          </div>

          <div className="space-y-4">
            <Divider />
            <h3 className="text-lg font-medium">Agent Configuration</h3>

            <Form.Item
              label="Agent Name"
              validateStatus={agentNameError ? 'error' : undefined}
              help={agentNameError ? 'Agent name must be a valid Python identifier (letters, numbers, underscores only, must start with letter or underscore)' : undefined}
            >
              <Input
                value={formAgentName}
                onChange={e => setFormAgentName(e.target.value)}
                placeholder="Auto-generated from server name"
                maxLength={100}
                showCount
                status={agentNameError ? 'error' : undefined}
              />
            </Form.Item>

            <Form.Item
              label="Agent Description"
              rules={[{ required: true, message: "Agent description is required" }]}
            >
              <TextArea
                value={formAgentDescription}
                onChange={e => setFormAgentDescription(e.target.value)}
                rows={4}
                placeholder="This agent can help you with... Use this server when the user needs to..."
                maxLength={500}
                showCount
              />
            </Form.Item>
            <p className="text-sm text-gray-500">
              Describe how and when this server should be used. This helps the orchestrator decide when to call this agent.
            </p>
          </div>
        </div>
      </Form>
    </Modal>
  );
};

export default McpConfigModal;
