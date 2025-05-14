import * as React from "react";
import { message } from "antd";
import { convertFilesToBase64, getServerUrl } from "../../utils";
import { IStatus } from "../../types/app";
import {
  Run,
  Message,
  WebSocketMessage,
  InputRequestMessage,
  TeamConfig,
  AgentMessageConfig,
  RunStatus as BaseRunStatus,
  TeamResult,
  Session,
  InputRequest,
} from "../../types/datamodel";
import { appContext } from "../../../hooks/provider";
import ChatInput from "./chatinput";
import { sessionAPI, settingsAPI } from "../api";
import RunView from "./runview";
import { messageUtils } from "./rendermessage";
import { useSettingsStore, GeneralConfig } from "../../store";
import { RcFile } from "antd/es/upload";
import {
  IPlan,
  IPlanStep,
  convertPlanStepsToJsonString,
} from "../../types/plan";
import SampleTasks from "./sampletasks";
import ProgressBar from "./progressbar";

// Extend RunStatus for sidebar status reporting
type SidebarRunStatus = BaseRunStatus | "final_answer_awaiting_input";

const defaultTeamConfig: TeamConfig = {
  name: "Default Team",
  participants: [],
  team_type: "RoundRobinGroupChat",
  component_type: "team",
};

interface ChatViewProps {
  session: Session | null;
  onSessionNameChange: (sessionData: Partial<Session>) => void;
  getSessionSocket: (
    sessionId: number,
    runId: string,
    fresh_socket: boolean,
    only_retrieve_existing_socket: boolean
  ) => WebSocket | null;
  visible?: boolean;
  onRunStatusChange: (sessionId: number, status: BaseRunStatus) => void;
}

type PlanUpdateHandler = (plan: IPlanStep[]) => void;

interface StepProgress {
  currentStep: number;
  totalSteps: number;
  plan?: {
    task: string;
    steps: Array<{
      title: string;
      details: string;
      agent_name?: string;
    }>;
    response?: string;
    plan_summary?: string;
  };
}

