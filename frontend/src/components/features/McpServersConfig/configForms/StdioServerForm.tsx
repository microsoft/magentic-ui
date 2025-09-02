import React, { useState, useEffect } from "react";
import { Input, Form, Collapse, Flex } from "antd";
import { StdioServerParams } from "../types";

const StdioServerForm: React.FC<{
  value: StdioServerParams;
  onValueChanged: (updated: StdioServerParams) => void;
  resetFlag?: number;
}> = ({ value, onValueChanged, resetFlag }) => {
  const [hasInteracted, setHasInteracted] = useState(false);
  const stdioCommandError = hasInteracted && (!value.command || value.command.trim() === '');

  const [envText, setEnvText] = useState('');

  // Clear error state when component mounts or resetFlag changes
  useEffect(() => {
    setHasInteracted(false);
  }, [resetFlag]);

  useEffect(() => {
    const envTextValue = value.env ? Object.entries(value.env).map(([k, v]) => `${k}=${v}`).join('\n') : '';
    setEnvText(envTextValue);
  }, [value.env]);

  let command = value.command ?? "";
  if (value.args !== undefined && value.args.length > 0) {
    command = command.concat(" ").concat(value.args.join(" "));
  }

  const handleCommandValueChanged: React.ChangeEventHandler<HTMLInputElement> = (event) => {
    setHasInteracted(true);

    const parts = event.target.value?.trimStart().split(" ");

    if (parts.length > 1) {
      // Trim the command only if there is an arg. Otherwise you can't type a space.
      parts[0] = parts[0].trim()
    }

    const command = parts.length > 0 ? parts[0] : "";
    const args = parts.length > 1 ? parts.slice(1) : [];

    onValueChanged({
      ...value,
      command: command,
      args: args
    });
  }

  return (
    <Flex vertical gap="small" style={{width: "100%"}}>
        <Form.Item
          label="Command (including args)"
          required
          validateStatus={stdioCommandError ? 'error' : undefined}
          help={stdioCommandError ? 'Command is required' : undefined}
        >
          <Input
            placeholder="npx -y mcp-server-fetch"
            value={command}
            status={stdioCommandError ? 'error' : undefined}
            onChange={handleCommandValueChanged}
          />
        </Form.Item>
      <Collapse>
        <Collapse.Panel key="1" header={<h1>Optional Properties</h1>}>
          <Form.Item label="Read Timeout (seconds)">
            <Input
              type="number"
              value={value.read_timeout_seconds}
              onChange={e =>
                onValueChanged({
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
                onValueChanged({
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
                onValueChanged({
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
                onValueChanged({
                  ...value,
                  encoding_error_handler: e.target.value as 'strict' | 'ignore' | 'replace',
                })
              }
            />
          </Form.Item>
          <Form.Item label="Environment Variables (env)">
            <Input.TextArea
              placeholder="KEY1=VALUE1"
              value={envText}
              onChange={e => {
                const newEnvText = e.target.value;
                setEnvText(newEnvText);

                const envLines = newEnvText.split('\n').map(line => line.trim()).filter(Boolean);
                const envObj = envLines.reduce((acc, line) => {
                  const [k, ...v] = line.split('=');
                  if (k && v.length > 0) acc[k] = v.join('=');
                  return acc;
                }, {} as Record<string, string>);

                onValueChanged({
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
