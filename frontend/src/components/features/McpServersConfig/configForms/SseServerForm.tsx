import React, { useState, useEffect } from "react";
import { Input, Form, Tooltip, Collapse, Flex } from "antd";
import { SseServerParams } from "../types";

const SseServerForm: React.FC<{
  value: SseServerParams;
  onValueChanged: (updated: SseServerParams) => void;
}> = ({ value, onValueChanged }) => {
  const [hasInteracted, setHasInteracted] = useState(false);
  const [initialUrl, setInitialUrl] = useState("");
  const sseUrlError = hasInteracted && (!value.url || value.url.trim() === '');

  // Track when user has interacted with URL field
  useEffect(() => {
    if (value.url !== initialUrl) {
      setHasInteracted(true);
    }
  }, [value.url, initialUrl]);

  // Set initial URL when value changes (form reset)
  useEffect(() => {
    setInitialUrl(value.url || "");
    setHasInteracted(false);
  }, [value.url]);

  return (
    <Flex vertical gap="small">
      <Tooltip title={sseUrlError ? 'URL is required' : ''} open={sseUrlError ? undefined : false}>
        <Form.Item label="URL" required>
          <Input
            placeholder="http://localhost:8000/sse"
            value={value.url}
            status={sseUrlError ? 'error' : ''}
            onChange={e =>
              onValueChanged({
                ...value,
                url: e.target.value,
              })
            }
          />
        </Form.Item>
      </Tooltip>
      <Collapse>
        <Collapse.Panel key="1" header={<h1>Optional Properties</h1>}>
          <Form.Item label="Headers (JSON)">
            <Input
              value={JSON.stringify(value.headers || {})}
              onChange={e => {
                let val = {};
                try {
                  val = JSON.parse(e.target.value);
                } catch { }
                onValueChanged({
                  ...value,
                  headers: val,
                });
              }}
            />
          </Form.Item>
          <Form.Item label="Timeout (seconds)">
            <Input
              type="number"
              value={value.timeout}
              onChange={e =>
                onValueChanged({
                  ...value,
                  timeout: Number(e.target.value),
                })
              }
            />
          </Form.Item>
          <Form.Item label="SSE Read Timeout (seconds)">
            <Input
              type="number"
              value={value.sse_read_timeout}
              onChange={e =>
                onValueChanged({
                  ...value,
                  sse_read_timeout: Number(e.target.value),
                })
              }
            />
          </Form.Item>
        </Collapse.Panel>
      </Collapse>
    </Flex>
  );
};

export default SseServerForm;
