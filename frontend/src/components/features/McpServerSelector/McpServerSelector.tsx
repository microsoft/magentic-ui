import React, { useMemo, useCallback } from "react";
import { Select, Typography, type SelectProps, Divider, Button, Flex, Tooltip } from "antd";
import { MCPServerInfo } from "../McpServersConfig/types"
import {
    PlusIcon, WrenchScrewdriverIcon
} from "@heroicons/react/24/outline";
import "./McpServerSelector.css";

interface McpServerSelectorProps {
    servers: MCPServerInfo[]
    onAddMcpServer: () => void;
    runStatus?: string
    value: string[]
    onChange: (value: string[]) => void
}

type OptionsProps = SelectProps["options"]

export const McpServerSelector: React.FC<McpServerSelectorProps> = ({ servers, onAddMcpServer, runStatus, value, onChange }) => {
    const disabled = runStatus !== "created"
    let mcpSelectorPrefixClassNames = "mcp-selector-prefix"
    if (disabled) {
        mcpSelectorPrefixClassNames += " disabled"
    }

    const handleChange = (newValue: string[]) => {
        onChange(newValue)
    }

    const handleAddServer = useCallback(() => {
        onAddMcpServer();
    }, [onAddMcpServer])

    const options: OptionsProps = useMemo(() => {
        return servers.map((server) => ({
            value: server.agentName,
            label: server.agentName
        }))
    }, [servers])

    const selectComponent = (
        <Select
            mode="multiple"
            disabled={disabled}
            showSearch={false}
            value={value}
            onChange={handleChange}
            options={options}
            className="mcp-selector"
            prefix={<WrenchScrewdriverIcon width={22} />}
            suffixIcon={null}
            popupMatchSelectWidth={false}
            maxTagCount={0}
            popupRender={(menu) => (
                <>
                    {menu}
                    <Divider style={{ margin: '8px 0' }} />
                    <Button
                        type="text"
                        onClick={handleAddServer}
                        style={{ width: '100%', padding: '0px 12px', marginBottom: "6px" }}
                        className="mcp-selector-add-mcp-server-button"
                    >
                        <Flex gap={4}>
                            <PlusIcon width={16} />
                            <span>Add MCP Server</span>
                        </Flex>
                    </Button>
                </>
            )}
            classNames={{
                popup: {
                    root: "mcp-selector-dropdown"
                }
            }}
        />
    )

    return disabled ? (
        <Tooltip title="You cannot modify tools after starting a session">
            {selectComponent}
        </Tooltip>
    ) : (
        selectComponent
    )
}       