import React, { useEffect } from "react";
import { Input, Form, Button, Switch, Flex, Collapse } from "antd";
import { ModelConfigFormProps, OpenAIModelConfig } from "./types";

export const DEFAULT_OPENAI: OpenAIModelConfig = {
  provider: "OpenAIChatCompletionClient",
  config: {
    model: "gpt-4.1-2025-04-14",
    api_key: null,
    base_url: null,
    max_retries: 5,
  }
};

export const OpenAIModelConfigForm: React.FC<ModelConfigFormProps> = ({ onChange, onSubmit, value }) => {
  const [form] = Form.useForm();
  const handleValuesChange = (_: any, allValues: any) => {
    const newValue = { ...DEFAULT_OPENAI, config: { ...DEFAULT_OPENAI.config, ...allValues.config } };
    if (onChange) onChange(newValue);
  };
  const handleSubmit = () => {
    const newValue = { ...DEFAULT_OPENAI, config: { ...DEFAULT_OPENAI.config, ...form.getFieldsValue().config } };
    if (onSubmit) onSubmit(newValue);
  };
  useEffect(() => {
    if (value) {
      form.setFieldsValue(value);
    }
  }, [value, value?.config, form]);

  return (
    <Form
      form={form}
      initialValues={value || DEFAULT_OPENAI}
      onFinish={handleSubmit}
      onValuesChange={handleValuesChange}
      layout="vertical"
    >
      <Flex vertical gap="small">
        <Form.Item label="Model" name={["config", "model"]} rules={[{ required: true, message: "Please enter the model name" }]}>
          <Input />
        </Form.Item>
        <Collapse>
          <Collapse.Panel key="1" header="Optional Properties">
            <Form.Item label="API Key" name={["config", "api_key"]} rules={[{ required: false, message: "Please enter your OpenAI API key" }]}>
              <Input />
            </Form.Item>
            <Form.Item label="Base URL" name={["config", "base_url"]} rules={[{ required: false, message: "Please enter your OpenAI API key" }]}>
              <Input />
            </Form.Item>
            <Form.Item label="Max Retries" name={["config", "max_retries"]} rules={[{ type: "number", min: 1, max: 20, message: "Enter a value between 1 and 20" }]}>
              <Input type="number" />
            </Form.Item>
          </Collapse.Panel>
        </Collapse>
        {onSubmit && <Button onClick={handleSubmit}>Save</Button>}
      </Flex>
    </Form>
  );
};