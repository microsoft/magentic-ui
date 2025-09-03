import React, { useEffect, useState } from "react";
import { settingsAPI } from "../../views/api";
import { appContext } from "../../../hooks/provider";
import { Typography, Spin, Alert, Empty, Card, Button } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import McpServerCard from "./McpServerCard";
import McpConfigModal from "./McpConfigModal";
import { MCPAgentConfig, MCPServerInfo, NamedMCPServerConfig, NamedMCPServerConfigSchema, MCPAgentConfigSchema } from "./types";

const { Title, Text } = Typography;

// Add MCP Server Card Component
const AddMcpServerCard: React.FC<{ onClick: () => void }> = ({ onClick }) => (
  <Card
    className="h-full border-2 border-dashed border-gray-300 dark:border-gray-600 hover:border-gray-400 transition-colors cursor-pointer bg-gray-50"
    onClick={onClick}
  >
    <div className="flex flex-col items-center justify-center h-full py-8">
      <PlusOutlined className="text-4xl text-gray-400 dark:text-gray-500 mb-4" />
      <div className="text-lg font-semibold text-gray-900 mb-2">
        Add MCP Server
      </div>
      <Text className="text-gray-500 dark:text-gray-500 text-center">
        Connect new capabilities to your agent
      </Text>
    </div>
  </Card>
);


// Helper function: Extract MCP servers from agent configurations
export const extractMcpServers = (agents: MCPAgentConfig[]): MCPServerInfo[] => {
  const serversList: MCPServerInfo[] = [];

  agents.forEach((agent) => {
    agent.mcp_servers.forEach((server: NamedMCPServerConfig) => {
      serversList.push({
        agentName: agent.name,
        agentDescription: agent.description,
        serverName: server.server_name,
        serverType: server.server_params.type,
        serverParams: server.server_params,
        connectionStatus: server.connection_status ? {
          isConnected: server.connection_status.is_connected,
          toolsFound: server.connection_status.tools_found,
        } : undefined,
      });
    });
  });

  return serversList;
};

