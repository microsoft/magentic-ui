import React from "react";
import { Input, Select, Collapse, Form, Tooltip, Flex, Button } from "antd";
import StdioServerForm from "./StdioServerForm";
import SseServerForm from "./SseServerForm";
import { MCPServerConfig, NamedMCPServerConfig } from "./types";

export const DEFAULT_STDIO_PARAMS: MCPServerConfig = {
    type: "StdioServerParams",
    command: "",
    args: [],
    read_timeout_seconds: 5,
};
export const DEFAULT_SSE_PARAMS: MCPServerConfig = {
    type: "SseServerParams",
    url: "",
    headers: {},
    timeout: 5,
    sse_read_timeout: 300,
};

export const MCP_SERVER_TYPES = {
    "StdioServerParams": { value: "StdioServerParams", label: "Stdio", defaultValue: DEFAULT_STDIO_PARAMS, },
    "SseServerParams": { value: "SseServerParams", label: "SSE", defaultValue: DEFAULT_SSE_PARAMS },
}

const isEmpty = (val: any) => val === undefined || val === null || (typeof val === 'string' && val.trim() === '') || (Array.isArray(val) && val.length === 0);

export interface MCPServerFormProps {
    server: NamedMCPServerConfig;
    idx: number;
    handleServerChange: (idx: number, updated: NamedMCPServerConfig) => void;
    removeServer: (idx: number) => void;
}

const MCPServerForm: React.FC<MCPServerFormProps> = ({ server, idx, handleServerChange, removeServer }) => {
    const serverNamePattern = /^[A-Za-z0-9]+$/;
    const serverNameError = isEmpty(server.server_name) || !serverNamePattern.test(server.server_name);

    // Type guards for server_params
    function isStdioServerParams(params: MCPServerConfig): params is import("./types").StdioServerParams {
        return params.type === "StdioServerParams";
    }
    function isSseServerParams(params: MCPServerConfig): params is import("./types").SseServerParams {
        return params.type === "SseServerParams";
    }

    let ServerForm = undefined;
    if (isStdioServerParams(server.server_params)) {
        ServerForm = (
            <StdioServerForm
                value={server.server_params}
                idx={idx}
                onValueChanged={(_idx, value) => handleServerChange(idx, { ...server, server_params: value })}
            />
        )
    } else if (isSseServerParams(server.server_params)) {
        ServerForm = (
            <SseServerForm
                value={server.server_params}
                idx={idx}
                onValueChanged={(_idx, value) => handleServerChange(idx, { ...server, server_params: value })}
            />
        )
    }


    return (
        <Collapse key={idx} defaultActiveKey={["1"]} style={{width: "100%"}}>
            <Collapse.Panel
                key="1"
                header={
                    <Flex align="center" gap="small">
                        <Tooltip title={serverNameError ? 'Server Name is required and can only contain letters and numbers.' : ''} open={serverNameError ? undefined : false}>
                            <Input
                                value={server.server_name}
                                placeholder={`Server Name e.g. `}
                                status={serverNameError ? 'error' : ''}
                                onChange={e => handleServerChange(idx, { ...server, server_name: e.target.value })}
                                onClick={(e) => e.stopPropagation()}
                            />
                        </Tooltip>
                        <Button danger onClick={(e) => { e.stopPropagation(); removeServer(idx); }}>
                            Remove
                        </Button>
                    </Flex>
                }
            >
                <Flex vertical gap="small">
                    <Form.Item label="Server Type">
                        <Select
                            value={server.server_params.type}
                            onChange={type => {
                                // Reset params to default for the selected type
                                const newParams = MCP_SERVER_TYPES[type]?.defaultValue
                                handleServerChange(idx, {
                                    ...server,
                                    server_params: newParams,
                                });
                            }}
                            options={Object.values(MCP_SERVER_TYPES)}
                        />
                    </Form.Item>
                    {ServerForm}
                </Flex>
            </Collapse.Panel>
        </Collapse>
    );
};

export default MCPServerForm;
