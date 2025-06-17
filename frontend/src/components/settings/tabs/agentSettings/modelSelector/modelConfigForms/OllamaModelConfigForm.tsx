import React, { useEffect } from "react";
import { Input, Form, Button, Switch, Flex, Collapse } from "antd";
import { ModelConfigFormProps, OllamaModelConfig } from "./types";

export const DEFAULT_OLLAMA: OllamaModelConfig = {
  provider: "autogen_ext.models.ollama.OllamaChatCompletionClient",
  config: {
    model: "qwen2.5vl:32b",
    host: "http://localhost:11434",
    max_retries: 5,
  }
};

export const OllamaModelConfigForm: React.FC<ModelConfigFormProps> = ({ onChange, onSubmit, value }) => {
  const [form] = Form.useForm();
  const handleValuesChange = (_: any, allValues: any) => {
    const newValue = { ...DEFAULT_OLLAMA, config: { ...DEFAULT_OLLAMA.config, ...allValues.config } };
    if (onChange) onChange(newValue);
  };
  const handleSubmit = () => {
    const newValue = { ...DEFAULT_OLLAMA, config: { ...DEFAULT_OLLAMA.config, ...form.getFieldsValue().config } };
    if (onSubmit) onSubmit(newValue);
  };
  useEffect(() => {
    if (value) {
      form.setFieldsValue(value);
    }
  }, [value, form]);
  return (
    <Form
      form={form}
      initialValues={value || DEFAULT_OLLAMA}
      onFinish={handleSubmit}
      onValuesChange={handleValuesChange}
      layout="vertical"
    >
      <Flex vertical gap="small">
        <Flex gap="small" wrap justify="space-between">
          <Form.Item label="Model" name={["config", "model"]}>
            <Input />
          </Form.Item>
          <Form.Item label="Host" name={["config", "host"]}>
            <Input />
          </Form.Item>
          <Collapse>
            <Collapse.Panel key={1} header="Optional Properties">
              <Form.Item label="Max Retries" name={["config", "model_info", "max_retries"]}>
                <Input type="number" />
              </Form.Item>
            </Collapse.Panel>
          </Collapse>
        </Flex>
        {onSubmit && <Button onClick={handleSubmit}>Save</Button>}
      </Flex>
    </Form>
  );
};