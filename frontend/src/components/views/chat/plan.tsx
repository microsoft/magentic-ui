import React, {
  useState,
  Dispatch,
  SetStateAction,
  useEffect,
  useContext,
  useCallback,
} from "react";
import { ChevronDownIcon, PlusIcon } from "@heroicons/react/24/outline";
import { ClipboardList } from "lucide-react";
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

  const noop = () => {};

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
                  className={`flex items-center ${
                    viewOnly ? "hover:opacity-80 cursor-pointer" : ""
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
                                className={`flex items-center justify-center  font-semibold p-1.5 ${
                                  !viewOnly ? "cursor-grab" : ""
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
                                    className={`flex-1 p-2 min-w-[100px] max-w-full resize-y bg-[var(--color-bg-secondary)] text-[var(--color-text-primary)] rounded ${
                                      !item.details.trim()
                                        ? "border border-orange-300"
                                        : ""
                                    } ${
                                      viewOnly
                                        ? "cursor-default focus:outline-none"
                                        : ""
                                    }`}
                                    readOnly={viewOnly}
                                    placeholder="Enter step details"
                                  />
                                }
                                {!viewOnly && (
                                  <div
                                    className={`flex items-center transition-opacity ${
                                      hoveredIndex === index
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
