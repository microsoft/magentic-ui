import React from "react";
import { Input, Form, Tooltip, Collapse, Flex } from "antd";
import { StdioServerParams } from "./types";

const StdioServerForm: React.FC<{
    value: StdioServerParams;
    idx: number;
    onValueChanged: (idx: number, updated: StdioServerParams) => void;
}> = ({ value, idx, onValueChanged }) => {
    const stdioCommandError = !value.command || value.command.trim() === '';
    
    let command = value.command ?? "";
    if (value.args !== undefined && value.args.length > 0) {
        command = command.concat(" ").concat(value.args.join(" "));
    }
    
    const handleCommandValueChanged: React.ChangeEventHandler<HTMLInputElement> = (event) => {
        const parts = event.target.value?.trimStart().split(" ");
        
        if (parts.length > 1) {
            // Trim the command only if there is an arg. Otherwise you can't type a space.
            parts[0] = parts[0].trim()
        }

        const command = parts.length > 0 ? parts[0] : "";
        const args = parts.length > 1 ? parts.slice(1) : [];


        onValueChanged(idx, {
            ...value,
            command: command,
            args: args
        },
        )
    }

    return (
        <Flex vertical gap="small" style={{width: "100%"}}>
            <Tooltip title={stdioCommandError ? 'Command is required' : 'Provide the command and arguments, e.g. "npx -y mcp-server-fetch"'}>
                <Form.Item label="Command (including args)" required>
                    <Input
                        placeholder="npx -y mcp-server-fetch"
                        value={command}
                        status={stdioCommandError ? 'error' : ''}
                        onChange={handleCommandValueChanged}
                    />
                </Form.Item>
            </Tooltip>
            <Collapse>
                <Collapse.Panel key="1" header={<h1>Optional Properties</h1>}>
                    <Form.Item label="Read Timeout (seconds)">
                        <Input
                            type="number"
                            value={value.read_timeout_seconds}
                            onChange={e =>
                                onValueChanged(idx, {
                                    ...value,
                                    read_timeout_seconds: Number(e.target.value),
                                })
                            }
                        />
                    </Form.Item>
                    <Form.Item label="Working Directory (cwd)">
                        <Input
                            value={value.cwd || ''}
                            onChange={e =>
                                onValueChanged(idx, {
                                    ...value,
                                    cwd: e.target.value,
                                })
                            }
                        />
                    </Form.Item>
                    <Form.Item label="Encoding">
                        <Input
                            value={value.encoding || 'utf-8'}
                            onChange={e =>
                                onValueChanged(idx, {
                                    ...value,
                                    encoding: e.target.value,
                                })
                            }
                        />
                    </Form.Item>
                    <Form.Item label="Encoding Error Handler">
                        <Input
                            value={value.encoding_error_handler || 'strict'}
                            onChange={e =>
                                onValueChanged(idx, {
                                    ...value,
                                    encoding_error_handler: e.target.value as 'strict' | 'ignore' | 'replace',
                                })
                            }
                        />
                    </Form.Item>
                    <Form.Item label="Environment Variables (env)">
                        <Input.TextArea
                            placeholder="KEY1=VALUE1"
                            value={value.env ? Object.entries(value.env).map(([k, v]) => `${k}=${v}`).join('\n') : ''}
                            onChange={e => {
                                const envLines = e.target.value.split('\n').map(line => line.trim()).filter(Boolean);
                                const envObj = envLines.reduce((acc, line) => {
                                    const [k, ...v] = line.split('=');
                                    if (k && v.length > 0) acc[k] = v.join('=');
                                    return acc;
                                }, {} as Record<string, string>);
                                onValueChanged(idx, {
                                    ...value,
                                    env: Object.keys(envObj).length > 0 ? envObj : undefined,
                                });
                            }}
                        />
                    </Form.Item>
                </Collapse.Panel>
            </Collapse>
        </Flex>
    );
};

export default StdioServerForm;
