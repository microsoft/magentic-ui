import React, {
  useState,
  Dispatch,
  SetStateAction,
  useEffect,
  useContext,
  useCallback,
} from "react";
import { ChevronDownIcon, PlusIcon } from "@heroicons/react/24/outline";
import { ClipboardList, Moon, Timer } from "lucide-react";
import {
  DragDropContext,
  Droppable,
  Draggable,
  DropResult,
} from "@hello-pangea/dnd";
import { Trash2 } from "lucide-react";
import { appContext } from "../../../hooks/provider";
import { IPlanStep } from "../../types/plan";
import AutoResizeTextarea from "../../common/AutoResizeTextarea";
import {
  CoderIcon,
  FileSurferIcon,
  WebSurferIcon,
  UserIcon,
  AgentIcon,
} from "../../common/Icon";

// Debounce hook
const useDebounce = (callback: Function, delay: number) => {
  const timeoutRef = React.useRef<NodeJS.Timeout>();

  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  return useCallback(
    (...args: any[]) => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }

      timeoutRef.current = setTimeout(() => {
        callback(...args);
      }, delay);
    },
    [callback, delay]
  );
};

// Utility functions for sentinel steps
const isSentinelStep = (step: IPlanStep): boolean => {
  return step.sleep_duration !== undefined && step.condition !== undefined;
};

const formatDuration = (seconds: number): string => {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remainingSeconds = seconds % 60;

  const parts = [];
  if (hours > 0) parts.push(`${hours}h`);
  if (minutes > 0) parts.push(`${minutes}m`);
  if (remainingSeconds > 0 || parts.length === 0) parts.push(`${remainingSeconds}s`);

  return parts.join(' ');
};

const formatCondition = (condition: number | string): { display: string; isTruncated: boolean } => {
  if (typeof condition === 'number') {
    return { display: `Run ${condition} times`, isTruncated: false };
  }

  const maxLength = 50;
  if (condition.length <= maxLength) {
    return { display: condition, isTruncated: false };
  }

  return { display: `${condition.substring(0, maxLength)}...`, isTruncated: true };
};

const validateSleepDuration = (value: string): boolean => {
  const num = parseInt(value);
  return !isNaN(num) && num >= 1 && num <= 86400; // 1 second to 24 hours
};

const validateCondition = (value: string): boolean => {
  if (!value.trim()) return false;

  // If it's a number, validate as positive integer
  const num = parseInt(value);
  if (!isNaN(num)) {
    return num > 0;
  }

  // If it's a string, check length
  return value.trim().length >= 3 && value.trim().length <= 200;
};

interface PlanProps {
  task: string;
  fromMemory?: boolean;
  plan: IPlanStep[];
  setPlan: Dispatch<SetStateAction<IPlanStep[]>>;
  viewOnly?: boolean;
  onSavePlan?: (plan: IPlanStep[]) => void;
  onRegeneratePlan?: () => void;
  isCollapsed?: boolean;
  forceCollapsed?: boolean;
}

