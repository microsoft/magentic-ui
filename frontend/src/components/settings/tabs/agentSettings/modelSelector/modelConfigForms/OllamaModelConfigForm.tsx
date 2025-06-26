import React, { useEffect } from "react";
import { Input, Form, Button, Switch, Flex, Collapse, Select } from "antd";
import { ModelConfigFormProps, ModelFamilySchema, OllamaModelConfig } from "./types";

export const DEFAULT_OLLAMA: OllamaModelConfig = {
  provider: "autogen_ext.models.ollama.OllamaChatCompletionClient",
  config: {
    model: "qwen2.5vl:32b",
    host: "http://localhost:11434",
    max_retries: 5,
  }
};

const ADVANCED_DEFAULTS = {
  vision: true,
  function_calling: true,
  json_output: true,
  family: "unknown" as const,
  structured_output: false,
  multiple_system_messages: false,
};

function normalizeConfig(config: any, hideAdvancedToggles?: boolean) {
  const newConfig = { ...DEFAULT_OLLAMA, ...config };
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

export const OllamaModelConfigForm: React.FC<ModelConfigFormProps> = ({ onChange, onSubmit, value, hideAdvancedToggles }) => {
  const [form] = Form.useForm();

  const handleValuesChange = (_: any, allValues: any) => {
    const mergedConfig = { ...DEFAULT_OLLAMA.config, ...allValues.config };
    const normalizedConfig = normalizeConfig(mergedConfig, hideAdvancedToggles);
    const newValue = { ...DEFAULT_OLLAMA, config: normalizedConfig };
    if (onChange) onChange(newValue);
  };
  const handleSubmit = () => {
    const mergedConfig = { ...DEFAULT_OLLAMA.config, ...form.getFieldsValue().config };
    const normalizedConfig = normalizeConfig(mergedConfig, hideAdvancedToggles);
    const newValue = { ...DEFAULT_OLLAMA, config: normalizedConfig };
    if (onSubmit) onSubmit(newValue);
  };

  useEffect(() => {
    if (value) {
      form.setFieldsValue(normalizeConfig(value, hideAdvancedToggles))
    }
  }, [value, form]);

  return (
    <Form
      form={form}
      initialValues={normalizeConfig(value, hideAdvancedToggles)}
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
          <Collapse style={{ width: "100%" }}>
            <Collapse.Panel key="1" header="Optional Properties">
              <Form.Item label="Max Retries" name={["config", "max_retries"]} rules={[{ type: "number", min: 1, max: 20, message: "Enter a value between 1 and 20" }]}>
                <Input type="number" />
              </Form.Item>
              {!hideAdvancedToggles && (
                <Flex gap="small" wrap justify="space-between">
                  <Form.Item label="Model Family" name={["config", "model_info", "family"]}>
                    <Select placeholder="Select model family" popupMatchSelectWidth={false}>
                      {ModelFamilySchema.options.map((family) => (
                        <Select.Option key={family} value={family}>
                          {family}
                        </Select.Option>
                      ))}
                    </Select>
                  </Form.Item>
                  <Form.Item label="Vision" name={["config", "model_info", "vision"]} valuePropName="checked">
                    <Switch checked={value?.config.model_info?.vision ?? false} />
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
        </Flex>
        {onSubmit && <Button onClick={handleSubmit}>Save</Button>}
      </Flex>
    </Form>
  );
};