export default function ChatView({
  session,
  onSessionNameChange,
  getSessionSocket,
  visible = true,
  onRunStatusChange,
}: ChatViewProps) {
  const serverUrl = getServerUrl();
  const [error, setError] = React.useState<IStatus | null>({
    status: true,
    message: "All good",
  });
  const [updatedPlan, setUpdatedPlan] = React.useState<IPlanStep[]>([]);
  const [localPlan, setLocalPlan] = React.useState<IPlan | null>(null);
  const [planProcessed, setPlanProcessed] = React.useState(false);
  const processedPlanIds = React.useRef(new Set<string>()).current;

  const settingsConfig = useSettingsStore((state) => state.config);
  const { user } = React.useContext(appContext);

  // Core state
  const [currentRun, setCurrentRun] = React.useState<Run | null>(null);
  const [messageApi, contextHolder] = message.useMessage();
  const [noMessagesYet, setNoMessagesYet] = React.useState(true);
  const chatContainerRef = React.useRef<HTMLDivElement | null>(null);
  const [isDetailViewerMinimized, setIsDetailViewerMinimized] =
    React.useState(true);
  const [showDetailViewer, setShowDetailViewer] = React.useState(true);
  const [hasFinalAnswer, setHasFinalAnswer] = React.useState(false);

  // Context and config
  const [activeSocket, setActiveSocket] = React.useState<WebSocket | null>(
    null
  );
  const [teamConfig, setTeamConfig] = React.useState<TeamConfig | null>(
    defaultTeamConfig
  );

  const inputTimeoutRef = React.useRef<NodeJS.Timeout | null>(null);
  const activeSocketRef = React.useRef<WebSocket | null>(null);

  // Add ref for ChatInput component
  const chatInputRef = React.useRef<any>(null);

  // Add state for progress tracking
  const [progress, setProgress] = React.useState<StepProgress>({
    currentStep: -1,
    totalSteps: -1,
  });
  const [isPlanning, setIsPlanning] = React.useState(false);

  // Replace stepTitles state with currentPlan state
  const [currentPlan, setCurrentPlan] = React.useState<StepProgress["plan"]>();

  // Create a Message object from AgentMessageConfig
  const createMessage = (
    config: AgentMessageConfig,
    runId: string,
    sessionId: number
  ): Message => ({
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    config,
    session_id: sessionId,
    run_id: runId,
    user_id: user?.email || undefined,
  });

  const loadSessionRun = async () => {
    if (!session?.id || !user?.email) return null;

    try {
      const response = await sessionAPI.getSessionRuns(session.id, user?.email);
      const latestRun = response.runs[response.runs.length - 1];
      return latestRun;
    } catch (error) {
      console.error("Error loading session runs:", error);
      messageApi.error("Failed to load chat history");
      return null;
    }
  };

  React.useEffect(() => {
    const initializeSession = async () => {
      if (session?.id) {
        // Reset plan state ONLY when session ID changes
        setLocalPlan(null);
        setPlanProcessed(false);
        processedPlanIds.clear();
        setUpdatedPlan([]);

        // Reset socket
        setActiveSocket(null);
        activeSocketRef.current = null;

        // Only load data if component is visible
        const latestRun = await loadSessionRun();

        if (latestRun) {
          setCurrentRun(latestRun);
          setNoMessagesYet(latestRun.messages.length === 0);

          if (latestRun.id) {
            setupWebSocket(latestRun.id, false, true);
          }
        } else {
          setError({
            status: false,
            message: "No run found",
          });
        }
      } else {
        setCurrentRun(null);
      }
    };

    initializeSession();
  }, [session?.id, visible]);

  // Keep the planReady event handler in a separate effect
  React.useEffect(() => {
    if (session?.id) {
      const handlePlanReady = (event: CustomEvent) => {
        // Check if this event belongs to current session
        if (event.detail.sessionId !== session.id) {
          return;
        }

        // Add a unique ID for deduplication if not present
        const planId = event.detail.messageId || `plan_${Date.now()}`;

        // Only set if we haven't processed this plan already
        if (!processedPlanIds.has(planId)) {
          const planData = {
            ...event.detail.planData,
            sessionId: session.id,
            messageId: planId,
          };

          setLocalPlan(planData);
          setPlanProcessed(false);
        }
      };

      window.addEventListener("planReady", handlePlanReady as EventListener);

      return () => {
        window.removeEventListener(
          "planReady",
          handlePlanReady as EventListener
        );
      };
    }
  }, [session?.id]);

  // Add ref to track previous status
  const previousStatus = React.useRef<SidebarRunStatus | null>(null);

  // Add effect to update run status when currentRun changes
  React.useEffect(() => {
    if (currentRun && session?.id) {
      // Only call onRunStatusChange if the status has actually changed
      let statusToReport: SidebarRunStatus = currentRun.status;
      const lastMsg = currentRun.messages?.[currentRun.messages.length - 1];
      const beforeLastMsg =
        currentRun.messages?.[currentRun.messages.length - 2];
      if (
        lastMsg &&
        ((typeof lastMsg.config?.content === "string" &&
          messageUtils.isFinalAnswer(lastMsg.config?.metadata)) ||
          (beforeLastMsg &&
            typeof beforeLastMsg.config?.content === "string" &&
            messageUtils.isFinalAnswer(beforeLastMsg.config?.metadata))) &&
        currentRun.status == "awaiting_input"
      ) {
        statusToReport = "final_answer_awaiting_input";
      }
      if (statusToReport !== previousStatus.current) {
        onRunStatusChange(session.id, statusToReport as BaseRunStatus);
        previousStatus.current = statusToReport; // Update the previous status
        // Clear error state when status changes
        setError(null);
      }
    }
  }, [
    currentRun?.status,
    currentRun?.messages,
    session?.id,
    onRunStatusChange,
  ]);

  // Scroll to bottom when a new message appears or message is updated
  React.useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTo({
        top: chatContainerRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [currentRun?.messages]);

  // Add effect to focus input when session changes
  React.useEffect(() => {
    if (chatInputRef.current) {
      chatInputRef.current.focus();
    }
  }, [session?.id]); // Focus when session changes

  // Add this effect to handle WebSocket messages even when not visible
  React.useEffect(() => {
    if (session?.id && !visible && activeSocket) {
      // Keep the socket connection alive but still process status updates
      const messageHandler = (event: MessageEvent) => {
        try {
          const message = JSON.parse(event.data) as WebSocketMessage;
          if (message.type === "system" && message.status && session.id) {
            // Update the run status even when not visible
            onRunStatusChange(session.id, message.status as BaseRunStatus);
          }
        } catch (error) {
          console.error("WebSocket message parsing error:", error);
        }
      };

      activeSocket.addEventListener("message", messageHandler);

      return () => {
        activeSocket.removeEventListener("message", messageHandler);
      };
    }
  }, [session?.id, visible, activeSocket, onRunStatusChange]);

  const handleWebSocketMessage = (message: WebSocketMessage) => {
    setCurrentRun((current: Run | null) => {
      if (!current || !session?.id) return null;


      switch (message.type) {
        case "error":
          if (inputTimeoutRef.current) {
            clearTimeout(inputTimeoutRef.current);
            inputTimeoutRef.current = null;
          }
          if (activeSocket) {
            activeSocket.close();
            setActiveSocket(null);
            activeSocketRef.current = null;
          }
          console.log("Error: ", message.error);

        case "message":
          if (!message.data) return current;

          // Create new Message object from websocket data
          const newMessage = createMessage(
            message.data as AgentMessageConfig,
            current.id,
            session.id
          );

          return {
            ...current,
            messages: [...current.messages, newMessage],
          };

        case "input_request":
          //console.log("InputRequest: " + JSON.stringify(message))

          var input_request: InputRequest;
          switch (message.input_type) {
            case "text_input":
            case null:
            default:
              input_request = { input_type: "text_input" };
              break;
            case "approval":
              var input_request_message = message as InputRequestMessage;
              input_request = {
                input_type: "approval",
                prompt: input_request_message.prompt,
              } as InputRequest;
              break;
          }

          // reset Updated Plan
          setUpdatedPlan([]);
          // Create new Message object from websocket data only if its for URL approval
          if (input_request.input_type === "approval") {
            return {
              ...current,
              status: "awaiting_input",
              input_request: input_request,
            };
          }
          return {
            ...current,
            status: "awaiting_input",
            input_request: input_request,
          };
        case "system":
          // update run status
          return {
            ...current,
            status: message.status as BaseRunStatus,
          };

        case "result":
        case "completion":
          const status: BaseRunStatus =
            message.status === "complete"
              ? "complete"
              : message.status === "error"
              ? "error"
              : "stopped";

          const isTeamResult = (data: any): data is TeamResult => {
            return (
              data &&
              "task_result" in data &&
              "usage" in data &&
              "duration" in data
            );
          };

          // close socket on completion
          if (activeSocket) {
            activeSocket.close();
            setActiveSocket(null);
            activeSocketRef.current = null;
          }

          return {
            ...current,
            status,
            team_result:
              message.data && isTeamResult(message.data) ? message.data : null,
          };

        default:
          return current;
      }
    });
  };

  const handleError = (error: any) => {
    console.error("Error:", error);
    message.error("Error during request processing");

    setError({
      status: false,
      message:
        error instanceof Error ? error.message : "Unknown error occurred",
    });
  };

  const handleInputResponse = async (
    response: string,
    accepted = false,
    plan?: IPlan
  ) => {
    if (!currentRun || !activeSocketRef.current) {
      handleError(new Error("WebSocket connection not available"));
      return;
    }

    if (activeSocketRef.current.readyState !== WebSocket.OPEN) {
      handleError(new Error("WebSocket connection not available"));
      return;
    }

    try {
      // Check if the last message is a plan
      const lastMessage = currentRun.messages.slice(-1)[0];
      var planString = "";
      if (plan) {
        planString = convertPlanStepsToJsonString(plan.steps);
      } else if (
        lastMessage &&
        messageUtils.isPlanMessage(lastMessage.config.metadata)
      ) {
        planString = convertPlanStepsToJsonString(updatedPlan);
      }

      const responseJson = {
        accepted: accepted,
        content: response,
        ...(planString !== "" && { plan: planString }),
      };
      const responseString = JSON.stringify(responseJson);

      activeSocketRef.current.send(
        JSON.stringify({
          type: "input_response",
          response: responseString,
        })
      );

      setCurrentRun((current: Run | null) => {
        if (!current) return null;
        return {
          ...current,
          status: "active",
          input_request: undefined, // Changed null to undefined
        };
      });
    } catch (error) {
      handleError(error);
    }
  };

  const handleRegeneratePlan = async () => {
    if (!currentRun || !activeSocketRef.current) {
      handleError(new Error("WebSocket connection not available"));
      return;
    }

    if (activeSocketRef.current.readyState !== WebSocket.OPEN) {
      handleError(new Error("WebSocket connection not available"));
      return;
    }

    try {
      // Check if the last message is a plan
      const lastMessage = currentRun.messages.slice(-1)[0];
      var planString = "";
      if (
        lastMessage &&
        messageUtils.isPlanMessage(lastMessage.config.metadata)
      ) {
        planString = convertPlanStepsToJsonString(updatedPlan);
      }

      const responseJson = {
        content: "Regenerate a plan that improves on the current plan",
        ...(planString !== "" && { plan: planString }),
      };
      const responseString = JSON.stringify(responseJson);

      activeSocketRef.current.send(
        JSON.stringify({
          type: "input_response",
          response: responseString,
        })
      );
    } catch (error) {
      handleError(error);
    }
  };

  const handleCancel = async () => {
    if (!activeSocketRef.current || !currentRun) return;

    // Clear timeout when manually cancelled
    if (inputTimeoutRef.current) {
      clearTimeout(inputTimeoutRef.current);
      inputTimeoutRef.current = null;
    }
    try {
      activeSocketRef.current.send(
        JSON.stringify({
          type: "stop",
          reason: "Cancelled by user",
        })
      );

      setCurrentRun((current: Run | null) => {
        if (!current) return null;
        const updatedRun = {
          ...current,
          status: "stopped" as BaseRunStatus, // Cast "stopped" to BaseRunStatus
          input_request: undefined, // Changed null to undefined
        };
        return updatedRun;
      });
    } catch (error) {
      handleError(error);
    }
  };

  const handlePause = async () => {
    if (!activeSocketRef.current || !currentRun) return;

    try {
      if (activeSocketRef.current.readyState !== WebSocket.OPEN) {
        throw new Error("WebSocket connection not available");
      }

      if (
        currentRun.status == "awaiting_input" ||
        currentRun.status == "connected"
      ) {
        return; // Do not pause if awaiting input or connected
      }

      activeSocketRef.current.send(
        JSON.stringify({
          type: "pause",
        })
      );

      setCurrentRun((current: Run | null) => {
        if (!current) return null;
        return {
          ...current,
          status: "pausing",
        };
      });
    } catch (error) {
      handleError(error);
    }
  };

  const runTask = async (
    query: string,
    files: RcFile[] = [],
    plan?: IPlan,
    fresh_socket: boolean = false
  ) => {
    setError(null);
    setNoMessagesYet(false);

    console.log("Running task:", query, files);

    try {
      // Make sure run is setup first
      let run = currentRun;
      if (!run) {
        run = await loadSessionRun();
        if (run) {
          setCurrentRun(run);
        } else {
          throw new Error("Could not setup run");
        }
      }

      // Load latest settings from database
      let currentSettings = settingsConfig;
      if (user?.email) {
        try {
          currentSettings = (await settingsAPI.getSettings(
            user.email
          )) as GeneralConfig;
          useSettingsStore.getState().updateConfig(currentSettings);
        } catch (error) {
          console.error("Failed to load settings:", error);
        }
      }

      // Setup websocket connection
      const socket = setupWebSocket(run.id, fresh_socket, false);
      if (!socket) {
        throw new Error("WebSocket connection not available");
      }

      // Wait for socket to be ready
      await new Promise<void>((resolve, reject) => {
        const checkState = () => {
          if (socket.readyState === WebSocket.OPEN) {
            resolve();
          } else if (
            socket.readyState === WebSocket.CLOSED ||
            socket.readyState === WebSocket.CLOSING
          ) {
            reject(new Error("Socket failed to connect"));
          } else {
            setTimeout(checkState, 100);
          }
        };
        checkState();
      });
      console.log("Socket connected");
      const processedFiles = await convertFilesToBase64(files);
      // Send start message

      var planString = plan ? convertPlanStepsToJsonString(plan.steps) : "";

      const taskJson = {
        content: query,
        ...(planString !== "" && { plan: planString }),
      };

      socket.send(
        JSON.stringify({
          type: "start",
          task: JSON.stringify(taskJson),
          files: processedFiles,
          team_config: teamConfig,
          settings_config: currentSettings,
        })
      );
      const sessionData = {
        id: session?.id,
        name: query.slice(0, 50),
      };
      onSessionNameChange(sessionData);
    } catch (error) {
      setError({
        status: false,
        message:
          error instanceof Error ? error.message : "Failed to start task",
      });
    }
  };

  const setupWebSocket = (
    runId: string,
    fresh_socket: boolean = false,
    only_retrieve_existing_socket: boolean = false
  ): WebSocket | null => {
    if (!session?.id) {
      throw new Error("Invalid session configuration");
    }

    const socket = getSessionSocket(
      session.id,
      runId,
      fresh_socket,
      only_retrieve_existing_socket
    );
    if (!socket) {
      return null;
    }

    socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        handleWebSocketMessage(message);
      } catch (error) {
        console.error("WebSocket message parsing error:", error);
      }
    };

    socket.onclose = () => {
      activeSocketRef.current = null;
      setActiveSocket(null);
    };

    socket.onerror = (error) => {
      handleError(error);
    };

    setActiveSocket(socket);
    // set up socket ref
    activeSocketRef.current = socket;
    console.log("Socket setup complete");
    return socket;
  };

  const lastMessage = currentRun?.messages.slice(-1)[0];
  const isPlanMessage =
    lastMessage && messageUtils.isPlanMessage(lastMessage.config.metadata);

  // Update the handler to be more specific about its purpose
  const handlePlanUpdate: PlanUpdateHandler = (plan: IPlanStep[]) => {
    setUpdatedPlan(plan);
  };

  React.useEffect(() => {
    if (localPlan && !planProcessed && visible && session?.id && currentRun) {
      // Only process if the plan belongs to current session
      if (localPlan.sessionId === session.id) {
        processPlan(localPlan);
      } else {
        setLocalPlan(null);
      }
    }
  }, [localPlan, planProcessed, visible, session?.id, currentRun]);

  const processPlan = async (newPlan: IPlan) => {
    if (!currentRun || !session?.id) return;

    // Verify the plan belongs to current session
    if (newPlan.sessionId !== session.id) {
      return;
    }

    try {
      // Always get a fresh socket connection
      const socket =
        activeSocketRef.current?.readyState === WebSocket.OPEN
          ? activeSocketRef.current
          : setupWebSocket(currentRun.id, true, false);

      if (!socket || socket.readyState !== WebSocket.OPEN) {
        console.error("WebSocket not available or not open");
        return;
      }

      // Create a copy of the settings config instead of modifying directly
      const sessionSettingsConfig = {
        ...settingsConfig,
        plan: {
          task: newPlan.task,
          steps: newPlan.steps,
          plan_summary: "Saved plan for task: " + newPlan.task,
        },
      };

      // Use the current session's team config
      const currentTeamConfig = teamConfig || defaultTeamConfig;

      const message = {
        type: "start",
        id: `plan_${Date.now()}`,
        task: newPlan.task,
        team_config: currentTeamConfig,
        settings_config: sessionSettingsConfig,
        sessionId: session.id,
      };

      socket.send(JSON.stringify(message));

      // Mark as no longer first message
      setNoMessagesYet(false);

      // Mark plan as processed
      setPlanProcessed(true);
      if (newPlan.messageId) {
        processedPlanIds.add(newPlan.messageId);
      }
    } catch (err) {
      console.error("Error processing plan for session:", session.id, err);
    }
  };

  const handleExecutePlan = React.useCallback(
    (plan: IPlan) => {
      plan.sessionId = session?.id || undefined; // Ensure session ID is set
      processPlan(plan);
    },
    [processPlan]
  );

  // Update effect to extract full plan
  React.useEffect(() => {
    if (!currentRun?.messages) return;

    // Find the last plan message
    const lastPlanMessage = [...currentRun.messages].reverse().find((msg) => {
      if (typeof msg.config.content !== "string") return false;
      return messageUtils.isPlanMessage(msg.config.metadata);
    });

    if (lastPlanMessage && typeof lastPlanMessage.config.content === "string") {
      try {
        const content = JSON.parse(lastPlanMessage.config.content);
        if (messageUtils.isPlanMessage(lastPlanMessage.config.metadata)) {
          setCurrentPlan({
            task: content.task,
            steps: content.steps,
            response: content.response,
            plan_summary: content.plan_summary,
          });
        }
      } catch {
        setCurrentPlan(undefined);
      }
    }
  }, [currentRun?.messages]);

  // Add effect to detect plan and final answer messages
  React.useEffect(() => {
    if (!currentRun?.messages.length) return;

    let currentStepIndex = -1;
    let planLength = 0;

    // Find the last final answer index
    const lastFinalAnswerIndex = currentRun.messages.findLastIndex(
      (msg: Message) =>
        typeof msg.config.content === "string" &&
        messageUtils.isFinalAnswer(msg.config.metadata)
    );

    // Calculate step progress only for messages after the last final answer
    const relevantMessages =
      lastFinalAnswerIndex === -1
        ? currentRun.messages
        : currentRun.messages.slice(lastFinalAnswerIndex + 1);

    relevantMessages.forEach((msg: Message) => {
      if (typeof msg.config.content === "string") {
        try {
          const content = JSON.parse(msg.config.content);
          if (content.index !== undefined) {
            currentStepIndex = content.index;
            if (content.plan_length) {
              planLength = content.plan_length;
            }
          }
        } catch {
          // Skip if we can't parse the message
        }
      }
    });

    setProgress({
      currentStep: currentStepIndex,
      totalSteps: planLength,
      plan: currentPlan,
    });

    // Check if we have a final answer
    const hasFinalAnswer = lastFinalAnswerIndex !== -1;

    // If we have a final answer, check for plans after it
    if (hasFinalAnswer) {
      // Look for plans after the final answer
      const messagesAfterFinalAnswer = currentRun.messages.slice(
        lastFinalAnswerIndex + 1
      );
      const hasPlanAfterFinalAnswer = messagesAfterFinalAnswer.some(
        (msg) =>
          typeof msg.config.content === "string" &&
          messageUtils.isPlanMessage(msg.config.metadata)
      );

      if (hasPlanAfterFinalAnswer) {
        // Reset to planning state if there's a plan after final answer
        setIsPlanning(progress.currentStep === -1);
        setHasFinalAnswer(false);
      } else {
        // Mark as completed if there's no plan after final answer
        setIsPlanning(false);
        setHasFinalAnswer(true);
      }
    } else {
      // No final answer - check for recent plans as before
      const recentMessages = currentRun.messages.slice(-3);
      const hasPlan = recentMessages.some(
        (msg: Message) =>
          typeof msg.config.content === "string" &&
          messageUtils.isPlanMessage(msg.config.metadata)
      );

      setHasFinalAnswer(false);
      // Only set planning to true if we have a plan but haven't started executing it yet
      setIsPlanning(hasPlan && progress.currentStep === -1);
    }

    // Hide progress if run is not in an active state
    if (
      currentRun.status !== "active" &&
      currentRun.status !== "awaiting_input" &&
      currentRun.status !== "paused" &&
      currentRun.status !== "pausing"
    ) {
      setIsPlanning(false);
      setProgress({ currentStep: -1, totalSteps: -1 }); // Reset progress
    }
  }, [
    currentRun?.messages,
    currentRun?.status,
    progress.currentStep,
    currentPlan,
  ]);

  // Add these handlers before the return statement
  const handleApprove = () => {
    if (currentRun?.status === "awaiting_input") {
      handleInputResponse("approve", true);
    }
  };

  const handleDeny = () => {
    if (currentRun?.status === "awaiting_input") {
      handleInputResponse("deny", false);
    }
  };

  const handleAcceptPlan = (text: string) => {
    if (currentRun?.status === "awaiting_input") {
      const query = text || "Plan Accepted";
      handleInputResponse(query, true);
    }
  };

  if (!visible) {
    return null;
  }

  return (
    <div className="text-primary h-[calc(100vh-100px)] bg-primary relative rounded flex-1 scroll w-full">
      {contextHolder}
      <div className="flex flex-col h-full w-full">
        {/* Progress Bar - Sticky at top */}
        <div className="progress-container" style={{ height: "3.5rem" }}>
          <div
            className="transition-opacity duration-300"
            style={{
              opacity:
                currentRun?.status === "active" ||
                currentRun?.status === "awaiting_input" ||
                currentRun?.status === "paused" ||
                currentRun?.status === "pausing"
                  ? 1
                  : 0,
            }}
          >
            <ProgressBar
              isPlanning={isPlanning}
              progress={progress}
              hasFinalAnswer={hasFinalAnswer}
            />
          </div>
        </div>

        <div
          ref={chatContainerRef}
          className={`flex-1 overflow-y-auto scroll mt-1 min-h-0 relative w-full h-full ${
            noMessagesYet && currentRun
              ? "flex items-center justify-center"
              : ""
          }`}
        >
          <div
            className={`${
              showDetailViewer && !isDetailViewerMinimized
                ? "w-full"
                : "max-w-full md:max-w-5xl lg:max-w-6xl xl:max-w-7xl"
            } mx-auto px-4 sm:px-6 md:px-8 h-full ${
              noMessagesYet && currentRun ? "hidden" : ""
            }`}
          >
            {
              <>
                {/* Current Run */}
                {currentRun && (
                  <RunView
                    run={currentRun}
                    onSavePlan={handlePlanUpdate}
                    onPause={handlePause}
                    onRegeneratePlan={handleRegeneratePlan}
                    isDetailViewerMinimized={isDetailViewerMinimized}
                    setIsDetailViewerMinimized={setIsDetailViewerMinimized}
                    showDetailViewer={showDetailViewer}
                    setShowDetailViewer={setShowDetailViewer}
                    onApprove={handleApprove}
                    onDeny={handleDeny}
                    onAcceptPlan={handleAcceptPlan}
                    // Add these to connect the functions from chat.tsx to RunView
                    onInputResponse={handleInputResponse}
                    onRunTask={runTask}
                    onCancel={handleCancel}
                    error={error}
                    chatInputRef={chatInputRef}
                    onExecutePlan={handleExecutePlan}
                    enable_upload={false} // Or true if needed
                  />
                )}
              </>
            }
          </div>

          {/* No existing messages in run - centered content */}
          {currentRun && noMessagesYet && teamConfig && (
            <div
              className={`text-center ${
                showDetailViewer && !isDetailViewerMinimized
                  ? "w-full"
                  : "w-full max-w-full md:max-w-4xl lg:max-w-5xl xl:max-w-6xl"
              } mx-auto px-4 sm:px-6 md:px-8`}
            >
              <div className="text-secondary text-lg mb-6">
                Enter a message to get started
              </div>

              <div className="w-full">
                <ChatInput
                  ref={chatInputRef}
                  onSubmit={(
                    query: string,
                    files: RcFile[],
                    accepted = false,
                    plan?: IPlan
                  ) => {
                    if (
                      currentRun?.status === "awaiting_input" ||
                      currentRun?.status === "paused"
                    ) {
                      handleInputResponse(query, accepted, plan);
                    } else {
                      runTask(query, files, plan, true);
                    }
                  }}
                  error={error}
                  onCancel={handleCancel}
                  runStatus={currentRun?.status}
                  inputRequest={currentRun?.input_request}
                  isPlanMessage={isPlanMessage}
                  onPause={handlePause}
                  enable_upload={true}
                  onExecutePlan={handleExecutePlan}
                />
              </div>
              <SampleTasks
                onSelect={(task: string) => {
                  if (chatInputRef.current) {
                    // Set the input value and trigger submit
                    chatInputRef.current.focus();
                    // Set value in textarea
                    const textarea = document.getElementById(
                      "queryInput"
                    ) as HTMLTextAreaElement;
                    if (textarea) {
                      textarea.value = task;
                      // Trigger input event for React state
                      const event = new Event("input", { bubbles: true });
                      textarea.dispatchEvent(event);
                    }
                    // Submit the task
                    setTimeout(() => {
                      if (chatInputRef.current) {
                        chatInputRef.current.focus();
                        // Simulate pressing Enter
                        const enterEvent = new KeyboardEvent("keydown", {
                          key: "Enter",
                          bubbles: true,
                        });
                        textarea?.dispatchEvent(enterEvent);
                      }
                    }, 100);
                  }
                }}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
