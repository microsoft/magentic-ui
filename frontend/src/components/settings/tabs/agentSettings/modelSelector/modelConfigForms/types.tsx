import { z } from "zod";

export const ModelFamilySchema = z.enum([
  "gpt-41",
  "gpt-45",
  "gpt-4o",
  "o1",
  "o3",
  "o4",
  "gpt-4",
  "gpt-35",
  "r1",
  "gemini-1.5-flash",
  "gemini-1.5-pro",
  "gemini-2.0-flash",
  "gemini-2.5-pro",
  "gemini-2.5-flash",
  "claude-3-haiku",
  "claude-3-sonnet",
  "claude-3-opus",
  "claude-3-5-haiku",
  "claude-3-5-sonnet",
  "claude-3-7-sonnet",
  "claude-4-opus",
  "claude-4-sonnet",
  "llama-3.3-8b",
  "llama-3.3-70b",
  "llama-4-scout",
  "llama-4-maverick",
  "codestral",
  "open-codestral-mamba",
  "mistral",
  "ministral",
  "pixtral",
  "unknown"
]);

export type ModelFamily = z.infer<typeof ModelFamilySchema>;

export const ModelInfoSchema = z.object({
  vision: z.boolean(),
  function_calling: z.boolean(),
  json_output: z.boolean(),
  family: ModelFamilySchema,
  structured_output: z.boolean().default(false).optional(),
  multiple_system_messages: z.boolean().default(false).optional(),
}).passthrough();

export type ModelInfo = z.infer<typeof ModelInfoSchema>;

export const OpenAIModelConfigSchema = z.object({
  provider: z.literal("OpenAIChatCompletionClient"),
  config: z.object({
    model: z.string().min(1, "Model name is required."),
    model_info: ModelInfoSchema.optional()
  }).passthrough(),
}).passthrough();

export type OpenAIModelConfig = z.infer<typeof OpenAIModelConfigSchema>;

export const AzureModelConfigSchema = z.object({
  provider: z.literal("AzureOpenAIChatCompletionClient"),
  config: z.object({
    model: z.string().min(1, "Model name is required."),
    azure_endpoint: z.string().min(1, "Azure endpoint is required."),
    azure_deployment: z.string().min(1, "Azure deployment is required."),
    model_info: ModelInfoSchema.optional()
  }).passthrough(),
}).passthrough();

export type AzureModelConfig = z.infer<typeof AzureModelConfigSchema>;

export const OllamaModelConfigSchema = z.object({
  provider: z.literal("autogen_ext.models.ollama.OllamaChatCompletionClient"),
  config: z.object({
    model: z.string().min(1, "Model name is required."),
    model_info: ModelInfoSchema.optional()
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

