import React, { useEffect } from "react";
import { Input, Form, Button, Row, Col } from "antd";
import { ModelConfigFormProps } from "./ModelConfigForms";

export const DEFAULT_AZURE = {
  provider: "AzureOpenAIChatCompletionClient",
  config: {
    model: "gpt-4o",
    azure_endpoint: "<YOUR ENDPOINT>",
    azure_deployment: "<YOUR DEPLOYMENT>",
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
      <Row gutter={16}>
        <Col xs={24} sm={12}>
          <Form.Item label="Model" name={["config", "model"]}>
            <Input />
          </Form.Item>
        </Col>
        <Col xs={24} sm={12}>
          <Form.Item label="Azure Endpoint" name={["config", "azure_endpoint"]}>
            <Input />
          </Form.Item>
        </Col>
        <Col xs={24} sm={12}>
          <Form.Item label="Azure Deployment" name={["config", "azure_deployment"]}>
            <Input />
          </Form.Item>
        </Col>
        <Col xs={24} sm={12}>
          <Form.Item label="API Version" name={["config", "api_version"]}>
            <Input />
          </Form.Item>
        </Col>
        <Col xs={24} sm={12}>
          <Form.Item label="Max Retries" name={["config", "max_retries"]}>
            <Input type="number" />
          </Form.Item>
        </Col>
      </Row>
      {onSubmit && <Button onClick={handleSubmit}>Save</Button>}
    </Form>
  );
};