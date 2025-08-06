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
import { useTranslation } from "react-i18next";
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
  const { t } = useTranslation();
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
    if (lowerCaseName === "coder_agent") return <CoderIcon tooltip={t("agents.coder")} />;
    if (lowerCaseName === "web_surfer") return <WebSurferIcon tooltip={t("agents.webSurfer")} />;
    if (lowerCaseName === "file_surfer") return <FileSurferIcon tooltip={t("agents.fileSurfer")} />;
    if (lowerCaseName === "user_proxy") return <UserIcon tooltip={t("agents.user")} />;
    if (lowerCaseName === "no_action_agent") return <AgentIcon tooltip={t("agents.selfReflection")} />;
    return <AgentIcon tooltip={t("agents.agent")} />;
  };

  const getAgentName = (agentName: string | undefined): string => {
    const lowerCaseName = (agentName || "").toLowerCase();
    if (lowerCaseName === "coder_agent") return t("agents.coder");
    if (lowerCaseName === "web_surfer") return t("agents.webSurfer");
    if (lowerCaseName === "file_surfer") return t("agents.fileSurfer");
    if (lowerCaseName === "user_proxy") return t("agents.user");
    if (lowerCaseName === "no_action_agent") return t("agents.selfReflection");
    return agentName || t("agents.agent");
  };

  const noop = () => {};

  return (
    <>
      {!viewOnly && onRegeneratePlan && (
        <div className="flex items-center mb-2">
          <ClipboardList className="h-5 w-5 mr-2 flex-shrink-0" />
          {fromMemory
            ? t("planView.potentiallyRelevantPlanFromMemory")
            : t("planView.heresAPlan")}
          <span> {t("planView.youCanEditDirectlyOrThroughChat")}</span>
        </div>
      )}
      <div className="rounded-none border-[var(--color-border-primary)]">
        {viewOnly && isCollapsed ? (
          <div
            className="flex items-center hover:opacity-80 cursor-pointer opacity-50"
            onClick={() => setIsCollapsed(false)}
          >
            <ClipboardList className="h-5 w-5 mr-2 flex-shrink-0" />
            <h2 className="line-through">{t("planView.planFor")} {task === "Untitled" ? t("planCard.untitledPlan") : task}</h2>
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
                  <h2 className="">{t("planView.planFor")} {task === "Untitled" ? t("planCard.untitledPlan") : task}</h2>
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
                                {t("planView.step")} {index + 1}
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
                                    placeholder={t("planView.enterStepDetails")}
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
                                {saveStatus === "saving" && t("planView.saving")}
            {saveStatus === "saved" && ""}
            {saveStatus === "error" && t("planView.errorSavingChanges")}
                  </span>
                  <div
                    onClick={addLocalPlan}
                    className="mt-2 flex items-center text-[var(--color-text-secondary)] px-4 rounded hover:text-[var(--color-text-primary)] cursor-pointer"
                  >
                    <PlusIcon className="h-5 w-5 mr-2" />
                    {t("planView.addStep")}
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
