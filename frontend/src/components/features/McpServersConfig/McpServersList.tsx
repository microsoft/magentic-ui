import React, { useEffect, useState } from "react";
import { settingsAPI } from "../../views/api";
import { appContext } from "../../../hooks/provider";
import { MCPAgentConfig } from "../../settings/tabs/agentSettings/mcpAgentsSettings/types";
import { Typography, Spin, Alert, Empty } from "antd";
import McpServerCard from "./McpServerCard";
import { MCPServerInfo } from "./types";

const { Title, Text } = Typography;

const McpServersList: React.FC = () => {
  const { user } = React.useContext(appContext);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mcpServers, setMcpServers] = useState<MCPServerInfo[]>([]);
  const [settings, setSettings] = useState<any>(null);

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
        <Empty
          description="No MCP servers configured"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {mcpServers.map((server, index) => (
            <McpServerCard
              key={`${server.agentName}-${server.serverName}-${index}`}
              server={server}
              index={index}
              onDelete={handleDeleteServer}
            />
          ))}
        </div>
      )}
    </div>
  );
};

export default McpServersList;
