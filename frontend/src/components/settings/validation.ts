import { z } from "zod";
import { MODEL_CLIENT_KEYS } from "./tabs/ModelConfigSettings/ModelConfigSettings";
import type { GeneralConfig } from "../store";

// MCP Agent Schema
const MCPAgentSchema = z.object({
  name: z.string().min(1, "Name is required."),
  description: z.string().min(1, "Description is required."),
  model_client: z.record(z.any()).refine((obj) => Object.keys(obj).length > 0, {
    message: "Model selection is required.",
  }),
  mcp_servers: z.array(z.any()).min(1, "At least one MCP Server is required."),
});

// Model Config Schemas (allowing additional props at root and in config)
const OpenAIModelConfigSchema = z.object({
  provider: z.literal("OpenAIChatCompletionClient"),
  config: z.object({
    model: z.string().min(1, "Model name is required."),
    // Allow additional properties
  }).passthrough(),
  // Allow additional properties at root
}).passthrough();

const AzureModelConfigSchema = z.object({
  provider: z.literal("AzureOpenAIChatCompletionClient"),
  config: z.object({
    model: z.string().min(1, "Model name is required."),
    azure_endpoint: z.string().min(1, "Azure endpoint is required."),
    azure_deployment: z.string().min(1, "Azure deployment is required."),
    // Allow additional properties
  }).passthrough(),
  // Allow additional properties at root
}).passthrough();

const OllamaModelConfigSchema = z.object({
  provider: z.literal("autogen_ext.models.ollama.OllamaChatCompletionClient"),
  config: z.object({
    model: z.string().min(1, "Model name is required."),
    // Allow additional properties
  }).passthrough(),
  // Allow additional properties at root
}).passthrough();

// ModelConfigSchema as a union of the concrete schemas
export const ModelConfigSchema = z.union([
  OpenAIModelConfigSchema,
  AzureModelConfigSchema,
  OllamaModelConfigSchema
]);

// GeneralSettingsSchema: schema for all properties in GeneralConfig
export const GeneralSettingsSchema = z.object({
  cooperative_planning: z.boolean(),
  autonomous_execution: z.boolean(),
  allowed_websites: z.array(z.string().min(1)).optional(),
  max_actions_per_step: z.number(),
  multiple_tools_per_call: z.boolean(),
  max_turns: z.number(),
  plan: z.object({
    task: z.string(),
    steps: z.array(z.any()),
    plan_summary: z.string(),
  }).optional(),
  approval_policy: z.enum(["always", "never", "auto-conservative", "auto-permissive"]),
  allow_for_replans: z.boolean(),
  do_bing_search: z.boolean(),
  websurfer_loop: z.boolean(),
  model_client_configs: z.object({
    orchestrator: ModelConfigSchema,
    web_surfer: ModelConfigSchema,
    coder: ModelConfigSchema,
    file_surfer: ModelConfigSchema,
    action_guard: ModelConfigSchema,
  }),
  mcp_agent_configs: z.array(MCPAgentSchema),
  retrieve_relevant_plans: z.enum(["never", "hint", "reuse"]),
});

function extractZodErrors(error: any): string[] {
  if (!error.errors) return [error.message || String(error)];
  return error.errors.map((e: any) => {
    const path = e.path.length ? `${e.path.join(".")}: ` : "";
    return `${path}${e.message}`;
  });
}

export function validateGeneralSettings(config: any): string[] {
  try {
    GeneralSettingsSchema.parse(config);
    return [];
  } catch (e) {
    return extractZodErrors(e);
  }
}

export function validateMCPAgentsSettings(agents: any[]): string[] {
  const errors: string[] = [];
  if (!Array.isArray(agents)) {
    return ["Agents must be an array."];
  }
  for (let i = 0; i < agents.length; i++) {
    try {
      MCPAgentSchema.parse(agents[i]);
    } catch (e) {
      extractZodErrors(e).forEach((msg) => errors.push(`Agent #${i + 1}: ${msg}`));
    }
  }
  return errors;
}

export function validateAdvancedConfigEditor(editorValue: string, isValidany: (obj: any) => boolean): string[] {
  const errors: string[] = [];
  try {
    const yaml = require('js-yaml');
    const parsed = yaml.load(editorValue || "");
    if (!parsed || typeof parsed !== "object") {
      errors.push("Config is empty or not an object.");
    } else if (!isValidany(parsed)) {
      errors.push("Config is not a valid any.");
    }
  } catch (e) {
    errors.push("Config YAML is invalid.");
  }
  return errors;
}

export function validateOpenAIModelConfig(config: any): string[] {
  try {
    OpenAIModelConfigSchema.parse(config);
    return [];
  } catch (e) {
    return extractZodErrors(e);
  }
}

export function validateAzureModelConfig(config: any): string[] {
  try {
    AzureModelConfigSchema.parse(config);
    return [];
  } catch (e) {
    return extractZodErrors(e);
  }
}

export function validateOllamaModelConfig(config: any): string[] {
  try {
    OllamaModelConfigSchema.parse(config);
    return [];
  } catch (e) {
    return extractZodErrors(e);
  }
}

export function validateModelConfig(config: any): string[] {
  const openai = validateOpenAIModelConfig(config);
  const azure = validateAzureModelConfig(config);
  const ollama = validateOllamaModelConfig(config);
  if (openai.length === 0 || azure.length === 0 || ollama.length === 0) {
    return [];
  }
  return openai.length ? openai : azure.length ? azure : ollama;
}

export function validateModelConfigSettings(modelClientConfigs: Record<string, any> | undefined, requiredKeys: string[]): string[] {
  const errors: string[] = [];
  if (!modelClientConfigs || typeof modelClientConfigs !== 'object') {
    errors.push('Model client configs are missing or invalid.');
    return errors;
  }
  for (const key of requiredKeys) {
    if (!modelClientConfigs[key]) {
      errors.push(`${key}: missing`);
    } else {
      const err = validateModelConfig(modelClientConfigs[key]);
      if (err.length > 0) {
        errors.push(`${key}: ${err.join('; ')}`);
      }
    }
  }
  return errors;
}

export function validateAll(config: any): string[] {
  let errors: string[] = [];
  errors = errors.concat(validateGeneralSettings(config));
  if (Array.isArray(config.mcp_agent_configs)) {
    errors = errors.concat(validateMCPAgentsSettings(config.mcp_agent_configs));
  }
  errors = errors.concat(validateModelConfigSettings(config.model_client_configs, MODEL_CLIENT_KEYS));
  return errors;
}