const PlanView: React.FC<PlanProps> = ({
  task = "Untitled",
  fromMemory = false,
  plan,
  setPlan,
  viewOnly = true,
  onSavePlan,
  onRegeneratePlan,
  isCollapsed: initialIsCollapsed = false,
  forceCollapsed = false,
}) => {
  const [localPlan, setLocalPlan] = useState<IPlanStep[]>([]);
  const [isCollapsed, setIsCollapsed] = useState(
    viewOnly && (initialIsCollapsed || forceCollapsed)
  );
  const { user } = useContext(appContext);
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const [focusedIndex, setFocusedIndex] = useState<number | null>(null);
  const [saveStatus, setSaveStatus] = useState<"saved" | "saving" | "error">(
    "saved"
  );
  const [expandedConditions, setExpandedConditions] = useState<{ [key: number]: boolean }>({});
  const [showSentinelTooltip, setShowSentinelTooltip] = useState<{ [key: number]: boolean }>({});

  useEffect(() => {
    if (forceCollapsed && !isCollapsed) {
      setIsCollapsed(true);
    }
  }, [forceCollapsed]);

  // Debounced save function
  const debouncedSave = useDebounce((newPlan: IPlanStep[]) => {
    setPlan(newPlan);
    if (onSavePlan) {
      onSavePlan(newPlan);
    }
    setSaveStatus("saved");
  }, 1000);

  useEffect(() => {
    if (plan && plan.length > 0) {
      setLocalPlan(JSON.parse(JSON.stringify(plan)));
    } else {
      setLocalPlan([]);
    }
  }, [plan]);

  const handlePlanChange = (newPlan: IPlanStep[]) => {
    setLocalPlan(newPlan);
    setSaveStatus("saving");
    debouncedSave(newPlan);
  };

  const updateDetails = (index: number, value: string) => {
    const newPlan = [...localPlan];
    newPlan[index] = {
      ...newPlan[index],
      details: value,
      title: value, // Update title to match details
      agent_name: "", // Reset agent_name when step is edited
    };
    handlePlanChange(newPlan);
  };

  const updateSleepDuration = (index: number, value: string) => {
    if (!validateSleepDuration(value)) return;

    const newPlan = [...localPlan];
    newPlan[index] = {
      ...newPlan[index],
      sleep_duration: parseInt(value),
    };
    handlePlanChange(newPlan);
  };

  const updateCondition = (index: number, value: string) => {
    if (!validateCondition(value)) return;

    const newPlan = [...localPlan];
    const numValue = parseInt(value);
    newPlan[index] = {
      ...newPlan[index],
      condition: !isNaN(numValue) ? numValue : value.trim(),
    };
    handlePlanChange(newPlan);
  };

  const toggleConditionExpansion = (index: number) => {
    setExpandedConditions(prev => ({
      ...prev,
      [index]: !prev[index]
    }));
  };

  const toggleSentinelTooltip = (index: number) => {
    setShowSentinelTooltip(prev => ({
      ...prev,
      [index]: !prev[index]
    }));
  };

  const deleteLocalPlan = (index: number) => {
    const newPlan = localPlan.filter((_, i) => i !== index);
    handlePlanChange(newPlan);
  };

  const addLocalPlan = () => {
    const newPlan = [
      ...localPlan,
      {
        title: "",
        details: "",
        enabled: true,
        agent_name: "",
      },
    ];
    handlePlanChange(newPlan);
  };

  const onDragEnd = (result: DropResult) => {
    if (!result.destination) return;

    const items = Array.from(localPlan);
    const [reorderedItem] = items.splice(result.source.index, 1);
    items.splice(result.destination.index, 0, reorderedItem);

    handlePlanChange(items);
  };

  const getAgentIcon = (agentName: string | undefined): JSX.Element | null => {
    const lowerCaseName = (agentName || "").toLowerCase();
    if (lowerCaseName === "coder_agent") return <CoderIcon tooltip="Coder" />;
    if (lowerCaseName === "web_surfer")
      return <WebSurferIcon tooltip="WebSurfer" />;
    if (lowerCaseName === "file_surfer")
      return <FileSurferIcon tooltip="FileSurfer" />;
    if (lowerCaseName === "user_proxy") return <UserIcon tooltip="User" />;
    if (lowerCaseName === "no_action_agent")
      return <AgentIcon tooltip="Self-Reflection" />;
    return <AgentIcon tooltip="Agent" />;
  };

  const getAgentName = (agentName: string | undefined): string => {
    const lowerCaseName = (agentName || "").toLowerCase();
    if (lowerCaseName === "coder_agent") return "Coder";
    if (lowerCaseName === "web_surfer") return "WebSurfer";
    if (lowerCaseName === "file_surfer") return "FileSurfer";
    if (lowerCaseName === "user_proxy") return "User";
    if (lowerCaseName === "no_action_agent") return "Self-Reflection";
    return agentName || "Agent";
  };

  const noop = () => { };

  return (
    <>
      {!viewOnly && onRegeneratePlan && (
        <div className="flex items-center mb-2">
          <ClipboardList className="h-5 w-5 mr-2 flex-shrink-0" />
          {fromMemory
            ? "Potentially relevant plan retrieved from memory. "
            : "Here's a plan. "}
          <span> You can edit it directly or through the chat.</span>
        </div>
      )}
      <div className="rounded-none border-[var(--color-border-primary)]">
        {viewOnly && isCollapsed ? (
          <div
            className="flex items-center hover:opacity-80 cursor-pointer opacity-50"
            onClick={() => setIsCollapsed(false)}
          >
            <ClipboardList className="h-5 w-5 mr-2 flex-shrink-0" />
            <h2 className="">Plan for: {task}</h2>
          </div>
        ) : (
          <>
            {onRegeneratePlan && !viewOnly ? (
              <div className="flex justify-between items-center mb-2">
                <h2 className="font-semibold"></h2>
              </div>
            ) : (
              <div className="flex justify-between items-center">
                <div
                  className={`flex items-center ${viewOnly ? "hover:opacity-80 cursor-pointer" : ""
                    }`}
                  onClick={viewOnly ? () => setIsCollapsed(true) : undefined}
                >
                  {viewOnly && (
                    <ClipboardList className="h-5 w-5 mr-2 flex-shrink-0" />
                  )}
                  <h2 className="">Plan for: {task}</h2>
                </div>
              </div>
            )}
            <DragDropContext onDragEnd={!viewOnly ? onDragEnd : noop}>
              <Droppable droppableId="plan">
                {(provided) => (
                  <div {...provided.droppableProps} ref={provided.innerRef}>
                    {localPlan.map((item, index) => (
                      <Draggable
                        key={`draggable-${index}`}
                        draggableId={`draggable-${index}`}
                        index={index}
                        isDragDisabled={viewOnly}
                      >
                        {(provided) => (
                          <div
                            ref={provided.innerRef}
                            {...provided.draggableProps}
                            className="flex flex-row gap-2"
                            onMouseEnter={() => setHoveredIndex(index)}
                            onMouseLeave={() => setHoveredIndex(null)}
                          >
                            <div className="flex items-center">
                              <span
                                {...(!viewOnly ? provided.dragHandleProps : {})}
                                className={`flex items-center justify-center  font-semibold p-1.5 ${!viewOnly ? "cursor-grab" : ""
                                  }`}
                              >
                                Step {index + 1}
                              </span>
                              <div className="flex items-center ml-2">
                                <div className="text-gray-600 dark:text-gray-300">
                                  {React.cloneElement(
                                    getAgentIcon(item.agent_name) || (
                                      <AgentIcon />
                                    ),
                                    {
                                      tooltip: getAgentName(item.agent_name),
                                    }
                                  )}
                                </div>
                              </div>
                              {/* Sentinel Step Indicator */}
                              {isSentinelStep(item) && (
                                <div className="relative ml-2">
                                  <ClipboardList
                                    className="h-4 w-4 text-purple-600 dark:text-purple-400 cursor-pointer hover:text-purple-800 dark:hover:text-purple-200 transition-colors"
                                    onClick={() => toggleSentinelTooltip(index)}
                                    title="Sentinel Step - Click for details"
                                  />
                                  {/* Tooltip */}
                                  {showSentinelTooltip[index] && (
                                    <div className="absolute top-6 left-0 z-10 bg-gray-900 dark:bg-gray-700 text-white text-xs rounded-lg p-3 shadow-lg min-w-[200px]">
                                      <div className="flex items-center mb-2">
                                        <Moon className="h-3 w-3 mr-2 text-blue-300" />
                                        <span className="font-medium">Sleep: {formatDuration(item.sleep_duration!)}</span>
                                      </div>
                                      <div className="flex items-start">
                                        <Timer className="h-3 w-3 mr-2 mt-0.5 text-purple-300 flex-shrink-0" />
                                        <div>
                                          <span className="font-medium">Condition: </span>
                                          <span className="break-words">
                                            {typeof item.condition === 'number'
                                              ? `Run ${item.condition} times`
                                              : item.condition}
                                          </span>
                                        </div>
                                      </div>
                                      {/* Close button */}
                                      <button
                                        onClick={() => toggleSentinelTooltip(index)}
                                        className="absolute -top-1 -right-1 bg-gray-600 hover:bg-gray-500 text-white rounded-full w-4 h-4 flex items-center justify-center text-xs"
                                      >
                                        ×
                                      </button>
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                            <div className="border-transparent p-1  px-2 mt-2.5 flex-1 rounded">
                              <div className="flex items-center">
                                {
                                  <AutoResizeTextarea
                                    key={`textarea-${index}`}
                                    value={item.details}
                                    onChange={(
                                      e: React.ChangeEvent<HTMLTextAreaElement>
                                    ) => updateDetails(index, e.target.value)}
                                    onBlur={() => setFocusedIndex(null)}
                                    autoFocus
                                    className={`flex-1 p-2 min-w-[100px] max-w-full resize-y bg-[var(--color-bg-secondary)] text-[var(--color-text-primary)] rounded ${!item.details.trim()
                                        ? "border border-orange-300"
                                        : ""
                                      } ${viewOnly
                                        ? "cursor-default focus:outline-none"
                                        : ""
                                      }`}
                                    readOnly={viewOnly}
                                    placeholder="Enter step details"
                                  />
                                }
                                {!viewOnly && (
                                  <div
                                    className={`flex items-center transition-opacity ${hoveredIndex === index
                                        ? "opacity-100"
                                        : "opacity-0"
                                      }`}
                                  >
                                    <Trash2
                                      role="button"
                                      onClick={() => deleteLocalPlan(index)}
                                      className="h-5 w-5 text-[var(--color-text-secondary)] ml-2 hover:text-red-500"
                                    />
                                  </div>
                                )}
                              </div>
                              {/* Sentinel Step Editable Fields */}
                              {isSentinelStep(item) && !viewOnly && (
                                <div className="mt-3 space-y-2 border-t border-gray-200 dark:border-gray-700 pt-3">
                                  <div className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-2">
                                    Sentinel Step Configuration
                                  </div>
                                  <div className="grid grid-cols-2 gap-3">
                                    {/* Sleep Duration Input */}
                                    <div>
                                      <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                                        Sleep Duration (seconds)
                                      </label>
                                      <input
                                        type="number"
                                        min="1"
                                        max="86400"
                                        value={item.sleep_duration || ''}
                                        onChange={(e) => updateSleepDuration(index, e.target.value)}
                                        className="w-full px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                                        placeholder="e.g., 3600"
                                      />
                                      <div className="text-xs text-gray-500 mt-1">
                                        Display: {item.sleep_duration ? formatDuration(item.sleep_duration) : 'Not set'}
                                      </div>
                                    </div>
                                    {/* Condition Input */}
                                    <div>
                                      <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                                        Condition
                                      </label>
                                      <input
                                        type="text"
                                        value={typeof item.condition === 'number' ? item.condition.toString() : (item.condition || '')}
                                        onChange={(e) => updateCondition(index, e.target.value)}
                                        className="w-full px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                                        placeholder="e.g., 5 or 'until condition met'"
                                      />
                                      <div className="text-xs text-gray-500 mt-1">
                                        {typeof item.condition === 'number'
                                          ? `Will run ${item.condition} times`
                                          : 'String condition'
                                        }
                                      </div>
                                    </div>
                                  </div>
                                </div>
                              )}
                            </div>
                          </div>
                        )}
                      </Draggable>
                    ))}
                    {provided.placeholder}
                  </div>
                )}
              </Droppable>
            </DragDropContext>
            {!viewOnly && (
              <div className="mt-2 p-0 flex justify-end">
                <div className="flex gap-4 items-center">
                  <span className="mt-1 text-[var(--color-text-secondary)] px-2">
                    {saveStatus === "saving" && "Saving..."}
                    {saveStatus === "saved" && ""}
                    {saveStatus === "error" && "Error saving changes"}
                  </span>
                  <div
                    onClick={addLocalPlan}
                    className="mt-2 flex items-center text-[var(--color-text-secondary)] px-4 rounded hover:text-[var(--color-text-primary)] cursor-pointer"
                  >
                    <PlusIcon className="h-5 w-5 mr-2" />
                    Add Step
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </>
  );
};

export default PlanView;
