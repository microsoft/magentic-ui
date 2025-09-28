import { z } from "zod";
import { ModelConfigSchema } from "./tabs/agentSettings/modelSelector/modelConfigForms/types";
import { MCPAgentConfigSchema } from "../features/McpServersConfig/types";

export const GeneralSettingsSchema = z.object({
  cooperative_planning: z.boolean(),
  autonomous_execution: z.boolean(),
  allowed_websites: z.array(z.string().min(1)).min(1).optional(),
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
  mcp_agent_configs: z.array(MCPAgentConfigSchema),
  retrieve_relevant_plans: z.enum(["never", "hint", "reuse"]),
});

export type GeneralSettings = z.infer<typeof GeneralSettingsSchema>

export interface SettingsTabProps {
  config: GeneralSettings;
  handleUpdateConfig: (changes: any) => void;
}
