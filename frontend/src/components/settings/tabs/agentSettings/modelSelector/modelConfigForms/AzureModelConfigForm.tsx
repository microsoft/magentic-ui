import React, { useEffect } from "react";
import { Input, Form, Button, Flex, Collapse, Switch } from "antd";
import { ModelConfigFormProps, AzureModelConfig } from "./types";

export const DEFAULT_AZURE: AzureModelConfig = {
  provider: "AzureOpenAIChatCompletionClient",
  config: {
    model: "gpt-4o",
    azure_endpoint: "",
    azure_deployment: "",
    api_version: "2024-10-21",
    model_info: {
      vision: true,
      function_calling: true,
      json_output: false,
      structured_output: false,
    },
    max_retries: 10,
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

export const AzureModelConfigForm: React.FC<ModelConfigFormProps> = ({ onChange, onSubmit, value, hideAdvancedToggles }) => {
  const [form] = Form.useForm();
  const handleValuesChange = (_: any, allValues: any) => {
    const mergedConfig = { ...DEFAULT_AZURE.config, ...allValues.config };
    const normalizedConfig = normalizeConfig(mergedConfig, hideAdvancedToggles);
    const newValue = { ...DEFAULT_AZURE, config: normalizedConfig };
    if (onChange) onChange(newValue);
  };
  const handleSubmit = () => {
    const mergedConfig = { ...DEFAULT_AZURE.config, ...form.getFieldsValue().config };
    const normalizedConfig = normalizeConfig(mergedConfig, hideAdvancedToggles);
    const newValue = { ...DEFAULT_AZURE, config: normalizedConfig };
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
      initialValues={value || DEFAULT_AZURE.config}
      onFinish={handleSubmit}
      onValuesChange={handleValuesChange}
      layout="vertical"
    >
      <Flex vertical gap="small">
        <Flex gap="small" wrap justify="space-between">
          <Form.Item required label="Model" name={["config", "model"]}>
            <Input />
          </Form.Item>
          <Form.Item required label="Azure Endpoint" name={["config", "api_key"]}>
            <Input />
          </Form.Item>
          <Form.Item required label="Azure Endpoint" name={["config", "azure_endpoint"]}>
            <Input />
          </Form.Item>
          <Form.Item required label="Azure Deployment" name={["config", "azure_deployment"]}>
            <Input />
          </Form.Item>
          <Form.Item label="API Version" name={["config", "api_version"]}>
            <Input />
          </Form.Item>
        </Flex>
        <Collapse>
          <Collapse.Panel key="1" header="Optional Properties">
            <Form.Item label="Max Retries" name={["config", "max_retries"]} rules={[{ type: "number", min: 1, max: 20, message: "Enter a value between 1 and 20" }]}>
              <Input type="number" />
            </Form.Item>
            {!hideAdvancedToggles && (
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