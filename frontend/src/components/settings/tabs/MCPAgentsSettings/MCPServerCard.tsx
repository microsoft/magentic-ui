import React, { useEffect } from "react";
import { Input, Select, Space, Collapse, Form, Tooltip } from "antd";
import { Button } from "../../../common/Button";

interface McpServerParams {
    type: "StdioServerParams" | "SseServerParams";
    command?: string;
    args?: string[];
    read_timeout_seconds?: number;
    url?: string;
    headers?: Record<string, string>;
    timeout?: number;
    sse_read_timeout?: number;
}

interface NamedMcpServerParams {
    server_name: string;
    server_params: McpServerParams;
    server_description?: string;
}

interface MCPServerCardProps {
    server: NamedMcpServerParams;
    idx: number;
    handleServerChange: (idx: number, updated: NamedMcpServerParams) => void;
    removeServer: (idx: number) => void;
}

const defaultStdioParams: McpServerParams = {
    type: "StdioServerParams",
    command: "npx",
    args: [],
    read_timeout_seconds: 5,
};
const defaultSseParams: McpServerParams = {
    type: "SseServerParams",
    url: "",
    headers: {},
    timeout: 5,
    sse_read_timeout: 300,
};

const MCP_SERVER_TYPES = [
    { value: "StdioServerParams", label: "Stdio" },
    { value: "SseServerParams", label: "SSE" },
];

const isEmpty = (val: any) => val === undefined || val === null || (typeof val === 'string' && val.trim() === '') || (Array.isArray(val) && val.length === 0);


// --- New StdioServerForm component ---
const StdioServerForm: React.FC<{
    server: NamedMcpServerParams;
    idx: number;
    handleServerChange: (idx: number, updated: NamedMcpServerParams) => void;
}> = ({ server, idx, handleServerChange }) => {
    const stdioCommandError = !server.server_params.command || server.server_params.command.trim() === '';
    const stdioArgsError = !server.server_params.args || server.server_params.args.length === 0;

    return (
        <>
            <Tooltip title={stdioCommandError ? 'Command is required' : ''} open={stdioCommandError ? undefined : false}>
                <Form.Item label="Command" required>
                    <Input
                        value={server.server_params.command}
                        status={stdioCommandError ? 'error' : ''}
                        onChange={e =>
                            handleServerChange(idx, {
                                ...server,
                                server_params: {
                                    ...server.server_params,
                                    command: e.target.value,
                                },
                            })
                        }
                    />
                </Form.Item>
            </Tooltip>
            <Tooltip title={stdioArgsError ? 'Args are required' : ''} open={stdioArgsError ? undefined : false}>
                <Form.Item label="Args (space separated)" required>
                    <Input
                        value={server.server_params.args?.join(" ")}
                        status={stdioArgsError ? 'error' : ''}
                        onChange={e =>
                            handleServerChange(idx, {
                                ...server,
                                server_params: {
                                    ...server.server_params,
                                    args: e.target.value.split(" ").map(s => s.trim()).filter(Boolean),
                                },
                            })
                        }
                    />
                </Form.Item>
            </Tooltip>
            <Collapse>
                <Collapse.Panel key="1" header={<h1>Optional Properties</h1>}>
                    <Form.Item label="Read Timeout (seconds)">
                        <Input
                            type="number"
                            value={server.server_params.read_timeout_seconds}
                            onChange={e =>
                                handleServerChange(idx, {
                                    ...server,
                                    server_params: {
                                        ...server.server_params,
                                        read_timeout_seconds: Number(e.target.value),
                                    },
                                })
                            }
                        />
                    </Form.Item>
                </Collapse.Panel>
            </Collapse>
        </>
    );
};

