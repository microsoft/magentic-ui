import React, { useEffect } from "react";
import { Input, Form, Button, Switch, Row, Col } from "antd";
import { ModelConfigFormProps } from "./ModelConfigForms";

export const DEFAULT_OLLAMA = {
  provider: "autogen_ext.models.ollama.OllamaChatCompletionClient",
  config: {
    model: "qwen2.5vl:32b",
    host: "http://localhost:11434",
    model_info: {
      vision: true,
      function_calling: true,
      json_output: false,
      family: "unknown",
      structured_output: false,
      max_retries: 5,
    }
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
      <Row gutter={16}>
        <Col xs={24} sm={12}>
          <Form.Item label="Model" name={["config", "model"]}>
            <Input />
          </Form.Item>
        </Col>
        <Col xs={24} sm={12}>
          <Form.Item label="Host" name={["config", "host"]}>
            <Input />
          </Form.Item>
        </Col>
        <Col xs={24} sm={12}>
          <Form.Item label="Family" name={["config", "model_info", "family"]}>
            <Input />
          </Form.Item>
        </Col>
        <Col xs={24} sm={12}>
          <Form.Item label="Max Retries" name={["config", "model_info", "max_retries"]}>
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