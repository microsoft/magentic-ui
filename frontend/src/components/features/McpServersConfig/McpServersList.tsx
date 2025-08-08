import React, { useEffect, useState } from "react";
import { settingsAPI } from "../../views/api";
import { appContext } from "../../../hooks/provider";
import { MCPAgentConfig } from "../../settings/tabs/agentSettings/mcpAgentsSettings/types";
import { Typography, Spin, Alert, Empty, Card, Button } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import McpServerCard from "./McpServerCard";
import McpConfigModal from "./McpConfigModal";
import { MCPServerInfo } from "./types";

const { Title, Text } = Typography;

// Add MCP Server Card Component
const AddMcpServerCard: React.FC<{ onClick: () => void }> = ({ onClick }) => (
  <Card
    className="h-full border-2 border-dashed border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500 transition-colors cursor-pointer bg-gray-50 dark:bg-gray-800"
    onClick={onClick}
  >
    <div className="flex flex-col items-center justify-center h-full py-8">
      <PlusOutlined className="text-4xl text-gray-400 dark:text-gray-500 mb-4" />
      <Title level={4} className="text-gray-600 dark:text-gray-400 mb-2">
        Add MCP Server
      </Title>
      <Text className="text-gray-500 dark:text-gray-500 text-center">
        Connect new capabilities to your agent
      </Text>
    </div>
  </Card>
);

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

        // Extract MCP servers from settings
        const mcpAgentConfigs: MCPAgentConfig[] = settings.mcp_agent_configs || [];

        // Flatten all MCP servers from all agents
        const servers: MCPServerInfo[] = [];

        mcpAgentConfigs.forEach((agent) => {
          agent.mcp_servers.forEach((server) => {
            servers.push({
              agentName: agent.name,
              agentDescription: agent.description,
              serverName: server.server_name,
              serverType: server.server_params.type,
              serverParams: server.server_params,
            });
          });
        });

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

  const handleSaveServer = async (agentConfig: any) => {
    if (!user?.email || !settings) {
      console.error("User not authenticated or settings not loaded");
      return;
    }

    try {
      let updatedAgentConfigs;

      if (editingServer) {
        // Editing existing server - update only the specific server within the agent
        updatedAgentConfigs = settings.mcp_agent_configs.map((agent: MCPAgentConfig): MCPAgentConfig => {
          if (agent.name === editingServer.agentName) {
            // Find and update the specific server within this agent
            const updatedServers = agent.mcp_servers.map((server: any) => {
              if (server.server_name === editingServer.serverName) {
                // Update this server with the new configuration
                return agentConfig.serverConfig; // The new server config from the form
              }
              return server;
            });

            return {
              ...agent,
              name: agentConfig.agentName || agent.name,
              description: agentConfig.agentDescription || agent.description,
              mcp_servers: updatedServers
            };
          }
          return agent;
        });
      } else {
        // Adding new server
        updatedAgentConfigs = [...(settings.mcp_agent_configs || []), agentConfig];
      }

      const updatedSettings = {
        ...settings,
        mcp_agent_configs: updatedAgentConfigs
      };

      // Save to database
      await settingsAPI.updateSettings(user.email, updatedSettings);

      // Update local state
      setSettings(updatedSettings);

      // Refresh the servers list
      const newServers: MCPServerInfo[] = [];
      updatedAgentConfigs.forEach((agent: MCPAgentConfig) => {
        agent.mcp_servers.forEach((server: any) => {
          newServers.push({
            agentName: agent.name,
            agentDescription: agent.description,
            serverName: server.server_name,
            serverType: server.server_params.type,
            serverParams: server.server_params,
          });
        });
      });
      setMcpServers(newServers);

      handleCloseConfigModal();
    } catch (error) {
      console.error("Failed to save MCP server:", error);
      setError(error instanceof Error ? error.message : "Failed to save MCP server");
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
      <Text className="text-gray-600 dark:text-gray-400 mb-4 block">
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
        existingServerNames={mcpServers.map(server => server.serverName)}
      />
    </div>
  );
};

export default McpServersList;
