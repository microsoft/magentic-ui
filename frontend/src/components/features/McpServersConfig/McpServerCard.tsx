import React from "react";
import { Card, Typography, Button, Tag, Tooltip } from "antd";
import { CheckCircleOutlined, CloseCircleOutlined, ClockCircleOutlined } from "@ant-design/icons";
import { MCPServerInfo } from "./types";

const { Title, Text } = Typography;

interface McpServerCardProps {
  server: MCPServerInfo;
  index: number;
  onEdit?: (server: MCPServerInfo) => void;
  onDelete?: (server: MCPServerInfo) => void;
}

const McpServerCard: React.FC<McpServerCardProps> = ({ server, index, onEdit, onDelete }) => {
  const DESCRIPTION_CHAR_LIMIT = 100;

  const truncateText = (text: string, limit: number) => {
    if (text.length <= limit) return text;
    return text.substring(0, limit) + "...";
  };

  const getServerTypeLabel = (serverType: string) => {
    switch (serverType) {
      case "StdioServerParams":
        return "Stdio";
      case "SseServerParams":
        return "SSE";
      default:
        return "Unknown";
    }
  };

  const getConnectionStatusIcon = () => {
    if (!server.connectionStatus) {
      return <ClockCircleOutlined className="text-gray-400" />;
    }

    if (server.connectionStatus.isConnected) {
      return <CheckCircleOutlined className="text-green-500" />;
    } else {
      return <CloseCircleOutlined className="text-red-500" />;
    }
  };

  const getConnectionStatusText = () => {
    if (!server.connectionStatus) {
      return "Not tested";
    }

    if (server.connectionStatus.isConnected) {
      return `Test found ${server.connectionStatus.toolsFound || 0} tools`;
    } else {
      return "Test failed";
    }
  };

  return (
    <Card
      key={`${server.agentName}-${server.serverName}-${index}`}
      className="border border-gray-200 dark:border-gray-700 hover:shadow-md transition-shadow"
    >
      <div className="flex flex-col h-full">
        <div className="flex items-start justify-between mb-3">
          <div>
            <Title level={4} className="text-gray-900 dark:text-gray-100 mb-1">
              {server.serverName}
            </Title>
            <Tag className="text-xs">
              {getServerTypeLabel(server.serverType)}
            </Tag>
          </div>
          <Tooltip title={getConnectionStatusText()}>
            {getConnectionStatusIcon()}
          </Tooltip>
        </div>

        <div className="h-12 mb-3 overflow-hidden">
          {server.agentDescription ? (
            <Text className="text-gray-700 dark:text-gray-300 text-sm leading-6 line-clamp-2">
              {truncateText(server.agentDescription, DESCRIPTION_CHAR_LIMIT)}
            </Text>
          ) : (
            <Text className="text-gray-500 dark:text-gray-400 text-sm italic leading-6">
              No description available
            </Text>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 pt-3 border-t border-gray-200 dark:border-gray-700 mt-auto">
          <Button
            type="text"
            size="small"
            className="rounded-md hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors"
            onClick={() => onEdit?.(server)}
          >
            Edit
          </Button>
          <Button
            type="text"
            size="small"
            danger
            className="rounded-md hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
            onClick={() => onDelete?.(server)}
          >
            Remove
          </Button>
        </div>
      </div>
    </Card>
  );
};

export default McpServerCard;
