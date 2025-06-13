import React from "react";
import { Input, Form, Tooltip, Collapse } from "antd";
import { StdioServerParams } from "./types";

const StdioServerForm: React.FC<{
    value: StdioServerParams;
    idx: number;
    onValueChanged: (idx: number, updated: StdioServerParams) => void;
}> = ({ value, idx, onValueChanged }) => {
    const stdioCommandError = !value.command || value.command.trim() === '';
    const stdioArgsError = !value.args || value.args.length === 0;

    return (
        <>
            <Tooltip title={stdioCommandError ? 'Command is required' : ''} open={stdioCommandError ? undefined : false}>
                <Form.Item label="Command" required>
                    <Input
                        value={value.command}
                        status={stdioCommandError ? 'error' : ''}
                        onChange={e =>
                            onValueChanged(idx, {
                                ...value,
                                command: e.target.value,
                            },
                            )
                        }
                    />
                </Form.Item>
            </Tooltip>
            <Tooltip title={stdioArgsError ? 'Args are required' : ''} open={stdioArgsError ? undefined : false}>
                <Form.Item label="Args (space separated)" required>
                    <Input
                        value={value.args?.join(" ")}
                        status={stdioArgsError ? 'error' : ''}
                        onChange={e =>
                            onValueChanged(idx, {
                                ...value,
                                args: e.target.value.split(" ").map(s => s.trim()).filter(Boolean),
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
                            value={value.read_timeout_seconds}
                            onChange={e =>
                                onValueChanged(idx, {
                                    ...value,
                                    read_timeout_seconds: Number(e.target.value),
                                })
                            }
                        />
                    </Form.Item>
                </Collapse.Panel>
            </Collapse>
        </>
    );
};

export default StdioServerForm;
