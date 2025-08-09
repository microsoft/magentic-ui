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
      return `Connected (${server.connectionStatus.toolsFound || 0} tools)`;
    } else {
      return "Connection failed";
    }
  };

  return (
    <Card
      key={`${server.agentName}-${server.serverName}-${index}`}
      className="h-full border border-gray-200 dark:border-gray-700 hover:shadow-md transition-shadow"
    >
      <div className="space-y-3">
        <div className="flex items-start justify-between">
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

        {/* Metadata */}
        <div className="pt-3">
          <div className="space-y-1">
            {server.agentDescription && (
              <div>
                <Text className="text-gray-700 dark:text-gray-300 text-right">
                  {server.agentDescription}
                </Text>
              </div>
            )}
          </div>
        </div>

        {/* Action buttons at the bottom */}
        <div className="flex items-center justify-end gap-2 pt-3 border-t border-gray-200 dark:border-gray-700">
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
