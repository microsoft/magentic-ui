import React, { useEffect } from "react";
import { Input, Form, Button, Flex, Collapse } from "antd";
import { ModelConfigFormProps, AzureModelConfig } from "./types";

export const DEFAULT_AZURE: AzureModelConfig = {
  provider: "AzureOpenAIChatCompletionClient",
  config: {
    model: "gpt-4o",
    azure_endpoint: "",
    azure_deployment: "",
    api_version: "2024-10-21",
    max_retries: 10,
  }
};

export const AzureModelConfigForm: React.FC<ModelConfigFormProps> = ({ onChange, onSubmit, value }) => {
  const [form] = Form.useForm();
  const handleValuesChange = (_: any, allValues: any) => {
    const newValue = { ...DEFAULT_AZURE, config: { ...DEFAULT_AZURE.config, ...allValues.config } };
    if (onChange) onChange(newValue);
  };
  const handleSubmit = () => {
    const newValue = { ...DEFAULT_AZURE, config: { ...DEFAULT_AZURE.config, ...form.getFieldsValue().config } };
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
          <Form.Item label="Model" name={["config", "model"]}>
            <Input />
          </Form.Item>
          <Form.Item label="Azure Endpoint" name={["config", "azure_endpoint"]}>
            <Input />
          </Form.Item>
          <Form.Item label="Azure Deployment" name={["config", "azure_deployment"]}>
            <Input />
          </Form.Item>
          <Form.Item label="API Version" name={["config", "api_version"]}>
            <Input />
          </Form.Item>
        </Flex>
        <Collapse>
          <Collapse.Panel key="1" header="Optional Properties">
            <Flex gap="small" wrap justify="space-between">
              <Form.Item label="Max Retries" name={["config", "max_retries"]}>
                <Input type="number" />
              </Form.Item>
            </Flex>
          </Collapse.Panel>
        </Collapse>
        {onSubmit && <Button onClick={handleSubmit}>Save</Button>}
      </Flex>
    </Form>
  );
};