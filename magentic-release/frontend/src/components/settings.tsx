import React from "react";
import { MoonIcon, SunIcon } from "@heroicons/react/24/outline";
import { appContext } from "../hooks/provider";
import SignInModal from "./signin";
import { useSettingsStore, generateOpenAIModelConfig } from "./store";
import MonacoEditor from "@monaco-editor/react";
import { settingsAPI } from "./views/api";
import {
  Input,
  Switch,
  Button,
  Space,
  Tag,
  Divider,
  Modal,
  Tooltip,
  Select,
  Tabs,
  Input as AntInput,
  Upload,
  message,
} from "antd";
import { InfoCircleOutlined, UploadOutlined } from "@ant-design/icons";
import { Plus } from "lucide-react";

const { TextArea } = AntInput;

interface SettingsMenuProps {
  isOpen: boolean;
  onClose: () => void;
}

const SettingsMenu: React.FC<SettingsMenuProps> = ({ isOpen, onClose }) => {
  const { darkMode, setDarkMode, user } = React.useContext(appContext);
  const [isEmailModalOpen, setIsEmailModalOpen] = React.useState(false);
  const [hasChanges, setHasChanges] = React.useState(false);
  const [validationWarning, setValidationWarning] = React.useState<
    string | null
  >(null);

  const { config, updateConfig, resetToDefaults } = useSettingsStore();
  const [websiteInput, setWebsiteInput] = React.useState("");
  const [cachedWebsites, setCachedWebsites] = React.useState<string[]>([]);
  const [allowedlistEnabled, setAllowedlistEnabled] = React.useState(false);

  const MODEL_OPTIONS = [
    { value: "gpt-4.1-2025-04-14", label: "OpenAI GPT-4.1" },
    { value: "gpt-4.1-mini-2025-04-14", label: "OpenAI GPT-4.1 Mini" },
    { value: "azure-ai-foundry", label: "Azure AI Foundry Template" },
    { value: "ollama", label: "Ollama (Local)" },
    { value: "openrouter", label: "OpenRouter" },
    { value: "gpt-4.1-nano-2025-04-14", label: "OpenAI GPT-4.1 Nano" },
    { value: "o4-mini-2025-04-16", label: "OpenAI O4 Mini" },
    { value: "o3-mini-2025-01-31", label: "OpenAI O3 Mini" },
    { value: "gpt-4o-2024-08-06", label: "OpenAI GPT-4o" },
    { value: "gpt-4o-mini-2024-07-18", label: "OpenAI GPT-4o Mini" },
  ];

  const AZURE_AI_FOUNDRY_YAML = `model_config: &client
  provider: AzureOpenAIChatCompletionClient
  config:
    model: gpt-4o
    azure_endpoint: "<YOUR ENDPOINT>"
    azure_deployment: "<YOUR DEPLOYMENT>"
    api_version: "2024-10-21"
    azure_ad_token_provider:
      provider: autogen_ext.auth.azure.AzureTokenProvider
      config:
        provider_kind: DefaultAzureCredential
        scopes:
          - https://cognitiveservices.azure.com/.default
    max_retries: 10

orchestrator_client: *client
coder_client: *client
web_surfer_client: *client
file_surfer_client: *client
action_guard_client: *client
`;

  const OPENROUTER_YAML = `model_config: &client
  provider: OpenAIChatCompletionClient
  config:
    model: "MODEL_NAME"
    base_url: "https://openrouter.ai/api/v1"
    api_key: "KEY"
    model_info: # change per model
       vision: true 
       function_calling: true # required true for file_surfer, but will still work if file_surfer is not needed
       json_output: false
       family: unknown
       structured_output: false
  max_retries: 5


orchestrator_client: *client
coder_client: *client
web_surfer_client: *client
file_surfer_client: *client
action_guard_client: *client
`;

  const OLLAMA_YAML = `model_config: &client
  provider: autogen_ext.models.ollama.OllamaChatCompletionClient
  config:
    model: "qwen2.5vl:32b" # change to your desired Ollama model
    host: "http://localhost:11434" # change to your ollama host
    model_info: # change per model you use
      vision: true
      function_calling: true # will work if false but not fully
      json_output: false # prefered true
      family: unknown
      structured_output: false
  max_retries: 5

# Note you can define multiple model clients and use them for different agents
# You can also use the OpenAI client instead and access Ollama models
#model_config: &client
#  provider: OpenAIChatCompletionClient
#  config:
#    model: "qwen2.5vl:32b"
#    base_url: "http://localhost:11434/v1" # change to your ollama host
#    model_info: # change per model
#       vision: true 
#       function_calling: true # required true for file_surfer, but will still work if file_surfer is not needed
#       json_output: false
#       family: unknown
#       structured_output: false
#  max_retries: 5

orchestrator_client: *client
coder_client: *client
web_surfer_client: *client
file_surfer_client: *client
action_guard_client: *client
`;

  React.useEffect(() => {
    if (isOpen) {
      setHasChanges(false);
      setValidationWarning(null);
      // Load settings when modal opens
      const loadSettings = async () => {
        if (user?.email) {
          try {
            const settings = await settingsAPI.getSettings(user.email);
            updateConfig(settings);
            // Initialize the cached websites from loaded settings
            setCachedWebsites(settings.allowed_websites || []);
            setAllowedlistEnabled(Boolean(settings.allowed_websites?.length));
          } catch (error) {
            console.error("Failed to load settings");
          }
        }
      };
      loadSettings();
    }
  }, [isOpen, user?.email]);

  const handleUpdateConfig = async (changes: any) => {
    updateConfig(changes);
    setHasChanges(true);

    // Save to database
    if (user?.email) {
      try {
        const updatedConfig = { ...config, ...changes };
        await settingsAPI.updateSettings(user.email, updatedConfig);
      } catch (error) {
        console.error("Failed to save settings:", error);
      }
    }
  };

  const handleResetDefaults = async () => {
    resetToDefaults();
    setCachedWebsites([]); // Clear the list of websites manually added by people
    setHasChanges(true);

    // Save default settings to database
    if (user?.email) {
      try {
        const defaultConfig = useSettingsStore.getState().config;
        await settingsAPI.updateSettings(user.email, defaultConfig);
      } catch (error) {
        console.error("Failed to save default settings:", error);
      }
    }
  };

  const addWebsite = () => {
    if (websiteInput && !cachedWebsites.includes(websiteInput)) {
      const updatedList = [...cachedWebsites, websiteInput];
      setCachedWebsites(updatedList);
      handleUpdateConfig({ allowed_websites: updatedList });
      setWebsiteInput("");
      setValidationWarning(null);
    }
  };

  const removeWebsite = (site: string) => {
    const updatedList = cachedWebsites.filter((item) => item !== site);
    setCachedWebsites(updatedList);
    handleUpdateConfig({ allowed_websites: updatedList });
  };

  const handleClose = () => {
    // Check if allowedlist is enabled but no websites are added
    if (allowedlistEnabled && cachedWebsites.length === 0) {
      setValidationWarning(
        "You must add at least one website to the Allowed Websites list or turn off this feature"
      );
      return;
    }
    setValidationWarning(null);
    onClose();
  };

  const validateYamlConfig = (content: string): boolean => {
    const requiredClients = [
      "orchestrator_client",
      "coder_client",
      "web_surfer_client",
      "file_surfer_client",
    ];
    const hasAllClients = requiredClients.every((client) =>
      content.includes(client)
    );
    if (!hasAllClients) {
      message.error(
        "YAML must include all required model clients: " +
          requiredClients.join(", ")
      );
      return false;
    }
    return true;
  };

  const handleYamlFileUpload = async (file: File) => {
    try {
      const reader = new FileReader();
      reader.onload = (e) => {
        const content = e.target?.result as string;
        if (validateYamlConfig(content)) {
          handleUpdateConfig({ model_configs: content });
          message.success("YAML configuration imported successfully");
        }
      };
      reader.onerror = () => {
        message.error("Failed to read the YAML file");
      };
      reader.readAsText(file);
    } catch (error) {
      message.error("Failed to import YAML configuration");
      console.error("Error importing YAML:", error);
    }
    return false; // Prevent default upload behavior
  };

  const updateModelInConfig = (modelName: string) => {
    try {
      if (modelName === "azure-ai-foundry") {
        handleUpdateConfig({ model_configs: AZURE_AI_FOUNDRY_YAML });
        message.success("Azure AI Foundry configuration applied");
        return;
      }
      if (modelName === "openrouter") {
        handleUpdateConfig({ model_configs: OPENROUTER_YAML });
        message.success("OpenRouter configuration applied");
        return;
      }
      if (modelName === "ollama") {
        handleUpdateConfig({ model_configs: OLLAMA_YAML });
        message.success("Ollama configuration applied");
        return;
      }
      // For OpenAI models, reset YAML to default with only client and selected model
      handleUpdateConfig({
        model_configs: generateOpenAIModelConfig(modelName),
      });
      message.success("OpenAI model configuration applied");
    } catch (error) {
      console.error("Error updating model in config:", error);
      message.error("Failed to update model configuration");
    }
  };

  return (
    <>
      <Modal
        open={isOpen}
        onCancel={handleClose}
        closable={!(allowedlistEnabled && cachedWebsites.length === 0)}
        footer={[
          <div key="footer" className="mt-12 space-y-2">
            {validationWarning && (
              <div className="text-red-500 text-sm">{validationWarning}</div>
            )}
            {hasChanges && (
              <div className="text-secondary text-sm italic">
                Warning: Settings changes will only apply when you create a new
                session
              </div>
            )}
            <div className="flex gap-2 justify-end">
              <Button key="reset" onClick={handleResetDefaults}>
                Reset to Defaults
              </Button>
            </div>
          </div>,
        ]}
        width={700}
      >
        <div className="mt-12 space-y-4">
          <Tabs
            tabPosition="left"
            items={[
              {
                key: "general",
                label: "General",
                children: (
                  <div className="space-y-6 px-4">
                    {/* Dark Mode Toggle */}
                    <div className="flex items-center justify-between">
                      <span className="text-primary">
                        {darkMode === "dark" ? "Dark Mode" : "Light Mode"}
                      </span>
                      <button
                        onClick={() =>
                          setDarkMode(darkMode === "dark" ? "light" : "dark")
                        }
                        className="text-secondary hover:text-primary"
                      >
                        {darkMode === "dark" ? (
                          <MoonIcon className="h-6 w-6" />
                        ) : (
                          <SunIcon className="h-6 w-6" />
                        )}
                      </button>
                    </div>

                    <Divider />

                    {/* Basic Settings */}
                    <div className="space-y-4">
                      <div className="flex items-center justify-between">
                        <span className="flex items-center gap-2">
                          Action Approval Policy
                          <Tooltip title="Controls when approval is required before taking actions">
                            <InfoCircleOutlined className="text-secondary hover:text-primary cursor-help" />
                          </Tooltip>
                        </span>
                        <Select
                          value={config.approval_policy}
                          onChange={(value: string) =>
                            handleUpdateConfig({ approval_policy: value })
                          }
                          style={{ width: 200 }}
                          options={[
                            { value: "never", label: "Never require approval" },
                            {
                              value: "auto-conservative",
                              label: "AI based judgement",
                            },
                            {
                              value: "always",
                              label: "Always require approval",
                            },
                          ]}
                        />
                      </div>

                      <Divider />

                      <div className="space-y-4">
                        <div className="flex items-center justify-between">
                          <span className="flex items-center gap-2">
                            Allowed Websites List
                            <Tooltip title="When enabled, Magentic-UI will only be able to visit websites you add to the list below.s">
                              <InfoCircleOutlined className="text-secondary hover:text-primary cursor-help" />
                            </Tooltip>
                          </span>
                          {cachedWebsites.length === 0 && (
                            <Switch
                              checked={allowedlistEnabled}
                              checkedChildren="Restricted to List"
                              unCheckedChildren="All Websites Allowed"
                              onChange={(checked) => {
                                setAllowedlistEnabled(checked);
                                if (!checked) {
                                  setCachedWebsites([]);
                                  handleUpdateConfig({ allowed_websites: [] });
                                  setValidationWarning(null);
                                }
                              }}
                            />
                          )}
                        </div>

                        <Space direction="vertical" style={{ width: "100%" }}>
                          {allowedlistEnabled || cachedWebsites.length > 0 ? (
                            <>
                              <div className="flex w-full gap-2">
                                <Input
                                  placeholder="https://example.com"
                                  value={websiteInput}
                                  onChange={(
                                    e: React.ChangeEvent<HTMLInputElement>
                                  ) => setWebsiteInput(e.target.value)}
                                  onPressEnter={addWebsite}
                                  className="flex-1"
                                />
                                <Button
                                  icon={<Plus size={16} />}
                                  onClick={addWebsite}
                                >
                                  Add
                                </Button>
                              </div>
                              <div>
                                {cachedWebsites.length === 0 ? (
                                  <div></div>
                                ) : (
                                  cachedWebsites.map(
                                    (site: string, index: number) => (
                                      <Tag
                                        key={index}
                                        closable
                                        onClose={() => removeWebsite(site)}
                                        style={{ margin: "0 8px 8px 0" }}
                                      >
                                        {site}
                                      </Tag>
                                    )
                                  )
                                )}
                              </div>
                            </>
                          ) : (
                            <div className="text-secondary italic"></div>
                          )}
                        </Space>
                      </div>
                    </div>
                  </div>
                ),
              },
              {
                key: "advanced",
                label: "Advanced",
                children: (
                  <div className="space-y-4 px-4">
                    <div className="flex items-center justify-between">
                      <span className="flex items-center gap-2">
                        Allow Replans
                        <Tooltip title="When enabled, Magentic-UI will automatically replan if the current plan is not working or you change the original request">
                          <InfoCircleOutlined className="text-secondary hover:text-primary cursor-help" />
                        </Tooltip>
                      </span>
                      <Switch
                        checked={config.allow_for_replans}
                        checkedChildren="ON"
                        unCheckedChildren="OFF"
                        onChange={(checked) =>
                          handleUpdateConfig({ allow_for_replans: checked })
                        }
                      />
                    </div>

                    {/*<div className="flex items-center justify-between">
                       <span className="flex items-center gap-2">
                        Use Bing Search for Planning
                        <Tooltip title="When enabled, Magentic-UI will use Bing Search when coming up with a plan. Note this adds 10 seconds to the planning time.">
                          <InfoCircleOutlined className="text-secondary hover:text-primary cursor-help" />
                        </Tooltip>
                      </span> 
                      <Switch
                        checked={config.do_bing_search}
                        checkedChildren="ON"
                        unCheckedChildren="OFF"
                        onChange={(checked) =>
                          handleUpdateConfig({ do_bing_search: checked })
                        }
                      />
                    </div>
                    */}
                    <div className="flex items-center justify-between">
                      <span className="flex items-center gap-2">
                        Retrieve Relevant Plans
                        <Tooltip title="Controls how Magentic-UI retrieves and uses relevant plans from previous sessions">
                          <InfoCircleOutlined className="text-secondary hover:text-primary cursor-help" />
                        </Tooltip>
                      </span>
                      <Select
                        value={config.retrieve_relevant_plans}
                        onChange={(value: string) =>
                          handleUpdateConfig({ retrieve_relevant_plans: value })
                        }
                        style={{ width: 200 }}
                        options={[
                          {
                            value: "never",
                            label: (
                              <Tooltip title="No plan retrieval">
                                No plan retrieval
                              </Tooltip>
                            ),
                          },
                          {
                            value: "hint",
                            label: (
                              <Tooltip title="Retrieve most relevant saved plan as hints for new plans">
                                Retrieve plans as hints
                              </Tooltip>
                            ),
                          },
                          {
                            value: "reuse",
                            label: (
                              <Tooltip title="Retrieve most relevant saved plan to be used directly">
                                Retrieve plans to use directly
                              </Tooltip>
                            ),
                          },
                        ]}
                      />
                    </div>
                  </div>
                ),
              },
              {
                key: "model",
                label: "Model Configuration",
                children: (
                  <div className="space-y-4 px-4">
                    <div className="flex flex-col gap-2">
                      <div className="flex items-center justify-between">
                        <span className="flex items-center gap-2">
                          Model Configuration
                          <Tooltip
                            title={
                              <>
                                <p>
                                  YAML configuration for the underlying LLM of
                                  the agents.{" "}
                                </p>
                                <p>
                                  {" "}
                                  The configuration uses AutoGen
                                  ChatCompletionClient format.
                                </p>
                                <p>
                                  Must include configurations for:
                                  orchestrator_client, coder_client,
                                  web_surfer_client, and file_surfer_client.
                                </p>
                                <p>
                                  Each client should follow the AutoGen
                                  ChatCompletionClient specification with
                                  provider, config (model, etc), and
                                  max_retries.
                                </p>
                                <p>
                                  Changes require a new session to take effect.
                                </p>
                              </>
                            }
                          >
                            <InfoCircleOutlined className="text-secondary hover:text-primary cursor-help" />
                          </Tooltip>
                        </span>
                        <Upload
                          accept=".yaml,.yml"
                          showUploadList={false}
                          beforeUpload={handleYamlFileUpload}
                        >
                          <Button icon={<UploadOutlined />}>Import YAML</Button>
                        </Upload>
                      </div>

                      <div className="flex gap-2 items-center">
                        <div className="flex-grow">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-sm">
                              Select LLM for All Clients
                            </span>
                            <Tooltip title="This will update the model configuration for all agent clients (orchestrator, coder, web surfer, and file surfer)">
                              <InfoCircleOutlined className="text-primary hover:text-primary cursor-help" />
                            </Tooltip>
                          </div>
                          <Select
                            style={{ width: "100%" }}
                            options={MODEL_OPTIONS}
                            onChange={(value: string) =>
                              updateModelInConfig(value)
                            }
                            placeholder="Select model to use for all clients"
                          />
                        </div>
                      </div>

                      <Divider />

                      <div>
                        <div className="text-sm mb-1">
                          Advanced Configuration (YAML)
                        </div>
                        <MonacoEditor
                          value={config.model_configs}
                          onChange={(value) => {
                            handleUpdateConfig({
                              model_configs: value,
                            });
                          }}
                          language="yaml"
                          height="300px"
                          options={{
                            fontFamily: "monospace",
                            minimap: { enabled: false },
                            wordWrap: "on",
                            scrollBeyondLastLine: false,
                            theme: darkMode === "dark" ? "vs-dark" : "light",
                          }}
                        />
                      </div>
                    </div>
                  </div>
                ),
              },
            ]}
          />
        </div>
      </Modal>
      <SignInModal
        isVisible={isEmailModalOpen}
        onClose={() => setIsEmailModalOpen(false)}
      />
    </>
  );
};

export default SettingsMenu;
