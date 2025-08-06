import React from "react";
import { Card, Typography, Button, Tag } from "antd";
import { MCPServerInfo } from "./types";

const { Title, Text } = Typography;

interface McpServerCardProps {
  server: MCPServerInfo;
  index: number;
  onDelete?: (server: MCPServerInfo) => void;
}

const McpServerCard: React.FC<McpServerCardProps> = ({ server, index, onDelete }) => {
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

  return (
    <Card
      key={`${server.agentName}-${server.serverName}-${index}`}
      className="h-full border border-gray-200 dark:border-gray-700 hover:shadow-md transition-shadow"
    >
      <div className="space-y-3">
        <div>
          <Title level={4} className="text-gray-900 dark:text-gray-100 mb-1">
            {server.serverName}
          </Title>
          <Tag className="text-xs">
            {getServerTypeLabel(server.serverType)}
          </Tag>
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
