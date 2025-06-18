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
  structured_output: false,
};

function normalizeConfig(config: any, hideAdvancedToggles?: boolean) {
  const newConfig = { ...config };
  if (hideAdvancedToggles) {
    if (newConfig.model_info) delete newConfig.model_info;
  } else {
    newConfig.model_info = {
      ...ADVANCED_DEFAULTS,
      ...(newConfig.model_info || {})
    };
  }
  return newConfig;
}

export const OpenAIModelConfigForm: React.FC<ModelConfigFormProps> = ({ onChange, onSubmit, value, hideAdvancedToggles }) => {
  const [form] = Form.useForm();
  const handleValuesChange = (_: any, allValues: any) => {
    const mergedConfig = { ...DEFAULT_OPENAI.config, ...allValues.config };
    const normalizedConfig = normalizeConfig(mergedConfig, hideAdvancedToggles);
    const newValue = { ...DEFAULT_OPENAI, config: normalizedConfig };
    if (onChange) onChange(newValue);
  };
  const handleSubmit = () => {
    const mergedConfig = { ...DEFAULT_OPENAI.config, ...form.getFieldsValue().config };
    const normalizedConfig = normalizeConfig(mergedConfig, hideAdvancedToggles);
    const newValue = { ...DEFAULT_OPENAI, config: normalizedConfig };
    if (onSubmit) onSubmit(newValue);
  };
  useEffect(() => {
    if (value) {
      form.setFieldsValue(value);
      // If advanced toggles are shown, ensure defaults are set in the form if missing
      if (!hideAdvancedToggles) {
        const modelInfo: Record<string, any> = value.config?.model_info || {};
        const needsUpdate = (Object.keys(ADVANCED_DEFAULTS) as (keyof typeof ADVANCED_DEFAULTS)[]).some(
          key => modelInfo[key] === undefined
        );
        if (needsUpdate) {
          form.setFieldsValue({
            config: {
              ...value.config,
              model_info: {
                ...ADVANCED_DEFAULTS,
                ...modelInfo
              }
            }
          });
        }
      }
    } else if (!hideAdvancedToggles) {
      // If no value, set defaults for advanced toggles
      form.setFieldsValue({
        config: {
          ...DEFAULT_OPENAI.config,
          model_info: { ...ADVANCED_DEFAULTS }
        }
      });
    }
  }, [value, value?.config, form, hideAdvancedToggles]);

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
            { !hideAdvancedToggles && (
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
              </Flex>
            )}
          </Collapse.Panel>
        </Collapse>
        {onSubmit && <Button onClick={handleSubmit}>Save</Button>}
      </Flex>
    </Form>
  );
};