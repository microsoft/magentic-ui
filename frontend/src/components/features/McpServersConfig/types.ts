import { z } from "zod";
import { ModelConfigSchema } from "../../settings/tabs/agentSettings/modelSelector/modelConfigForms/types";

// Shared server name pattern - must start with letter, then letters/numbers
export const SERVER_NAME_PATTERN = /^[A-Za-z]+[A-Za-z0-9]*$/;

// Agent name pattern - must be a valid Python identifier (same as Python side)
export const AGENT_NAME_PATTERN = /^[a-zA-Z_]+[a-zA-Z0-9_]*$/;

export const StdioServerParamsSchema = z.object({
  type: z.literal("StdioServerParams"),
  command: z.string(),
  args: z.array(z.string()).optional(),
  read_timeout_seconds: z.number().gt(0).optional(),
  env: z.record(z.string()).optional(),
  cwd: z.string().optional(),
  encoding: z.string().default("utf-8").optional(),
  encoding_error_handler: z.enum(["strict", "ignore", "replace"]).default("strict").optional(),
})

export type StdioServerParams = z.infer<typeof StdioServerParamsSchema>

export const SseServerParamsSchema = z.object({
  type: z.literal("SseServerParams"),
  url: z.string(),
  headers: z.record(z.string()).optional(),
  timeout: z.number().gt(0).optional(),
  sse_read_timeout: z.number().gt(0).optional(),
})

export type SseServerParams = z.infer<typeof SseServerParamsSchema>

// Zod schema for server configuration validation
export const MCPServerConfigSchema = z.discriminatedUnion("type", [
  StdioServerParamsSchema, SseServerParamsSchema
]);

export type MCPServerConfig = z.infer<typeof MCPServerConfigSchema>;

// Zod schema for named server configuration validation
export const NamedMCPServerConfigSchema = z.object({
  server_name: z.string().regex(SERVER_NAME_PATTERN, "Only letters and numbers are allowed and the name must be a valid python identifier."),
  server_params: MCPServerConfigSchema,
  connection_status: z.object({
    is_connected: z.boolean().optional(),
    tools_found: z.number().optional(),
  }).optional(),
});

export type NamedMCPServerConfig = z.infer<typeof NamedMCPServerConfigSchema>;

// Zod schema for agent configuration validation
export const MCPAgentConfigSchema = z.object({
  name: z.string().regex(/^[a-zA-Z_]+[a-zA-Z0-9_]*/, "Agent name must be a valid python identifier."),
  description: z.string(),
  system_message: z.string().optional(),
  mcp_servers: z.array(NamedMCPServerConfigSchema).min(1, { message: "At least one MCP server is required." }),
  model_context_token_limit: z.number().optional(),
  tool_call_summary_format: z.string().optional(),
  model_client: ModelConfigSchema,
});

export type MCPAgentConfig = z.infer<typeof MCPAgentConfigSchema>;

export interface MCPServerInfo {
  agentName: string;
  agentDescription: string;
  serverName: string;
  serverType: string;
  serverParams: StdioServerParams | SseServerParams;
  connectionStatus?: {
    isConnected?: boolean;
    toolsFound?: number;
  };
}

export const DEFAULT_SSE_PARAMS: SseServerParams = {
  type: "SseServerParams",
  url: "",
  headers: {},
  timeout: 5,
  sse_read_timeout: 300,
};

export const DEFAULT_STDIO_PARAMS: StdioServerParams = {
  type: "StdioServerParams",
  command: "",
  args: [],
  read_timeout_seconds: 5,
};

export const MCP_SERVER_TYPES = {
  "StdioServerParams": { value: "StdioServerParams", label: "Stdio", defaultValue: DEFAULT_STDIO_PARAMS },
  "SseServerParams": { value: "SseServerParams", label: "SSE", defaultValue: DEFAULT_SSE_PARAMS },
};

export const serverNamePattern = SERVER_NAME_PATTERN;
export const agentNamePattern = AGENT_NAME_PATTERN;

export const isEmpty = (val: any) => val === undefined || val === null || (typeof val === 'string' && val.trim() === '') || (Array.isArray(val) && val.length === 0);

// Type guards for server_params
export function isStdioServerParams(params: any): params is StdioServerParams {
  return params.type === "StdioServerParams";
}

export function isSseServerParams(params: any): params is SseServerParams {
  return params.type === "SseServerParams";
}

// Generic validation utility function
export function validateWithZod(schema: any, data: any, errorPrefix: string = "Validation"): any {
  const result = schema.safeParse(data);
  if (!result.success) {
    const errors = result.error.errors.map((err: any) => `${err.path.join('.')}: ${err.message}`).join(', ');
    throw new Error(`${errorPrefix} failed: ${errors}`);
  }
  return result.data;
}

// JSON validation utility function
export function validateJsonConfig(jsonString: string, schema: any, errorPrefix: string = "Invalid configuration"): any {
  try {
    const parsed = JSON.parse(jsonString);
    return validateWithZod(schema, parsed, errorPrefix);
  } catch (error) {
    throw new Error(`${errorPrefix}: ${error instanceof Error ? error.message : 'Invalid JSON format'}`);
  }
}

// Validation utility functions
export function validateMCPServerConfig(config: any): any {
  return validateWithZod(MCPServerConfigSchema, config, "MCP Server Config");
}

export function validateNamedMCPServerConfig(config: any): any {
  return validateWithZod(NamedMCPServerConfigSchema, config, "Named MCP Server Config");
}

export function validateMCPAgentConfig(config: any): any {
  return validateWithZod(MCPAgentConfigSchema, config, "MCP Agent Config");
}
