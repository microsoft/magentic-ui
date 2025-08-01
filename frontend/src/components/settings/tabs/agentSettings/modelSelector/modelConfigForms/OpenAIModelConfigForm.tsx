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

const ADVANCED_DEFAULTS = {
  vision: true,
  function_calling: true,
  json_output: false,
  family: "unknown" as const,
  structured_output: false,
  multiple_system_messages: false,
};

function normalizeConfig(config: any, hideAdvancedToggles?: boolean) {
  const newConfig = { ...DEFAULT_OPENAI, ...config };
  if (hideAdvancedToggles) {
    if (newConfig.config.model_info) delete newConfig.config.model_info;
  } else {
    newConfig.config.model_info = {
      ...ADVANCED_DEFAULTS,
      ...(newConfig.config.model_info || {})
    };
  }
  return newConfig;
}


export const OpenAIModelConfigForm: React.FC<ModelConfigFormProps> = ({ onChange, onSubmit, value, hideAdvancedToggles }) => {
  const [form] = Form.useForm();
  const baseUrl = Form.useWatch(['config', 'base_url'], form);

  const shouldHideAdvanced = (config: any) => {
    return hideAdvancedToggles && !(config?.base_url && config.base_url.trim() !== '');
  };

  const handleValuesChange = (_: any, allValues: any) => {
    const mergedConfig = { ...DEFAULT_OPENAI.config, ...allValues.config };
    const normalizedConfig = normalizeConfig(mergedConfig, shouldHideAdvanced(mergedConfig));
    const newValue = { ...DEFAULT_OPENAI, config: normalizedConfig };
    if (onChange) onChange(newValue);
  };
  const handleSubmit = () => {
    const mergedConfig = { ...DEFAULT_OPENAI.config, ...form.getFieldsValue().config };
    const normalizedConfig = normalizeConfig(mergedConfig, shouldHideAdvanced(mergedConfig));
    const newValue = { ...DEFAULT_OPENAI, config: normalizedConfig };
    if (onSubmit) onSubmit(newValue);
  };


  useEffect(() => {
    if (value) {
      form.setFieldsValue(normalizeConfig(value, shouldHideAdvanced(value.config)))
    }
  }, [value, form, hideAdvancedToggles]);

  return (
    <Form
      form={form}
      initialValues={normalizeConfig(value, shouldHideAdvanced(value?.config))}
      onFinish={handleSubmit}
      onValuesChange={handleValuesChange}
      layout="vertical"
    >
      <Flex vertical gap="small">
        <Form.Item label="Model" name={["config", "model"]} rules={[{ required: true, message: "Please enter the model name" }]}>
          <Input />
        </Form.Item>
        <Collapse style={{ width: "100%" }}>
          <Collapse.Panel key="1" header="Optional Properties">
            <Form.Item label="API Key" name={["config", "api_key"]} rules={[{ required: false, message: "Please enter your OpenAI API key" }]}>
              <Input />
            </Form.Item>
            <Form.Item label="Base URL" name={["config", "base_url"]} rules={[{ required: false, message: "Please enter your Base URL" }]}>
              <Input />
            </Form.Item>
            <Form.Item label="Max Retries" name={["config", "max_retries"]} rules={[{ type: "number", min: 1, max: 20, message: "Enter a value between 1 and 20" }]}>
              <Input type="number" />
            </Form.Item>
            {!shouldHideAdvanced({ base_url: baseUrl }) && (
              <Flex gap="small" wrap justify="space-between">
                <Form.Item label="Vision" name={["config", "model_info", "vision"]} valuePropName="checked">
                  <Switch />
                </Form.Item>
                <Form.Item label="Function Calling" name={["config", "model_info", "function_calling"]} valuePropName="checked">
                  <Switch />
                </Form.Item>
                <Form.Item label="JSON Output" name={["config", "model_info", "json_output"]} valuePropName="checked">
                  <Switch />
                </Form.Item>
                <Form.Item label="Structured Output" name={["config", "model_info", "structured_output"]} valuePropName="checked">
                  <Switch />
                </Form.Item>
                <Form.Item label="Multiple System Messages" name={["config", "model_info", "multiple_system_messages"]} valuePropName="checked">
                  <Switch />
                </Form.Item>
              </Flex>
            )}
          </Collapse.Panel>
        </Collapse>
        {onSubmit && <Button onClick={handleSubmit}>Save</Button>}
      </Flex>
    </Form>
  );
};