import { z } from "zod";
import { ModelConfigSchema } from "../modelSelector/modelConfigForms/types";
import { NamedMCPServerConfigSchema } from "./mcpServerForms/types";

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