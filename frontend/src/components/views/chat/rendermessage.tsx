import React, { useState, memo, useEffect } from "react";
import {
  Globe2,
  ChevronDown,
  ChevronRight,
  AlertTriangle,
  FileTextIcon,
  ImageIcon,
  CheckCircle,
  RefreshCw,
  Clock,
} from "lucide-react";
import {
  AgentMessageConfig,
  FunctionCall,
  FunctionExecutionResult,
  ImageContent,
} from "../../types/datamodel";
import { ClickableImage } from "../atoms";
import MarkdownRenderer from "../../common/markdownrender";
import PlanView from "./plan";
import { IPlanStep, convertToIPlanSteps } from "../../types/plan";
import RenderFile from "../../common/filerenderer";
import LearnPlanButton from "../../features/Plans/LearnPlanButton";

// Types
interface MessageProps {
  message: AgentMessageConfig;
  sessionId: number;
  messageIdx: number;
  isLast?: boolean;
  className?: string;
  isEditable?: boolean;
  hidden?: boolean;
  is_step_repeated?: boolean;
  is_step_failed?: boolean;
  onSavePlan?: (plan: IPlanStep[]) => void;
  onImageClick?: (index: number) => void;
  onToggleHide?: (expanded: boolean) => void;
  onRegeneratePlan?: () => void;
  runStatus?: string;
  forceCollapsed?: boolean;
}

interface RenderPlanProps {
  content: any;
  isEditable: boolean;
  onSavePlan?: (plan: IPlanStep[]) => void;
  onRegeneratePlan?: () => void;
  forceCollapsed?: boolean;
}

interface RenderStepExecutionProps {
  content: {
    index: number;
    title: string;
    plan_length: number;
    agent_name: string;
    instruction?: string;
    progress_summary: string;
    details: string;
  };
  hidden?: boolean;
  is_step_repeated?: boolean;
  is_step_failed?: boolean;
  runStatus: string;
  onToggleHide?: (expanded: boolean) => void;
}

interface ParsedContent {
  text:
    | string
    | FunctionCall[]
    | (string | ImageContent)[]
    | FunctionExecutionResult[];
  metadata?: Record<string, string>;
  plan?: IPlanStep[];
}

interface AttachedFile {
  name: string;
  type: string;
}

// Helper functions
const getImageSource = (item: ImageContent): string => {
  if (item.url) return item.url;
  if (item.data) return `data:image/png;base64,${item.data}`;
  return "/api/placeholder/400/320";
};

const getStepIcon = (
  status: string,
  runStatus: string,
  is_step_repeated?: boolean,
  is_step_failed?: boolean
) => {
  if (is_step_failed)
    return <AlertTriangle size={16} className="text-magenta-800" />;
  if (is_step_repeated)
    return <AlertTriangle size={16} className="text-magenta-800" />;
  if (status === "completed")
    return <CheckCircle size={16} className="text-magenta-800" />;
  if (status === "current" && runStatus === "active")
    return <RefreshCw size={16} className="text-magenta-800 animate-spin" />;
  if (status === "upcoming")
    return <Clock size={16} className="text-gray-400" />;
  if (status === "failed")
    return <AlertTriangle size={16} className="text-magenta-500" />;
  return null;
};

const parseUserContent = (content: AgentMessageConfig): ParsedContent => {
  const message_content = content.content;

  if (Array.isArray(message_content)) {
    return { text: message_content, metadata: content.metadata };
  }

  // If content is not a string, convert it to string
  if (typeof message_content !== "string") {
    return { text: String(message_content), metadata: content.metadata };
  }

  try {
    const parsedContent = JSON.parse(message_content);

    // Handle case where content is in content field
    if (parsedContent.content) {
      const text = parsedContent.content?.content || parsedContent.content;
      // If text is an array, it might contain images
      if (Array.isArray(text)) {
        return { text, metadata: content.metadata };
      }
      return { text, metadata: content.metadata };
    }

    // Handle case where plan exists
    let planSteps: IPlanStep[] = [];
    if (parsedContent.plan && typeof parsedContent.plan === "string") {
      try {
        planSteps = convertToIPlanSteps(parsedContent.plan);
      } catch (e) {
        console.error("Failed to parse plan:", e);
        planSteps = [];
      }
    }

    // Return both the content and plan if they exist
    return {
      text: parsedContent.content || content,
      plan: planSteps.length > 0 ? planSteps : undefined,
      metadata: content.metadata,
    };
  } catch (e) {
    // If JSON parsing fails, return original content
    return { text: message_content, metadata: content.metadata };
  }
};

