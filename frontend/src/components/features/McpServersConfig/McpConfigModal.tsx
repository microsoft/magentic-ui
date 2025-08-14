import React, { useState } from "react";
import { Modal, Form, Input, Button, message, Tabs, Tooltip, Divider } from "antd";
import {
  // Types
  MCPServerInfo,
  SseServerParams,
  StdioServerParams,

  // Constants
  DEFAULT_SSE_PARAMS,
  DEFAULT_STDIO_PARAMS,
  serverNamePattern,

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
  onSave?: (server: MCPServerInfo) => void;
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

  // Server configuration state
  const [serverName, setServerName] = useState("");
  const [serverParams, setServerParams] = useState<SseServerParams | StdioServerParams>(DEFAULT_SSE_PARAMS);
  const [formAgentName, setFormAgentName] = useState("");
  const [formAgentDescription, setFormAgentDescription] = useState("");
  const [jsonConfig, setJsonConfig] = useState("");

  // Model configuration state
  const { defaultModel } = useDefaultModel();
  const [modelClient, setModelClient] = useState<ModelConfig>(DEFAULT_OPENAI);

  // Initialize modelClient with defaultModel when available
  React.useEffect(() => {
    if (defaultModel) {
      setModelClient(defaultModel);
    }
  }, [defaultModel]);

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

  React.useEffect(() => {
    if (isOpen) {
      const activeTab = server?.serverType === "StdioServerParams" ? "stdio" : "sse";
      setActiveTab(activeTab);
      setServerName(server?.serverName || "");
      setServerParams(server?.serverParams || DEFAULT_SSE_PARAMS);
      setFormAgentName(server?.agentName || "");
      setFormAgentDescription(server?.agentDescription || "");

      // Set JSON config after state is initialized
      if (server) {
        const serverConfig = {
          server_name: server.serverName,
          server_params: server.serverParams
        };
        setJsonConfig(JSON.stringify(serverConfig, null, 2));
      } else {
        setJsonConfig("");
      }

      // Reset form fields only when adding new server
      if (!server) {
        form.resetFields();
      }
    }
  }, [server, isOpen, form]);

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
        // Editing existing server - return server config and updated agent info
        if (onSave) {
          onSave({
            serverConfig,
            agentName: formAgentName,
            agentDescription: formAgentDescription
          } as any);
        }
      } else {
        // Adding new server - create complete agent configuration
        const agentConfig = {
          name: formAgentName || `${serverConfig.server_name}agent`,
          description: formAgentDescription || `Agent using ${serverConfig.server_name}`, // TODO: automatically generate agent description
          system_message: "",
          mcp_servers: [serverConfig],
          tool_call_summary_format: "{tool_name}({arguments}): {result}",
          model_client: modelClient
        };

        // Validate complete agent configuration using Zod
        validateMCPAgentConfig(agentConfig);

        if (onSave) {
          onSave(agentConfig as any);
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

      return connectionStatus;
    } catch (error) {
      console.error("Test connection failed:", error);
      message.error(`Test failed: ${error instanceof Error ? error.message : 'Unknown error'}`);

      // Save error status
      connectionStatus = {
        isConnected: false,
        toolsFound: undefined,
      };

      return connectionStatus;
    } finally {
      // Update connection status in database if we have a server being edited
      if (server && onUpdateConnectionStatus && connectionStatus) {
        onUpdateConnectionStatus(server.serverName, connectionStatus);
      }
      setIsTesting(false);
    }
  };

  const serverNameError = isEmpty(serverName) || !serverNamePattern.test(serverName);
  const serverNameDuplicateError = serverName && existingServerNames.includes(serverName) && (!server || server.serverName !== serverName);

  return (
    <Modal
      title={server ? "Edit MCP Server" : "Add MCP Server"}
      open={isOpen}
      onCancel={onClose}
      footer={[
        <Button key="test" onClick={handleTestConnection} loading={isTesting}>
          Test Connection
        </Button>,
        <Button key="save" type="primary" onClick={handleSave} loading={isSaving}>
          {server ? "Update Server" : "Add Server"}
        </Button>,
      ]}
      width={600}
      className="max-h-[75vh] p-0 overflow-y-auto"
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
              <Tooltip title={
                serverNameError ? 'Server Name is required and can only contain letters and numbers.' :
                serverNameDuplicateError ? 'Server name already exists.' : ''
              } open={serverNameError || serverNameDuplicateError ? undefined : false}>
                <Form.Item label="Server Name" required>
                  <Input
                    value={serverName}
                    placeholder="Server Name"
                    status={serverNameError || serverNameDuplicateError ? 'error' : ''}
                    onChange={e => setServerName(e.target.value)}
                    maxLength={50}
                    showCount
                  />
                </Form.Item>
              </Tooltip>
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
            >
              <Input
                value={formAgentName}
                onChange={e => setFormAgentName(e.target.value)}
                placeholder="Auto-generated from server name"
                maxLength={100}
                showCount
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