// --- New SseServerForm component ---
const SseServerForm: React.FC<{
    server: NamedMcpServerParams;
    idx: number;
    handleServerChange: (idx: number, updated: NamedMcpServerParams) => void;
}> = ({ server, idx, handleServerChange }) => {
    const sseUrlError = !server.server_params.url || server.server_params.url.trim() === '';

    return (
        <>
            <Tooltip title={sseUrlError ? 'URL is required' : ''} open={sseUrlError ? undefined : false}>
                <Form.Item label="URL" required>
                    <Input
                        value={server.server_params.url}
                        status={sseUrlError ? 'error' : ''}
                        onChange={e =>
                            handleServerChange(idx, {
                                ...server,
                                server_params: {
                                    ...server.server_params,
                                    url: e.target.value,
                                },
                            })
                        }
                    />
                </Form.Item>
            </Tooltip>
            <Collapse>
                <Collapse.Panel key="1" header={<h1>Optional Properties</h1>}>
                    <Form.Item label="Headers (JSON)">
                        <Input
                            value={JSON.stringify(server.server_params.headers || {})}
                            onChange={e => {
                                let val = {};
                                try {
                                    val = JSON.parse(e.target.value);
                                } catch { }
                                handleServerChange(idx, {
                                    ...server,
                                    server_params: {
                                        ...server.server_params,
                                        headers: val,
                                    },
                                });
                            }}
                        />
                    </Form.Item>
                    <Form.Item label="Timeout (seconds)">
                        <Input
                            type="number"
                            value={server.server_params.timeout}
                            onChange={e =>
                                handleServerChange(idx, {
                                    ...server,
                                    server_params: {
                                        ...server.server_params,
                                        timeout: Number(e.target.value),
                                    },
                                })
                            }
                        />
                    </Form.Item>
                    <Form.Item label="SSE Read Timeout (seconds)">
                        <Input
                            type="number"
                            value={server.server_params.sse_read_timeout}
                            onChange={e =>
                                handleServerChange(idx, {
                                    ...server,
                                    server_params: {
                                        ...server.server_params,
                                        sse_read_timeout: Number(e.target.value),
                                    },
                                })
                            }
                        />
                    </Form.Item>
                </Collapse.Panel>
            </Collapse>

        </>
    );
};

const MCPServerCard: React.FC<Omit<MCPServerCardProps, 'MCP_SERVER_TYPES'>> = ({ server, idx, handleServerChange, removeServer }) => {
    const isStdio = server.server_params.type === "StdioServerParams";
    const serverNameError = isEmpty(server.server_name);

    return (
        <Collapse key={idx} defaultActiveKey={["1"]} style={{ width: '100%' }}>
            <Collapse.Panel
                key="1"
                header={
                    <Space style={{ width: '100%' }} align="center">
                        <Tooltip title={serverNameError ? 'Server Name is required' : ''} open={serverNameError ? undefined : false}>
                            <Input
                                value={server.server_name}
                                placeholder={`MCP Server #${idx + 1}`}
                                status={serverNameError ? 'error' : ''}
                                onChange={e => handleServerChange(idx, { ...server, server_name: e.target.value })}
                                style={{ flex: 1 }}
                                onClick={(e) => e.stopPropagation()}
                            />
                        </Tooltip>
                        <Button variant="danger" onClick={(e) => { e.stopPropagation(); removeServer(idx); }}>
                            Remove MCP Server
                        </Button>
                    </Space>
                }
            >
                <Space direction="vertical" style={{ width: "100%" }}>
                    <Form.Item label="Server Type">
                        <Select
                            value={server.server_params.type}
                            onChange={type => {
                                // Reset params to default for the selected type
                                const newParams = type === "StdioServerParams"
                                    ? { ...defaultStdioParams }
                                    : { ...defaultSseParams };
                                handleServerChange(idx, {
                                    ...server,
                                    server_params: newParams,
                                });
                            }}
                            options={MCP_SERVER_TYPES}
                        />
                    </Form.Item>
                    {isStdio ? (
                        <StdioServerForm server={server} idx={idx} handleServerChange={handleServerChange} />
                    ) : (
                        <SseServerForm server={server} idx={idx} handleServerChange={handleServerChange} />
                    )}
                </Space>
            </Collapse.Panel>
        </Collapse>
    );
};

export default MCPServerCard;
