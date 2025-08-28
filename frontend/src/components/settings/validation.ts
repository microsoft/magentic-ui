import { ModelConfigSchema } from "./tabs/agentSettings/modelSelector/modelConfigForms/types";
import { MCPAgentConfigSchema } from "../features/McpServersConfig/types";
import { GeneralSettingsSchema } from "./types";

export function extractZodErrors(error: any): string[] {
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
      MCPAgentConfigSchema.parse(agents[i]);
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

export function validateModelConfig(config: any): string[] {
  try {
    ModelConfigSchema.parse(config);
    return [];
  } catch (e) {
    return extractZodErrors(e);
  }
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
  return errors;
}
