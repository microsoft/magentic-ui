import React, { useEffect } from "react";
import { Input, Form, Button, Switch, Row, Col } from "antd";
import { ModelConfigFormProps } from "./ModelConfigForms";

export const DEFAULT_OPENAI = {
  provider: "OpenAIChatCompletionClient",
  config: {
    model: "gpt-4.1-2025-04-14",
    api_key: null,
    base_url: null,
    model_info: {
      vision: true,
      function_calling: true, // required true for file_surfer, but will still work if file_surfer is not needed
      json_output: false,
      family: "unknown",
      structured_output: false,
    },
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
      <Row gutter={16}>
        <Col xs={24} sm={12}>
          <Form.Item label="Model" name={["config", "model"]} rules={[{ required: true, message: "Please enter the model name" }]}>
            <Input />
          </Form.Item>
        </Col>
        <Col xs={24} sm={12}>
          <Form.Item label="API Key" name={["config", "api_key"]} rules={[{ required: false, message: "Please enter your OpenAI API key" }]}>
            <Input />
          </Form.Item>
        </Col>
        <Col xs={24} sm={12}>
          <Form.Item label="Base URL" name={["config", "base_url"]} rules={[{ required: false, message: "Please enter your OpenAI API key" }]}>
            <Input />
          </Form.Item>
        </Col>
        <Col xs={24} sm={12}>
          <Form.Item label="Family" name={["config", "model_info", "family"]}>
            <Input />
          </Form.Item>
        </Col>
        <Col xs={24} sm={12}>
          <Form.Item label="Max Retries" name={["config", "max_retries"]} rules={[{ type: "number", min: 1, max: 20, message: "Enter a value between 1 and 20" }]}>
            <Input type="number" />
          </Form.Item>
        </Col>
      </Row>

      <Row gutter={16}>
        <Col xs={24} sm={12}>
          <Form.Item label="Vision" name={["config", "model_info", "vision"]} valuePropName="checked">
            <Switch />
          </Form.Item>
        </Col>
        <Col xs={24} sm={12}>
          <Form.Item label="Function Calling" name={["config", "model_info", "function_calling"]} valuePropName="checked">
            <Switch />
          </Form.Item>
        </Col>
        <Col xs={24} sm={12}>
          <Form.Item label="JSON Output" name={["config", "model_info", "json_output"]} valuePropName="checked">
            <Switch />
          </Form.Item>
        </Col>
        <Col xs={24} sm={12}>
          <Form.Item label="Structured Output" name={["config", "model_info", "structured_output"]} valuePropName="checked">
            <Switch />
          </Form.Item>
        </Col>
      </Row>
      {onSubmit && <Button onClick={handleSubmit}>Save</Button>}
    </Form>
  );
};