const McpServersList: React.FC = () => {
  const { user } = React.useContext(appContext);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mcpServers, setMcpServers] = useState<MCPServerInfo[]>([]);
  const [settings, setSettings] = useState<any>(null);
  const [isConfigModalOpen, setIsConfigModalOpen] = useState(false);
  const [editingServer, setEditingServer] = useState<MCPServerInfo | undefined>();

  useEffect(() => {
    const fetchMCPServers = async () => {
      if (!user?.email) {
        setError("User not authenticated");
        setIsLoading(false);
        return;
      }

      try {
        setIsLoading(true);
        setError(null);

        // Get user's latest settings from database
        const settings = await settingsAPI.getSettings(user.email);
        setSettings(settings);

        const mcpAgentConfigs: MCPAgentConfig[] = settings.mcp_agent_configs || [];

        const servers = extractMcpServers(mcpAgentConfigs);

        setMcpServers(servers);
      } catch (err) {
        console.error("Failed to fetch MCP servers:", err);
        setError(err instanceof Error ? err.message : "Failed to fetch MCP servers");
      } finally {
        setIsLoading(false);
      }
    };

    fetchMCPServers();
  }, [user?.email]);

  const handleDeleteServer = async (serverToDelete: MCPServerInfo) => {
    if (!user?.email || !settings) {
      console.error("User not authenticated or settings not loaded");
      return;
    }

    try {
      // Find the agent that contains this server
      const updatedAgentConfigs: MCPAgentConfig[] = settings.mcp_agent_configs.map((agent: MCPAgentConfig) => {
        if (agent.name === serverToDelete.agentName) {
          // Remove the server from this agent
          const updatedServers = agent.mcp_servers.filter(
            (server) => server.server_name !== serverToDelete.serverName
          );

          return {
            ...agent,
            mcp_servers: updatedServers
          };
        }
        return agent;
      }).filter((agent: MCPAgentConfig) => {
        // Remove agents that have no servers left (since agents require at least one MCP server)
        return agent.mcp_servers.length > 0
      });

      const updatedSettings = {
        ...settings,
        mcp_agent_configs: updatedAgentConfigs
      };

      // Save to database
      await settingsAPI.updateSettings(user.email, updatedSettings);

      // Update local state
      setSettings(updatedSettings);

      // Update the servers list - remove the deleted server
      const updatedServers = mcpServers.filter((server) =>
        !(server.agentName === serverToDelete.agentName && server.serverName === serverToDelete.serverName)
      );
      setMcpServers(updatedServers);
    } catch (error) {
      console.error("Failed to delete MCP server:", error);
      setError(error instanceof Error ? error.message : "Failed to delete MCP server");
    }
  };

  const handleEditServer = (server: MCPServerInfo) => {
    setEditingServer(server);
    setIsConfigModalOpen(true);
  };

  const handleCloseConfigModal = () => {
    setIsConfigModalOpen(false);
    setEditingServer(undefined);
  };

  const handleAddServer = () => {
    setEditingServer(undefined); // Clear any editing state
    setIsConfigModalOpen(true);
  };

  const addAgent = (formData: MCPAgentConfig, settings: any) => {
    return [...(settings.mcp_agent_configs || []), formData];
  };

  const handleSaveServer = async (formData: MCPAgentConfig) => {
    if (!user?.email || !settings) {
      console.error("User not authenticated or settings not loaded");
      return;
    }

    try {
      let updatedSettings;

      if (editingServer) {
        const updatedAgents = settings.mcp_agent_configs.map((agent: MCPAgentConfig) => {
          if (agent.name === editingServer.agentName) {
            return {
              ...agent, // Preserve existing system_message, tool_call_summary_format, model_client
              ...formData, // Override only name, description, mcp_servers from modal
            };
          }
          return agent;
        });
        updatedSettings = { ...settings, mcp_agent_configs: updatedAgents };
      } else {
        // Adding new server/agent - formData is already complete
        const updatedAgents = addAgent(formData, settings);
        updatedSettings = { ...settings, mcp_agent_configs: updatedAgents };
      }

      // Validate the complete agent configuration after merging
      const agentToValidate = editingServer
        ? updatedSettings.mcp_agent_configs.find((agent: MCPAgentConfig) => agent.name === editingServer.agentName)
        : formData;

      const agentValidationResult = MCPAgentConfigSchema.safeParse(agentToValidate);
      if (!agentValidationResult.success) {
        throw new Error(`Agent validation failed: ${agentValidationResult.error.errors.map(err => err.message).join(', ')}`);
      }

      await settingsAPI.updateSettings(user.email, updatedSettings);
      setSettings(updatedSettings);

      const serversList = extractMcpServers(updatedSettings.mcp_agent_configs);
      setMcpServers(serversList);

      handleCloseConfigModal();
    } catch (error) {
      console.error("Failed to save MCP server:", error);
      setError(error instanceof Error ? error.message : "Failed to save MCP server");
    }
  };

  const handleUpdateConnectionStatus = async (serverName: string, connectionStatus: any) => {
    if (!user?.email || !settings) {
      console.error("User not authenticated or settings not loaded");
      return;
    }

    try {
      // Find the agent that contains this server and update its connection status
      const updatedAgents = settings.mcp_agent_configs.map((agent: MCPAgentConfig) => {
        const updatedMcpServers = agent.mcp_servers.map((server: NamedMCPServerConfig) => {
          if (server.server_name === serverName) {
            return {
              ...server,
              connection_status: {
                is_connected: connectionStatus.isConnected,
                tools_found: connectionStatus.toolsFound,
              },
            };
          }
          return server;
        });

        return {
          ...agent,
          mcp_servers: updatedMcpServers,
        };
      });

      const updatedSettings = { ...settings, mcp_agent_configs: updatedAgents };
      await settingsAPI.updateSettings(user.email, updatedSettings);
      setSettings(updatedSettings);

      const serversList = extractMcpServers(updatedSettings.mcp_agent_configs);
      setMcpServers(serversList);
    } catch (error) {
      console.error("Failed to update connection status:", error);
      setError(error instanceof Error ? error.message : "Failed to update connection status");
    }
  };

  if (isLoading) {
    return (
      <div className="p-4">
        <Title level={2}>MCP Servers</Title>
        <div className="flex justify-center items-center h-64">
          <Spin size="large" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4">
        <Title level={2}>MCP Servers</Title>
        <Alert
          message="Error"
          description={error}
          type="error"
          showIcon
        />
      </div>
    );
  }

  return (
    <div className="p-4">
      <Title level={2}>MCP Servers</Title>
      <Text className="text-gray-600 dark:text-gray-300 mb-4 block">
        Manage Model Context Protocol servers to extend your agent's capabilities
      </Text>

      {mcpServers.length === 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <AddMcpServerCard onClick={handleAddServer} />
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {mcpServers.map((server, index) => {
            return (
            <McpServerCard
              key={`${server.agentName}-${server.serverName}-${index}`}
              server={server}
              index={index}
              onEdit={handleEditServer}
              onDelete={handleDeleteServer}
            />
          )})}
          <AddMcpServerCard onClick={handleAddServer} />
        </div>
      )}

      {/* Configuration Modal */}
      <McpConfigModal
        isOpen={isConfigModalOpen}
        onClose={handleCloseConfigModal}
        server={editingServer}
        onSave={handleSaveServer}
        onUpdateConnectionStatus={handleUpdateConnectionStatus}
        existingServerNames={mcpServers.map(server => server.serverName)}
      />
    </div>
  );
};

export default McpServersList;
