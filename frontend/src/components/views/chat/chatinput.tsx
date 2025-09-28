import {
  PaperAirplaneIcon,
  ExclamationTriangleIcon,
  PauseCircleIcon,
} from "@heroicons/react/24/outline";
import * as React from "react";
import { appContext } from "../../../hooks/provider";
import { IStatus } from "../../types/app";
import {
  Upload,
  message,
  Button,
  Tooltip,
  notification,
  Modal,
  Dropdown,
  Menu,
} from "antd";
import type { UploadFile, UploadProps, RcFile } from "antd/es/upload/interface";
import {
  FileTextIcon,
  ImageIcon,
  XIcon,
  UploadIcon,
  PaperclipIcon,
} from "lucide-react";
import { InputRequest } from "../../types/datamodel";
import { debounce } from "lodash";
import { planAPI, settingsAPI } from "../api";
import RelevantPlans from "./relevant_plans";
import { IPlan } from "../../types/plan";
import PlanView from "./plan";
import { McpServerSelector } from "../../features/McpServerSelector/McpServerSelector";
import { MCPAgentConfig, MCPServerInfo } from "../../features/McpServersConfig/types";
import { extractMcpServers } from "../../features/McpServersConfig/McpServersList";
// Threshold for large text files (in characters)
const LARGE_TEXT_THRESHOLD = 1500;

interface ChatInputProps {
  onSubmit: (
    text: string,
    files: RcFile[],
    accepted?: boolean,
    plan?: IPlan
  ) => void;
  error: IStatus | null;
  disabled?: boolean;
  onCancel?: () => void;
  runStatus?: string;
  inputRequest?: InputRequest;
  isPlanMessage?: boolean;
  onPause?: () => void;
  enable_upload?: boolean;
  onExecutePlan?: (plan: IPlan) => void;
  onSubMenuChange: React.Dispatch<React.SetStateAction<string>>;
  mcpSelectorDisabled: boolean;
  selectedMcpServers: string[];
  onSelectedMcpServersChange: (servers: string[]) => void;
}

