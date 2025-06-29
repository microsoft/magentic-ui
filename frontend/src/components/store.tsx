import { create } from "zustand";
import { DEFAULT_OPENAI } from "./settings/tabs/agentSettings/modelSelector/modelConfigForms/OpenAIModelConfigForm";
import { PROVIDER_FORM_MAP } from "./settings/tabs/agentSettings/modelSelector/ModelSelector";

export interface GeneralConfig {
  cooperative_planning: boolean;
  autonomous_execution: boolean;
  allowed_websites?: string[];
  max_actions_per_step: number;
  multiple_tools_per_call: boolean;
  max_turns: number;
  plan?: {
    task: string;
    steps: any[];
    plan_summary: string;
  };
  approval_policy: "always" | "never" | "auto-conservative" | "auto-permissive";
  allow_for_replans: boolean;
  do_bing_search: boolean;
  websurfer_loop: boolean;
  run_without_docker: boolean;
  browser_headless: boolean;
  model_client_configs: {orchestrator: any, web_surfer: any, coder: any, file_surfer: any, action_guard: any};
  mcp_agent_configs: any[];
  retrieve_relevant_plans: "never" | "hint" | "reuse"; // this is for using task centric memory to retrieve relevant plans
  server_url: string; // Optional server URL for VNC/live view
}

const defaultConfig: GeneralConfig = {
  cooperative_planning: true,
  autonomous_execution: false,
  max_actions_per_step: 5,
  multiple_tools_per_call: false,
  max_turns: 20,
  approval_policy: "auto-conservative",
  allow_for_replans: true,
  do_bing_search: false,
  websurfer_loop: false,
  retrieve_relevant_plans: "never",
  server_url: "localhost",
  mcp_agent_configs: [],
  run_without_docker: false,
  browser_headless: true,
  model_client_configs: {
    "orchestrator": DEFAULT_OPENAI,
    "web_surfer": DEFAULT_OPENAI,
    "coder": DEFAULT_OPENAI,
    "file_surfer": DEFAULT_OPENAI,
    "action_guard": PROVIDER_FORM_MAP[DEFAULT_OPENAI.provider].presets["gpt-4.1-nano-2025-04-14"],
  },
};

interface SettingsState {
  config: GeneralConfig;
  updateConfig: (update: Partial<GeneralConfig>) => void;
  resetToDefaults: () => void;
}

export const useSettingsStore = create<SettingsState>()((set) => ({
  config: defaultConfig,
  updateConfig: (update) =>
    set((state) => ({
      config: { ...state.config, ...update },
    })),
  resetToDefaults: () => set({ config: defaultConfig }),
}));

export function generateOpenAIModelConfig(model: string) {
  return `model_client_configs:
  orchestrator:
    provider: OpenAIChatCompletionClient
    config:
      model: ${model}
    max_retries: 5
  coder:
    provider: OpenAIChatCompletionClient
    config:
      model: ${model}
    max_retries: 5
  web_surfer:
    provider: OpenAIChatCompletionClient
    config:
      model: ${model}
    max_retries: 5
  file_surfer:
    provider: OpenAIChatCompletionClient
    config:
      model: ${model}
    max_retries: 5
  action_guard:
    provider: OpenAIChatCompletionClient
    config:
      model: ${model}
    max_retries: 5
`;
}
