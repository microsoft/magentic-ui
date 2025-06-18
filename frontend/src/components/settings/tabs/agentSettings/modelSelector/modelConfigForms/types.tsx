import { z } from "zod";

export const OpenAIModelConfigSchema = z.object({
  provider: z.literal("OpenAIChatCompletionClient"),
  config: z.object({
    model: z.string().min(1, "Model name is required."),
  }).passthrough(),
}).passthrough();

export type OpenAIModelConfig = z.infer<typeof OpenAIModelConfigSchema>;

export const AzureModelConfigSchema = z.object({
  provider: z.literal("AzureOpenAIChatCompletionClient"),
  config: z.object({
    model: z.string().min(1, "Model name is required."),
    azure_endpoint: z.string().min(1, "Azure endpoint is required."),
    azure_deployment: z.string().min(1, "Azure deployment is required."),
  }).passthrough(),
}).passthrough();

export type AzureModelConfig = z.infer<typeof AzureModelConfigSchema>;

export const OllamaModelConfigSchema = z.object({
  provider: z.literal("autogen_ext.models.ollama.OllamaChatCompletionClient"),
  config: z.object({
    model: z.string().min(1, "Model name is required."),
  }).passthrough(),
}).passthrough();

export type OllamaModelConfig = z.infer<typeof OllamaModelConfigSchema>;

export const ModelConfigSchema = z.discriminatedUnion("provider", [
  OpenAIModelConfigSchema,
  AzureModelConfigSchema,
  OllamaModelConfigSchema
]);

export type ModelConfig = z.infer<typeof ModelConfigSchema>;

// Common interface for all model config forms
export interface ModelConfigFormProps {
  onChange?: (config: ModelConfig) => void;
  onSubmit?: (config: ModelConfig) => void;
  value?: ModelConfig;
  hideAdvancedToggles?: boolean;
}