const parseContent = (content: any): string => {
  if (typeof content !== "string") return String(content);

  try {
    const parsedContent = JSON.parse(content);
    return parsedContent.content?.content || parsedContent.content || content;
  } catch {
    return content;
  }
};

const parseorchestratorContent = (
  content: string,
  metadata?: Record<string, any>
) => {
  if (messageUtils.isFinalAnswer(metadata)) {
    return {
      type: "final-answer" as const,
      content: content.substring("Final Answer:".length).trim(),
    };
  }

  try {
    const parsedContent = JSON.parse(content);
    if (messageUtils.isPlanMessage(metadata)) {
      return { type: "plan" as const, content: parsedContent };
    }
    if (messageUtils.isStepExecution(metadata)) {
      return { type: "step-execution" as const, content: parsedContent };
    }
  } catch {}

  return { type: "default" as const, content };
};

const RenderMultiModalBrowserStep: React.FC<{
  content: (string | ImageContent)[];
  onImageClick?: (index: number) => void;
}> = memo(({ content, onImageClick }) => (
  <div className="text-sm">
    {content.map((item, index) => {
      if (typeof item !== "string") return null;

      const hasNextImage =
        index < content.length - 1 && typeof content[index + 1] === "object";

      return (
        <div key={index} className="relative pl-4">
          {/* Full-height connector line */}
          <div
            className="absolute top-0 bottom-0 left-0 w-2 border-l-[2px] border-b-[2px] rounded-bl-lg"
            style={{ borderColor: "var(--color-border-secondary)" }}
          />

          {/* Content container */}
          <div className="flex items-center h-full">
            {hasNextImage && (
              <div className="flex-shrink-0 mr-1 -ml-1 mt-2">
                <Globe2
                  size={16}
                  className="text-magenta-800 hover:text-magenta-900 cursor-pointer"
                  onClick={() => onImageClick?.(index)}
                />
              </div>
            )}

            {/* Text content */}
            <div
              className="flex-1 cursor-pointer mt-2"
              onClick={() => onImageClick?.(index)}
            >
              <MarkdownRenderer content={item} indented={true} />
            </div>
          </div>
        </div>
      );
    })}
  </div>
));

const RenderMultiModal: React.FC<{
  content: (string | ImageContent)[];
}> = memo(({ content }) => (
  <div className="space-y-2 text-sm">
    {content.map((item, index) => (
      <div key={index}>
        {typeof item === "string" ? (
          <MarkdownRenderer content={item} indented={true} />
        ) : (
          <ClickableImage
            src={getImageSource(item)}
            alt={`Content ${index}`}
            className="max-w-[400px]  max-h-[30vh] rounded-lg"
          />
        )}
      </div>
    ))}
  </div>
));

const RenderToolCall: React.FC<{ content: FunctionCall[] }> = memo(
  ({ content }) => (
    <div className="space-y-2 text-sm">
      {content.map((call) => (
        <div key={call.id} className="border border-secondary rounded p-2">
          <div className="font-medium">Function: {call.name}</div>
          <MarkdownRenderer
            content={JSON.stringify(JSON.parse(call.arguments), null, 2)}
            indented={true}
          />
        </div>
      ))}
    </div>
  )
);