const ChatInput = React.forwardRef<{ focus: () => void }, ChatInputProps>(
  (
    {
      onSubmit,
      error,
      disabled = false,
      onCancel,
      runStatus,
      inputRequest,
      isPlanMessage = false,
      onPause,
      enable_upload = false,
      onExecutePlan,
      onSubMenuChange,
      mcpSelectorDisabled,
      selectedMcpServers,
      onSelectedMcpServersChange
    },
    ref
  ) => {
    const textAreaRef = React.useRef<HTMLTextAreaElement>(null);
    const textAreaDivRef = React.useRef<HTMLDivElement>(null);
    const [text, setText] = React.useState("");
    const [fileList, setFileList] = React.useState<UploadFile[]>([]);
    const [dragOver, setDragOver] = React.useState(false);
    const { darkMode, user } = React.useContext(appContext) as {
      darkMode: string;
      user: { email: string };
    };
    const [notificationApi, notificationContextHolder] =
      notification.useNotification();
    const [isSearching, setIsSearching] = React.useState(false);
    const [relevantPlans, setRelevantPlans] = React.useState<any[]>([]);
    const [allPlans, setAllPlans] = React.useState<any[]>([]);
    const [attachedPlan, setAttachedPlan] = React.useState<IPlan | null>(null);
    const [isLoading, setIsLoading] = React.useState(false);
    const userId = user?.email || "default_user";
    const [isRelevantPlansVisible, setIsRelevantPlansVisible] =
      React.useState(false);
    const [isPlanModalVisible, setIsPlanModalVisible] = React.useState(false);
    const textAreaDefaultHeight = "64px";
    const isInputDisabled =
      disabled ||
      runStatus === "active" ||
      runStatus === "pausing" ||
      inputRequest?.input_type === "approval";
    const [mcpServers, setMcpServers] = React.useState<MCPServerInfo[]>([]);
    // Handle textarea auto-resize
    React.useEffect(() => {
      if (textAreaRef.current) {
        textAreaRef.current.style.height = textAreaDefaultHeight;
        const scrollHeight = textAreaRef.current.scrollHeight;
        textAreaRef.current.style.height = `${scrollHeight}px`;
      }
      if (textAreaDivRef.current) {
        textAreaDivRef.current.style.height = textAreaDefaultHeight;
        const scrollHeight = textAreaDivRef.current.scrollHeight;
        textAreaDivRef.current.style.height = `${scrollHeight}px`;
      }
    }, [text, inputRequest]);

    React.useEffect(() => {
      if (!error) {
        resetInput();
      }
    }, [error]);

    React.useEffect(() => {
      if (!isInputDisabled && textAreaRef.current) {
        textAreaRef.current.focus();
      }
    }, [isInputDisabled]);

    React.useEffect(() => {
      const fetchAllPlans = async () => {
        try {
          setIsLoading(true);

          const response = await planAPI.listPlans(userId);

          if (response) {
            if (Array.isArray(response)) {
              setAllPlans(response);
            } else {
              console.warn("Unexpected response format:", response);
            }
          } else {
            console.warn("Empty response received");
          }
        } catch (error) {
          console.error("Error fetching plans:", error);
        } finally {
          setIsLoading(false);
        }
      };
      const fetchMCPServers = async () => {
        if (!user?.email) {
          console.error("User not authenticated");
          setIsLoading(false);
          return;
        }

        try {
          setIsLoading(true);

          // Get user's latest settings from database
          const settings = await settingsAPI.getSettings(user.email);
          const mcpAgentConfigs: MCPAgentConfig[] = settings.mcp_agent_configs || [];
          const mcpServers = extractMcpServers(mcpAgentConfigs);
          setMcpServers(mcpServers);
        } catch (err) {
          console.error("Failed to fetch MCP servers:", err);
        } finally {
          setIsLoading(false);
        }
      };

      fetchMCPServers();
      fetchAllPlans();
    }, [userId, user?.email]);

    // Add paste event listener for images and large text
    const handlePaste = (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
      if (isInputDisabled || !enable_upload) return;

      // Handle image paste
      if (e.clipboardData?.items) {
        let hasImageItem = false;

        for (let i = 0; i < e.clipboardData.items.length; i++) {
          const item = e.clipboardData.items[i];

          // Handle image items
          if (item.type.indexOf("image/") === 0) {
            hasImageItem = true;
            const file = item.getAsFile();

            if (file) {
              // Prevent the default paste behavior for images
              e.preventDefault();

              // Create a unique file name
              const fileName = `pasted-image-${new Date().getTime()}.png`;

              // Create a new File with a proper name
              const namedFile = new File([file], fileName, {
                type: file.type,
              });

              // Convert to the expected UploadFile format
              const uploadFile: UploadFile = {
                uid: `paste-${Date.now()}`,
                name: fileName,
                status: "done",
                size: namedFile.size,
                type: namedFile.type,
                originFileObj: namedFile as RcFile,
              };

              // Add to file list
              setFileList((prev) => [...prev, uploadFile]);

              // Show successful paste notification
              message.success(`File pasted successfully`);
            }
          }

          // Handle text items - only if there's a large amount of text
          if (item.type === "text/plain" && !hasImageItem) {
            item.getAsString((text) => {
              // Only process for large text
              if (text.length > LARGE_TEXT_THRESHOLD) {
                // We need to prevent the default paste behavior
                // But since we're in an async callback, we need to
                // manually clear the textarea's selection value
                setTimeout(() => {
                  if (textAreaRef.current) {
                    const currentValue = textAreaRef.current.value;
                    const selectionStart =
                      textAreaRef.current.selectionStart || 0;
                    const selectionEnd = textAreaRef.current.selectionEnd || 0;

                    // Remove the pasted text from the textarea
                    const newValue =
                      currentValue.substring(0, selectionStart - text.length) +
                      currentValue.substring(selectionEnd);

                    // Update the textarea
                    textAreaRef.current.value = newValue;
                    // Trigger the onChange event manually
                    setText(newValue);
                  }
                }, 0);

                // Prevent default paste for large text
                e.preventDefault();

                // Create a text file from the pasted content
                const blob = new Blob([text], { type: "text/plain" });
                const file = new File(
                  [blob],
                  `pasted-text-${new Date().getTime()}.txt`,
                  { type: "text/plain" }
                );

                // Add to file list
                const uploadFile: UploadFile = {
                  uid: `paste-${Date.now()}`,
                  name: file.name,
                  status: "done",
                  size: file.size,
                  type: file.type,
                  originFileObj: file as RcFile,
                };

                setFileList((prev) => [...prev, uploadFile]);

                // Notify user about the conversion
                notificationApi.info({
                  message: (
                    <span className="text-sm">
                      Large Text Converted to File
                    </span>
                  ),
                  description: (
                    <span className="text-sm text-secondary">
                      Your pasted text has been attached as a file.
                    </span>
                  ),
                  duration: 3,
                });
              }
            });
          }
        }
      }
    };

    const resetInput = () => {
      if (textAreaRef.current) {
        textAreaRef.current.value = "";
        textAreaRef.current.style.height = textAreaDefaultHeight;
        setText("");
        setFileList([]);
        setRelevantPlans([]);
        setAttachedPlan(null);
      }
      if (textAreaDivRef.current) {
        textAreaDivRef.current.style.height = textAreaDefaultHeight;
      }
    };

    const searchableData = React.useMemo(() => {
      return allPlans.map((plan) => ({
        ...plan,
        taskLower: plan.task?.toLowerCase() || "",
        stepTexts:
          plan.steps?.map(
            (step: { title: string; details: string }) =>
              (step.title?.toLowerCase() || "") +
              " " +
              (step.details?.toLowerCase() || "")
          ) || [],
      }));
    }, [allPlans]);

    const searchPlans = React.useCallback(
      debounce((query: string) => {
        // Don't search if query is too short, no plans available, or plan is already attached
        if (
          query.length < 3 ||
          !searchableData ||
          searchableData.length === 0 ||
          attachedPlan
        ) {
          return;
        }

        setIsSearching(true);
        try {
          const searchTerms = query.toLowerCase().split(" ");
          const matchingPlans = searchableData.filter((plan) => {
            if (query.length <= 2) {
              if (plan.taskLower.startsWith(query.toLowerCase())) {
                return true;
              }
            }
            const taskMatches = searchTerms.every((term) =>
              plan.taskLower.includes(term)
            );
            if (taskMatches) {
              return true;
            }

            return plan.stepTexts.some((stepText: string | string[]) =>
              searchTerms.every((term) => stepText.includes(term))
            );
          });

          if (matchingPlans.length > 0) {
            const sortedPlans = matchingPlans.sort((a, b) => {
              return (
                new Date(b.created_at || "").getTime() -
                new Date(a.created_at || "").getTime()
              );
            });
            setRelevantPlans(sortedPlans.slice(0, 5));
            setIsRelevantPlansVisible(true);
          } else {
            setRelevantPlans([]);
            setAttachedPlan(null);
            setIsRelevantPlansVisible(false);
          }
        } catch (error) {
        } finally {
          setIsSearching(false);
        }
      }, 1000),
      [searchableData, runStatus, isPlanMessage, attachedPlan]
    );

    const handleTextChange = (
      event: React.ChangeEvent<HTMLTextAreaElement>
    ) => {
      const newText = event.target.value;
      setText(newText);

      // Clear relevant plans and attached plan as soon as the query changes
      setRelevantPlans([]);

      const shouldSearch = !(
        runStatus === "connected" || runStatus === "awaiting_input"
      );
      if (shouldSearch) {
        searchPlans(newText);
      } else if (relevantPlans.length > 0) {
        // Clear any relevant plans if not in the right state
        setRelevantPlans([]);
        setAttachedPlan(null);
      }
    };

    const submitInternal = (
      query: string,
      files: RcFile[],
      accepted: boolean,
      doResetInput: boolean = true
    ) => {
      if (attachedPlan) {
        onSubmit(query, files, accepted, attachedPlan);
      } else {
        onSubmit(query, files, accepted);
      }

      if (doResetInput) {
        resetInput();
      }
      textAreaRef.current?.focus();
    };

    const handleSubmit = () => {
      if (
        (textAreaRef.current?.value || fileList.length > 0) &&
        !isInputDisabled
      ) {
        const query = textAreaRef.current?.value || "";

        // Get all valid RcFile objects
        const files = fileList
          .filter((file) => file.originFileObj)
          .map((file) => file.originFileObj as RcFile);

        submitInternal(query, files, false);
      }
    };

    const handlePause = () => {
      if (onPause) {
        onPause();
      }
    };

    const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        handleSubmit();
      }
    };

    // Expose focus method via ref
    React.useImperativeHandle(ref, () => ({
      focus: () => {
        textAreaRef.current?.focus();
      },
    }));

    // Add helper function for file addition
    const handleFileAdd = (file: File): boolean => {
      // Add file to fileList
      const uploadFile: UploadFile = {
        uid: `file-${Date.now()}-${file.name}`,
        name: file.name,
        status: "done",
        size: file.size,
        type: file.type,
        originFileObj: file as RcFile,
      };

      setFileList((prev) => [...prev, uploadFile]);
      return true;
    };

    // Update the upload props to use the new helper function
    const uploadProps: UploadProps = {
      name: "file",
      multiple: true,
      fileList,
      beforeUpload: (file: RcFile) => {
        handleFileAdd(file);
        return false; // Prevent automatic upload
      },
      onRemove: (file: UploadFile) => {
        setFileList(fileList.filter((item) => item.uid !== file.uid));
      },
      showUploadList: false, // We'll handle our own custom file preview
      customRequest: (options: any) => {
        // Mock successful upload since we're not actually uploading anywhere yet
        if (options.onSuccess) {
          options.onSuccess("ok", options.file);
        }
      },
    };

    const getFileIcon = (file: UploadFile) => {
      const fileType = file.type || "";
      const fileName = file.name || "";

      if (fileType.startsWith("image/")) {
        return <ImageIcon className="w-4 h-4" />;
      }

      // Check for specific file types based on extension
      const extension = fileName.split(".").pop()?.toLowerCase();
      switch (extension) {
        case "pdf":
          return <FileTextIcon className="w-4 h-4 text-red-500" />;
        case "doc":
        case "docx":
          return <FileTextIcon className="w-4 h-4 text-blue-500" />;
        case "xls":
        case "xlsx":
          return <FileTextIcon className="w-4 h-4 text-green-500" />;
        case "zip":
        case "rar":
        case "7z":
          return <FileTextIcon className="w-4 h-4 text-yellow-500" />;
        default:
          return <FileTextIcon className="w-4 h-4" />;
      }
    };

    // Add drag and drop handlers
    const handleDragOver = (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      if (!isInputDisabled && enable_upload) {
        setDragOver(true);
      }
    };

    const handleDragLeave = (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setDragOver(false);
    };

    // Update the drop handler to use the new helper function
    const handleDrop = async (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setDragOver(false);

      if (isInputDisabled || !enable_upload) return;

      const droppedFiles = Array.from(e.dataTransfer.files);
      droppedFiles.forEach(handleFileAdd);
    };

    const handleUsePlan = (plan: IPlan) => {
      setRelevantPlans([]); // Close the dropdown
      setAttachedPlan(plan);
    };

    const handlePlanClick = () => {
      setIsPlanModalVisible(true);
    };

    const handlePlanModalClose = () => {
      setIsPlanModalVisible(false);
    };

    React.useEffect(() => {
      const handleClickOutside = (e: MouseEvent) => {
        // Only process if dropdown is visible
        if (!isRelevantPlansVisible) return;

        // Get the clicked element
        const target = e.target as Node;

        // Check if click was on textarea or within the plans dropdown
        const textAreaElement = textAreaRef.current;
        const planElement = document.querySelector(
          '[data-component="relevant-plans"]'
        );

        const isClickInsideTextArea =
          textAreaElement && textAreaElement.contains(target);
        const isClickInsidePlans = planElement && planElement.contains(target);

        // Hide dropdown if click is outside both elements
        if (!isClickInsideTextArea && !isClickInsidePlans) {
          setIsRelevantPlansVisible(false);
        }
      };

      // Handle escape key
      const handleKeyDown = (e: KeyboardEvent) => {
        if (e.key === "Escape" && isRelevantPlansVisible) {
          setIsRelevantPlansVisible(false);
        }
      };

      // Add listeners
      document.addEventListener("click", handleClickOutside);
      document.addEventListener("keydown", handleKeyDown);

      return () => {
        document.removeEventListener("click", handleClickOutside);
        document.removeEventListener("keydown", handleKeyDown);
      };
    }, [isRelevantPlansVisible]);

    const goToMcpServersTab = React.useCallback(() => {
      onSubMenuChange("mcp_servers");
    }, [onSubMenuChange]);

    const handleMcpServerSelectionChange = React.useCallback((newSelection: string[]) => {
      onSelectedMcpServersChange(newSelection);
    }, [onSelectedMcpServersChange]);


    return (
      <div className="mt-2 w-full relative">
        {notificationContextHolder}

        {/* Relevant Plans Indicator and Dropdown */}
        {isRelevantPlansVisible && (
          <RelevantPlans
            isSearching={isSearching}
            relevantPlans={relevantPlans}
            darkMode={darkMode}
            onUsePlan={handleUsePlan}
          />
        )}

        {/* Selected MCP Tools Display */}
        {selectedMcpServers.length > 0 && (
          <div
            className={`-mb-2 mx-1 ${darkMode === "dark" ? "bg-[#333333]" : "bg-gray-100"
              } rounded-t border-b-0 p-2 flex border flex-wrap gap-2`}
          >
            {selectedMcpServers.map((serverName) => (
              <div
                key={serverName}
                className={`flex items-center gap-1 ${darkMode === "dark"
                  ? "bg-[#444444] text-white"
                  : "bg-white text-black"
                  } rounded px-2 py-1 text-xs`}
              >
                <span className="truncate max-w-[150px]">🔧 {serverName}</span>
                {runStatus === "created" && (
                  <Button
                    type="text"
                    size="small"
                    className="p-0 ml-1 flex items-center justify-center"
                    onClick={() =>
                      onSelectedMcpServersChange(
                        selectedMcpServers.filter((s) => s !== serverName)
                      )
                    }
                    icon={<XIcon className="w-3 h-3" />}
                  />
                )}
              </div>
            ))}
          </div>
        )}

        {/* Attached Items Preview */}
        {(attachedPlan || fileList.length > 0) && (
          <div
            className={`${selectedMcpServers.length > 0 ? '-mt-2' : '-mb-2'} mx-1 ${darkMode === "dark" ? "bg-[#333333]" : "bg-gray-100"
              } ${selectedMcpServers.length > 0 ? 'rounded-b border-t-0' : 'rounded-t border-b-0'} p-2 flex border flex-wrap gap-2`}
          >
            {/* Attached Plan */}
            {attachedPlan && (
              <div
                className={`flex items-center gap-1 ${darkMode === "dark"
                  ? "bg-[#444444] text-white"
                  : "bg-white text-black"
                  } rounded px-2 py-1 text-xs cursor-pointer hover:opacity-80 transition-opacity`}
                onClick={handlePlanClick}
              >
                <span className="truncate max-w-[150px]">
                  📋 {attachedPlan.task}
                </span>
                <Button
                  type="text"
                  size="small"
                  className="p-0 ml-1 flex items-center justify-center"
                  onClick={(e: { stopPropagation: () => void }) => {
                    e.stopPropagation();
                    setAttachedPlan(null);
                  }}
                  icon={<XIcon className="w-3 h-3" />}
                />
              </div>
            )}

            {/* Attached Files */}
            {fileList.map((file) => (
              <div
                key={file.uid}
                className={`flex items-center gap-1 ${darkMode === "dark"
                  ? "bg-[#444444] text-white"
                  : "bg-white text-black"
                  } rounded px-2 py-1 text-xs`}
              >
                {getFileIcon(file)}
                <span className="truncate max-w-[150px]">{file.name}</span>
                <Button
                  type="text"
                  size="small"
                  className="p-0 ml-1 flex items-center justify-center"
                  onClick={() =>
                    setFileList((prev) =>
                      prev.filter((f) => f.uid !== file.uid)
                    )
                  }
                  icon={<XIcon className="w-3 h-3" />}
                />
              </div>
            ))}
          </div>
        )}

        {/* Plan View Modal */}
        <Modal
          title={`Plan: ${attachedPlan?.task || "Untitled Plan"}`}
          open={isPlanModalVisible}
          onCancel={handlePlanModalClose}
          footer={null}
          width={800}
          destroyOnClose
        >
          {attachedPlan && (
            <PlanView
              task={attachedPlan.task || ""}
              plan={attachedPlan.steps || []}
              viewOnly={true}
              setPlan={() => { }}
            />
          )}
        </Modal>

        <div className="mt-2 rounded shadow-sm flex">
          <div
            className={`flex w-full ${dragOver ? "opacity-50" : ""}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            <div className="flex w-full">
              <div className="flex-1">
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    handleSubmit();
                  }}
                >
                  <textarea
                    id="queryInput"
                    name="queryInput"
                    onPaste={handlePaste}
                    ref={textAreaRef}
                    defaultValue={""}
                    onChange={handleTextChange}
                    onKeyDown={handleKeyDown}
                    className={`flex items-center w-full resize-none border-l border-t border-b border-accent p-2 pl-5 rounded-l-lg ${darkMode === "dark"
                      ? "bg-[#444444] text-white"
                      : "bg-white text-black"
                      } ${isInputDisabled ? "cursor-not-allowed" : ""
                      } focus:outline-none`}
                    style={{
                      maxHeight: "120px",
                      overflowY: "auto",
                      minHeight: "50px",
                    }}
                    placeholder={
                      runStatus === "awaiting_input"
                        ? "Type your response here and let Magentic-UI know of any changes in the browser."
                        : enable_upload
                          ? dragOver
                            ? "Drop files here..."
                            : "Type your message here..."
                          : "Type your message here..."
                    }
                    disabled={isInputDisabled}
                  />
                </form>
              </div>

              <div
                className={`flex items-center justify-center gap-2 border-t border-r border-b border-accent px-2 rounded-r-lg ${darkMode === "dark"
                  ? "bg-[#444444] text-white"
                  : "bg-white text-black"
                  }`}
              >

                {runStatus === "created" && (
                  <McpServerSelector
                    servers={mcpServers}
                    onAddMcpServer={goToMcpServersTab}
                    runStatus={runStatus}
                    value={selectedMcpServers}
                    onChange={handleMcpServerSelectionChange}
                  />
                )}

                {/* File upload button replaced with Dropdown */}
                {enable_upload && (
                  <div
                    className={`${isInputDisabled ? "pointer-events-none opacity-50" : ""
                      }`}
                  >
                    <Dropdown
                      overlay={
                        <Menu>
                          <Menu.Item
                            key="attach-file"
                            className="!py-0 !my-0 !h-8"
                          >
                            <Upload {...uploadProps} showUploadList={false}>
                              <span className="flex items-center gap-2">
                                <PaperclipIcon className="w-4 h-4" />
                                Attach File
                              </span>
                            </Upload>
                          </Menu.Item>
                          <Menu.Divider />
                          <Menu.SubMenu key="attach-plan" title="Attach Plan">
                            {allPlans.length === 0 ? (
                              <Menu.Item disabled key="no-plans">
                                No plans available
                              </Menu.Item>
                            ) : (
                              allPlans.map((plan: any) => (
                                <Menu.Item
                                  key={plan.id || plan.task}
                                  onClick={() => handleUsePlan(plan)}
                                >
                                  {plan.task}
                                </Menu.Item>
                              ))
                            )}
                          </Menu.SubMenu>
                        </Menu>
                      }
                      trigger={["click"]}
                    >
                      <Tooltip
                        title={
                          <span className="text-sm">Attach File or Plan</span>
                        }
                        placement="top"
                      >
                        <button
                          type="button"
                          disabled={isInputDisabled}
                          className="flex justify-center items-center transition duration-300"
                        >
                          <UploadIcon className="h-6 -mt-1 w-6 text-accent" />
                        </button>
                      </Tooltip>
                    </Dropdown>
                  </div>
                )}

                {runStatus === "active" && (
                  <button
                    type="button"
                    onClick={handlePause}
                    className="bg-magenta-800 hover:bg-magenta-900 text-white rounded flex justify-center items-center w-11 h-9 transition duration-300"
                  >
                    <PauseCircleIcon className="h-6 w-6" />
                  </button>
                )}
                {
                  <button
                    type="button"
                    onClick={handleSubmit}
                    disabled={isInputDisabled}
                    className={`bg-magenta-800 transition duration-300 rounded flex justify-center items-center w-11 h-9 ${isInputDisabled
                      ? "cursor-not-allowed"
                      : "hover:bg-magenta-900"
                      }`}
                  >
                    <PaperAirplaneIcon className="h-6 w-6 text-white" />
                  </button>
                }
              </div>
            </div>
          </div>
        </div>

        {error && !error.status && (
          <div className="p-2 border rounded mt-4 text-orange-500 text-sm">
            <ExclamationTriangleIcon className="h-5 text-orange-500 inline-block mr-2" />
            {error.message}
          </div>
        )}
      </div>
    );
  }
);

export default ChatInput;