const RenderToolResult: React.FC<{ content: FunctionExecutionResult[] }> = memo(
  ({ content }) => {
    const [expandedResults, setExpandedResults] = useState<{ [key: string]: boolean }>({});

    const toggleExpand = (callId: string) => {
      setExpandedResults(prev => ({
        ...prev,
        [callId]: !prev[callId]
      }));
    };

    return (
      <div className="space-y-2 text-sm">
        {content.map((result) => {
          const isExpanded = expandedResults[result.call_id];
          const displayContent = isExpanded ? result.content : result.content.slice(0, 100) + (result.content.length > 100 ? "..." : "");

          return (
            <div key={result.call_id} className="rounded p-2">
              <div className="font-medium">Result ID: {result.call_id}</div>
              <div 
                className="cursor-pointer hover:bg-secondary/50 rounded p-1"
                onClick={() => toggleExpand(result.call_id)}
              >
                <MarkdownRenderer content={displayContent} indented={true} />
                {result.content.length > 100 && (
                  <div className="text-xs text-gray-500 mt-1">
                    {isExpanded ? "Click to minimize" : "Click to expand"}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    );
  }
);

const RenderPlan: React.FC<RenderPlanProps> = memo(
  ({ content, isEditable, onSavePlan, onRegeneratePlan, forceCollapsed }) => {
    // Make sure content.steps is an array before using it
    const initialSteps = Array.isArray(content.steps) ? content.steps : [];

    // Convert to IPlanStep[] if needed
    const initialPlanSteps: IPlanStep[] = initialSteps.map((step: any) => ({
      title: step.title || "",
      details: step.details || "",
      enabled: step.enabled !== false,
      open: step.open || false,
      agent_name: step.agent_name || "",
      // Include sentinel fields if present
      ...(step.sleep_duration !== undefined && { sleep_duration: step.sleep_duration }),
      ...(step.condition !== undefined && { condition: step.condition }),
    }));

    const [planSteps, setPlanSteps] = useState<IPlanStep[]>(initialPlanSteps);

    return (
      <div className="space-y-2 text-sm">
        <PlanView
          task={content.task || "Untitled Task"}
          plan={planSteps}
          setPlan={setPlanSteps}
          viewOnly={!isEditable}
          onSavePlan={onSavePlan}
          onRegeneratePlan={onRegeneratePlan}
          forceCollapsed={forceCollapsed}
          fromMemory={content.from_memory || false}
        />
      </div>
    );
  }
);

const RenderStepExecution: React.FC<RenderStepExecutionProps> = memo(
  ({
    content,
    hidden,
    is_step_repeated, // is_step_repeated means the step is being re-tried
    is_step_failed, // is_step_failed means the step is being re-planned
    runStatus,
    onToggleHide,
  }) => {
    const [isExpanded, setIsExpanded] = useState(true);

    useEffect(() => {
      if (hidden && isExpanded) {
        setIsExpanded(false);
      } else if (!hidden && !isExpanded) {
        setIsExpanded(true);
      }
    }, [hidden]);

    const handleToggle = () => {
      const newExpanded = !isExpanded;
      setIsExpanded(newExpanded);
      onToggleHide?.(newExpanded);
    };

    const isUserProxyInstruction = content.agent_name === "user_proxy";

    if (is_step_repeated && !hidden) {
      return (
        <div className="">
          {isUserProxyInstruction && content.instruction && (
            <div className="flex items-start">
              <MarkdownRenderer content={content.instruction} />
            </div>
          )}

          {!isUserProxyInstruction && content.instruction && (
            <MarkdownRenderer
              content={content.progress_summary}
              indented={true}
            />
          )}
        </div>
      );
    }
    if (is_step_repeated && hidden) {
      return null;
    }
    // if hidden add success green thingy

    return (
      <div className="flex flex-col">
        {!isUserProxyInstruction &&
          content.instruction &&
          content.index !== 0 && (
            <div className=" mb-2">
              <MarkdownRenderer
                content={content.progress_summary}
                indented={true}
              />
            </div>
          )}
        <div
          className={`relative border-2 border-transparent hover:border-gray-300 rounded-lg p-2 cursor-pointer overflow-hidden bg-secondary`}
          onClick={handleToggle}
        >
          <div className="flex items-center w-full">
            <button
              className="flex-none flex items-center justify-center w-8 h-8 rounded-full bg-secondary transition-colors"
              onClick={(e) => {
                e.stopPropagation();
                handleToggle();
              }}
              aria-label={
                isExpanded
                  ? "Hide following messages"
                  : "Show following messages"
              }
            >
              {isExpanded ? (
                <ChevronDown size={16} className="text-primary" />
              ) : (
                <ChevronRight size={16} className="text-primary" />
              )}
            </button>
            <div className="flex-1 mx-2">
              <div className="font-semibold text-primary">
                Step {content.index + 1}: {content.title}
              </div>
            </div>
            <div className="flex-none">
              {getStepIcon(
                hidden ? "completed" : "current",
                runStatus,
                is_step_repeated,
                is_step_failed
              )}
            </div>
          </div>
        </div>
        <div>
          {isUserProxyInstruction && content.instruction && isExpanded && (
            <div className="flex items-start">
              <MarkdownRenderer content={content.instruction} />
            </div>
          )}
        </div>
      </div>
    );
  }
);

interface RenderFinalAnswerProps {
  content: string;
  sessionId: number;
  messageIdx: number;
}

const RenderFinalAnswer: React.FC<RenderFinalAnswerProps> = memo(
  ({ content, sessionId, messageIdx }) => {
    return (
      <div className="border-2 border-secondary rounded-lg p-4">
        <div className="flex justify-between items-center">
          <div className="font-semibold text-primary">Final Answer</div>
          <LearnPlanButton
            sessionId={sessionId}
            messageId={messageIdx}
            onSuccess={(planId: string) => {
            }}
          />
        </div>
        <div className="break-words">
          <MarkdownRenderer content={content} />
        </div>
      </div>
    );
  }
);

RenderFinalAnswer.displayName = "RenderFinalAnswer";

// Message type checking utilities
export const messageUtils = {
  isToolCallContent(content: unknown): content is FunctionCall[] {
    if (!Array.isArray(content)) return false;
    return content.every(
      (item) =>
        typeof item === "object" &&
        item !== null &&
        "id" in item &&
        "arguments" in item &&
        "name" in item
    );
  },

  isMultiModalContent(content: unknown): content is (string | ImageContent)[] {
    if (!Array.isArray(content)) return false;
    return content.every(
      (item) =>
        typeof item === "string" ||
        (typeof item === "object" &&
          item !== null &&
          ("url" in item || "data" in item))
    );
  },

  isFunctionExecutionResult(
    content: unknown
  ): content is FunctionExecutionResult[] {
    if (!Array.isArray(content)) return false;
    return content.every(
      (item) =>
        typeof item === "object" &&
        item !== null &&
        "call_id" in item &&
        "content" in item
    );
  },

  isFinalAnswer(metadata?: Record<string, any>): boolean {
    return metadata?.type === "final_answer";
  },

  isPlanMessage(metadata?: Record<string, any>): boolean {
    return metadata?.type === "plan_message";
  },

  isStepExecution(metadata?: Record<string, any>): boolean {
    return metadata?.type === "step_execution";
  },

  findUserPlan(content: unknown): IPlanStep[] {
    if (typeof content !== "string") return [];
    try {
      const parsedContent = JSON.parse(content);
      let plan = [];
      if (parsedContent.plan && typeof parsedContent.plan === "string") {
        plan = JSON.parse(parsedContent.plan);
      }
      return plan;
    } catch {
      return [];
    }
  },

  updatePlan(content: unknown, planSteps: IPlanStep[]): string {
    if (typeof content !== "string") return "";

    try {
      const parsedContent = JSON.parse(content);

      if (typeof parsedContent === "object" && parsedContent !== null) {
        parsedContent.steps = planSteps;
        return JSON.stringify(parsedContent);
      }

      return "";
    } catch (error) {
      return "";
    }
  },

  isUser(source: string): boolean {
    return source === "user" || source === "user_proxy";
  },
};

const RenderUserMessage: React.FC<{
  parsedContent: ParsedContent;
  isUserProxy: boolean;
}> = memo(({ parsedContent, isUserProxy }) => {
  // Parse attached files from metadata if present
  const attachedFiles: AttachedFile[] = React.useMemo(() => {
    if (parsedContent.metadata?.attached_files) {
      try {
        return JSON.parse(parsedContent.metadata.attached_files);
      } catch (e) {
        return [];
      }
    }
    return [];
  }, [parsedContent.metadata?.attached_files]);

  return (
    <div className="space-y-2">
      {/* Show attached file icons if present */}
      {attachedFiles.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {attachedFiles.map((file, index) => (
            <div
              key={index}
              className="flex items-center gap-1  rounded px-2 py-1 text-xs"
              title={file.name}
            >
              {file.type.startsWith("image") ? (
                <ImageIcon className="w-3 h-3" />
              ) : (
                <FileTextIcon className="w-3 h-3" />
              )}
              <span className="truncate max-w-[150px]">{file.name}</span>
            </div>
          ))}
        </div>
      )}

      {/* Existing content rendering */}
      {messageUtils.isMultiModalContent(parsedContent.text) ? (
        <div className="space-y-2">
          {parsedContent.text.map((item, index) => (
            <div key={index}>
              {typeof item === "string" ? (
                <div className="break-words whitespace-pre-wrap overflow-wrap-anywhere">
                  {parseContent(item)}
                </div>
              ) : (
                <></>
              )}
            </div>
          ))}
        </div>
      ) : (
        <div className="break-words whitespace-pre-wrap overflow-wrap-anywhere">
          {String(parsedContent.text)}
        </div>
      )}

      {parsedContent.plan &&
        Array.isArray(parsedContent.plan) &&
        parsedContent.plan.length > 0 && (
          <PlanView
            task={""}
            plan={parsedContent.plan}
            setPlan={() => {}} // No-op since it's read-only
            viewOnly={true}
            onSavePlan={() => {}} // No-op since it's read-only
          />
        )}
    </div>
  );
});

RenderUserMessage.displayName = "RenderUserMessage";

// Main component
export const RenderMessage: React.FC<MessageProps> = memo(
  ({
    message,
    sessionId,
    messageIdx,
    runStatus,
    isLast = false,
    className = "",
    isEditable = false,
    hidden = false,
    is_step_repeated = false,
    is_step_failed = false,
    onSavePlan,
    onImageClick,
    onToggleHide,
    onRegeneratePlan,
    forceCollapsed = false,
  }) => {
    if (!message) return null;
    if (message.metadata?.type === "browser_address") return null;

    const isUser = messageUtils.isUser(message.source);
    const isUserProxy = message.source === "user_proxy";
    const isOrchestrator = ["Orchestrator"].includes(message.source);

    const parsedContent =
      isUser || isUserProxy
        ? parseUserContent(message)
        : { text: message.content, metadata: message.metadata };


    // Use new plan message check
    const isPlanMsg = messageUtils.isPlanMessage(message.metadata);

    const orchestratorContent =
      isOrchestrator && typeof message.content === "string"
        ? parseorchestratorContent(message.content, message.metadata)
        : null;

    // Hide regeneration request messages
    if (
      parsedContent.text ===
      "Regenerate a plan that improves on the current plan"
    ) {
      return null;
    }

    return (
      <div
        className={`relative group mb-3 ${className} w-full break-words ${
          hidden &&
          (!orchestratorContent ||
            orchestratorContent.type !== "step-execution")
            ? "hidden"
            : ""
        }`}
      >
        <div
          className={`flex ${
            isUser || isUserProxy ? "justify-end" : "justify-start"
          } items-start w-full transition-all duration-200`}
        >
          <div
            className={`${
              isUser || isUserProxy
                ? `text-primary rounded-2xl bg-tertiary rounded-tr-sm px-4 py-2 ${
                    parsedContent.plan && parsedContent.plan.length > 0
                      ? "w-[80%]"
                      : "max-w-[80%]"
                  }`
                : "w-full text-primary"
            } break-words overflow-hidden`}
          >
            {/* Show user message content first */}
            {(isUser || isUserProxy) && (
              <RenderUserMessage
                parsedContent={parsedContent}
                isUserProxy={isUserProxy}
              />
            )}
            {/* Handle other content types */}
            {!isUser &&
              !isUserProxy &&
              (isPlanMsg ? (
                <RenderPlan
                  content={orchestratorContent?.content || {}}
                  isEditable={isEditable}
                  onSavePlan={onSavePlan}
                  onRegeneratePlan={onRegeneratePlan}
                  forceCollapsed={forceCollapsed}
                />
              ) : orchestratorContent?.type === "step-execution" ? (
                <RenderStepExecution
                  content={orchestratorContent.content}
                  hidden={hidden}
                  is_step_repeated={is_step_repeated}
                  is_step_failed={is_step_failed}
                  runStatus={runStatus || ""}
                  onToggleHide={onToggleHide}
                />
              ) : orchestratorContent?.type === "final-answer" ? (
                <RenderFinalAnswer
                  content={orchestratorContent.content}
                  sessionId={sessionId}
                  messageIdx={messageIdx}
                />
              ) : messageUtils.isToolCallContent(parsedContent.text) ? (
                <RenderToolCall content={parsedContent.text} />
              ) : messageUtils.isMultiModalContent(parsedContent.text) ? (
                message.metadata?.type === "browser_screenshot" ? (
                  <RenderMultiModalBrowserStep
                    content={parsedContent.text}
                    onImageClick={onImageClick}
                  />
                ) : (
                  <RenderMultiModal content={parsedContent.text} />
                )
              ) : messageUtils.isFunctionExecutionResult(parsedContent.text) ? (
                <RenderToolResult content={parsedContent.text} />
              ) : (
                <div className="break-words">
                  {message.metadata?.type === "file" ? (
                    <RenderFile message={message} />
                  ) : (
                    <MarkdownRenderer
                      content={String(parsedContent.text)}
                      indented={
                        !orchestratorContent ||
                        orchestratorContent.type !== "default"
                      }
                    />
                  )}
                </div>
              ))}
          </div>
        </div>
      </div>
    );
  }
);

RenderMessage.displayName = "RenderMessage";
