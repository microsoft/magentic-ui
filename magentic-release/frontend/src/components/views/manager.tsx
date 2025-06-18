import React, {
  useCallback,
  useEffect,
  useState,
  useContext,
  useMemo,
} from "react";
import { message, Spin } from "antd";
import { useConfigStore } from "../../hooks/store";
import { appContext } from "../../hooks/provider";
import { sessionAPI } from "./api";
import { SessionEditor } from "./session_editor";
import type { Session } from "../types/datamodel";
import ChatView from "./chat/chat";
import { Sidebar } from "./sidebar";
import { getServerUrl } from "../utils";
import { RunStatus } from "../types/datamodel";
import ContentHeader from "../contentheader";
import PlanList from "../features/Plans/PlanList";

interface SessionWebSocket {
  socket: WebSocket;
  runId: string;
}

type SessionWebSockets = {
  [sessionId: number]: SessionWebSocket;
};

export const SessionManager: React.FC = () => {
  const [isLoading, setIsLoading] = useState(false);
  const [isEditorOpen, setIsEditorOpen] = useState(false);
  const [editingSession, setEditingSession] = useState<Session | undefined>();
  const [isSidebarOpen, setIsSidebarOpen] = useState(() => {
    if (typeof window !== "undefined") {
      const stored = localStorage.getItem("sessionSidebar");
      return stored !== null ? JSON.parse(stored) : true;
    }
    return true;
  });
  const [messageApi, contextHolder] = message.useMessage();
  const [sessionSockets, setSessionSockets] = useState<SessionWebSockets>({});
  const [sessionRunStatuses, setSessionRunStatuses] = useState<{
    [sessionId: number]: RunStatus;
  }>({});
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [activeSubMenuItem, setActiveSubMenuItem] = useState("current_session");

  const { user } = useContext(appContext);
  const { session, setSession, sessions, setSessions } = useConfigStore();

  useEffect(() => {
    if (typeof window !== "undefined") {
      localStorage.setItem("sessionSidebar", JSON.stringify(isSidebarOpen));
    }
  }, [isSidebarOpen]);

  const fetchSessions = useCallback(async () => {
    if (!user?.email) return;

    try {
      setIsLoading(true);
      const data = await sessionAPI.listSessions(user.email);
      setSessions(data);

      // Only set first session if there's no sessionId in URL
      const params = new URLSearchParams(window.location.search);
      const sessionId = params.get("sessionId");
      if (!session && data.length > 0 && !sessionId) {
        setSession(data[0]);
      } else {
        if (data.length === 0) {
          console.log("No sessions found, creating default session...");
          createDefaultSession();
        }
      }
    } catch (error) {
      console.error("Error fetching sessions:", error);
      messageApi.error("Error loading sessions");
    } finally {
      setIsLoading(false);
    }
  }, [user?.email, setSessions, session, setSession]);

  // Handle initial URL params
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const sessionId = params.get("sessionId");

    if (sessionId && !session) {
      handleSelectSession({ id: parseInt(sessionId) } as Session);
    }
  }, []);

  // Handle browser back/forward
  useEffect(() => {
    const handleLocationChange = () => {
      const params = new URLSearchParams(window.location.search);
      const sessionId = params.get("sessionId");

      if (!sessionId && session) {
        setSession(null);
      }
    };

    window.addEventListener("popstate", handleLocationChange);
    return () => window.removeEventListener("popstate", handleLocationChange);
  }, [session]);

  const handleSaveSession = async (sessionData: Partial<Session>) => {
    if (!user || !user.email) return;

    try {
      setIsLoading(true);
      if (sessionData.id) {
        const updated = await sessionAPI.updateSession(
          sessionData.id,
          sessionData,
          user.email
        );
        setSessions(sessions.map((s) => (s.id === updated.id ? updated : s)));
        if (session?.id === updated.id) {
          setSession(updated);
        }
      } else {
        const created = await sessionAPI.createSession(
          {
            ...sessionData,
            name:
              "Default Session - " +
              new Date().toLocaleDateString(undefined, {
                year: "numeric",
                month: "long",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit",
              }),
          },
          user.email
        );
        setSessions([created, ...sessions]);
        setSession(created);
      }
      setIsEditorOpen(false);
      setEditingSession(undefined);
    } catch (error) {
      messageApi.error("Error saving session");
      console.error(error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleEditSession = (session?: Session) => {
    setActiveSubMenuItem("current_session");
    setIsLoading(true);
    if (session) {
      setEditingSession(session);
      setIsEditorOpen(true);
    } else {
      // this means we are creating a new session
      handleSaveSession({});
    }
    setIsLoading(false);
  };

  const handleDeleteSession = async (sessionId: number) => {
    if (!user?.email) return;

    try {
      setIsLoading(true);
      // Close and remove socket if it exists
      if (sessionSockets[sessionId]) {
        sessionSockets[sessionId].socket.close();
        setSessionSockets((prev) => {
          const updated = { ...prev };
          delete updated[sessionId];
          return updated;
        });
      }

      const response = await sessionAPI.deleteSession(sessionId, user.email);
      setSessions(sessions.filter((s) => s.id !== sessionId));
      if (session?.id === sessionId || sessions.length === 0) {
        setSession(sessions[0] || null);
        window.history.pushState({}, "", window.location.pathname); // Clear URL params
      }
      messageApi.success("Session deleted");
    } catch (error) {
      console.error("Error deleting session:", error);
      messageApi.error("Error deleting session");
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectSession = async (selectedSession: Session) => {
    if (!user?.email || !selectedSession.id) return;

    try {
      setActiveSubMenuItem("current_session");
      setIsLoading(true);
      const data = await sessionAPI.getSession(selectedSession.id, user.email);
      if (!data) {
        // Session not found
        messageApi.error("Session not found");
        window.history.pushState({}, "", window.location.pathname); // Clear URL
        if (sessions.length > 0) {
          setSession(sessions[0]); // Fall back to first session
        } else {
          setSession(null);
        }
        return;
      }
      setSession(data);
      window.history.pushState({}, "", `?sessionId=${selectedSession.id}`);
    } catch (error) {
      console.error("Error loading session:", error);
      messageApi.error("Error loading session");
      window.history.pushState({}, "", window.location.pathname); // Clear invalid URL
      if (sessions.length > 0) {
        setSession(sessions[0]); // Fall back to first session
      } else {
        setSession(null);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleSessionName = async (sessionData: Partial<Session>) => {
    if (!sessionData.id || !user?.email) return;

    // Check if current session name matches default pattern
    const currentSession = sessions.find((s) => s.id === sessionData.id);
    if (!currentSession) return;

    // Only update if it starts with "Default Session - "
    if (currentSession.name.startsWith("Default Session - ")) {
      try {
        const updated = await sessionAPI.updateSession(
          sessionData.id,
          sessionData,
          user.email
        );
        setSessions(sessions.map((s) => (s.id === updated.id ? updated : s)));
        if (session?.id === updated.id) {
          setSession(updated);
        }
      } catch (error) {
        console.error("Error updating session name:", error);
        messageApi.error("Error updating session name");
      }
    }
  };

  const getBaseUrl = (url: string): string => {
    try {
      let baseUrl = url.replace(/(^\w+:|^)\/\//, "");
      if (baseUrl.startsWith("localhost")) {
        baseUrl = baseUrl.replace("/api", "");
      } else if (baseUrl === "/api") {
        baseUrl = window.location.host;
      } else {
        baseUrl = baseUrl.replace("/api", "").replace(/\/$/, "");
      }
      return baseUrl;
    } catch (error) {
      console.error("Error processing server URL:", error);
      throw new Error("Invalid server URL configuration");
    }
  };

  const setupWebSocket = (sessionId: number, runId: string): WebSocket => {
    // Close existing socket for this session if it exists
    if (sessionSockets[sessionId]) {
      sessionSockets[sessionId].socket.close();
    }

    const serverUrl = getServerUrl();
    const baseUrl = getBaseUrl(serverUrl);
    const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${wsProtocol}//${baseUrl}/api/ws/runs/${runId}`;

    const socket = new WebSocket(wsUrl);

    // Store the new socket
    setSessionSockets((prev) => ({
      ...prev,
      [sessionId]: { socket, runId },
    }));

    return socket;
  };

  const getSessionSocket = (
    sessionId: number,
    runId: string,
    fresh_socket: boolean = false,
    only_retrieve_existing_socket: boolean = false
  ): WebSocket | null => {
    if (fresh_socket) {
      return setupWebSocket(sessionId, runId);
    } else {
      const existingSocket = sessionSockets[sessionId];

      if (
        existingSocket?.socket.readyState === WebSocket.OPEN &&
        existingSocket.runId === runId
      ) {
        return existingSocket.socket;
      }
      if (only_retrieve_existing_socket) {
        return null;
      }
      return setupWebSocket(sessionId, runId);
    }
  };

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  const updateSessionRunStatus = (sessionId: number, status: RunStatus) => {
    setSessionRunStatuses((prev) => ({
      ...prev,
      [sessionId]: status,
    }));
  };

  const createDefaultSession = async () => {
    if (!user?.email) return;

    try {
      setIsLoading(true);
      const defaultName = `Default Session - ${new Date().toLocaleDateString(
        undefined,
        {
          year: "numeric",
          month: "long",
          day: "numeric",
          hour: "2-digit",
          minute: "2-digit",
        }
      )}`;

      const created = await sessionAPI.createSession(
        {
          name: defaultName,
        },
        user.email
      );

      setSessions([created, ...sessions]);
      setSession(created);
      window.history.pushState({}, "", `?sessionId=${created.id}`);
    } catch (error) {
      console.error("Error creating default session:", error);
      messageApi.error("Error creating default session");
    } finally {
      setIsLoading(false);
    }
  };

  const chatViews = useMemo(() => {
    return sessions.map((s: Session) => {
      const status = sessionRunStatuses[s.id] as RunStatus;
      const isSessionPotentiallyActive = [
        "active",
        "awaiting_input",
        "pausing",
        "paused",
      ].includes(status);

      if (!isSessionPotentiallyActive && session?.id !== s.id) return null;

      return (
        <div
          key={s.id}
          className={`${session?.id === s.id ? "block" : "hidden"} relative`}
        >
          {isLoading && session?.id === s.id && (
            <div className="absolute inset-0 z-10 flex items-center justify-center">
              <Spin size="large" tip="Loading session..." />
            </div>
          )}
          <ChatView
            session={s}
            onSessionNameChange={handleSessionName}
            getSessionSocket={getSessionSocket}
            visible={session?.id === s.id}
            onRunStatusChange={updateSessionRunStatus}
          />
        </div>
      );
    });
  }, [
    sessions,
    session?.id,
    handleSessionName,
    getSessionSocket,
    updateSessionRunStatus,
    isLoading,
    sessionRunStatuses,
  ]);

  // Add cleanup handlers for page unload and connection loss
  useEffect(() => {
    const closeAllSockets = () => {
      Object.values(sessionSockets).forEach(({ socket }) => {
        try {
          socket.close();
        } catch (error) {
          console.error("Error closing socket:", error);
        }
      });
    };

    // Handle page unload/refresh
    window.addEventListener("beforeunload", closeAllSockets);

    // Handle connection loss
    window.addEventListener("offline", closeAllSockets);

    return () => {
      window.removeEventListener("beforeunload", closeAllSockets);
      window.removeEventListener("offline", closeAllSockets);
      closeAllSockets(); // Clean up on component unmount too
    };
  }, []); // Empty dependency array since we want this to run once on mount

  const handleCreateSessionFromPlan = (
    sessionId: number,
    sessionName: string,
    planData: any
  ) => {
    // First select the session
    handleSelectSession({ id: sessionId } as Session);

    // Then dispatch the plan data to the chat component
    setTimeout(() => {
      window.dispatchEvent(
        new CustomEvent("planReady", {
          detail: {
            planData: planData,
            sessionId: sessionId,
            messageId: `plan_${Date.now()}`,
          },
        })
      );
    }, 2000); // Give time for session selection to complete
  };

  return (
    <div className="relative flex flex-col h-full w-full">
      {contextHolder}

      <ContentHeader
        isMobileMenuOpen={isMobileMenuOpen}
        onMobileMenuToggle={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
        isSidebarOpen={isSidebarOpen}
        onToggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)}
        onNewSession={() => handleEditSession()}
      />

      <div className="flex flex-1 relative">
        <div
          className={`absolute left-0 top-0 h-full transition-all duration-200 ease-in-out ${
            isSidebarOpen ? "w-77" : "w-0"
          }`}
        >
          <Sidebar
            isOpen={isSidebarOpen}
            sessions={sessions}
            currentSession={session}
            onToggle={() => setIsSidebarOpen(!isSidebarOpen)}
            onSelectSession={handleSelectSession}
            onEditSession={handleEditSession}
            onDeleteSession={handleDeleteSession}
            isLoading={isLoading}
            sessionRunStatuses={sessionRunStatuses}
            activeSubMenuItem={activeSubMenuItem}
            onSubMenuChange={setActiveSubMenuItem}
            onStopSession={(sessionId: number) => {
              if (sessionId === undefined || sessionId === null) return;
              const id = Number(sessionId);
              // Find the session's socket and close it, update status
              const ws = sessionSockets[id]?.socket;
              if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(
                  JSON.stringify({
                    type: "stop",
                    reason: "Cancelled by user (sidebar)",
                  })
                );
                ws.close();
              }
              setSessionRunStatuses((prev) => ({
                ...prev,
                [id]: "stopped",
              }));
            }}
          />
        </div>

        <div
          className={`flex-1 transition-all -mr-4 duration-200 w-[200px] ${
            isSidebarOpen ? "ml-64" : "ml-0"
          }`}
        >
          {activeSubMenuItem === "current_session" ? (
            session && sessions.length > 0 ? (
              <div className="pl-4">{chatViews}</div>
            ) : (
              <div className="flex items-center justify-center h-full text-secondary">
                <Spin size="large" tip={"Loading..."} />
              </div>
            )
          ) : (
            <div className="h-full overflow-hidden pl-4">
              <PlanList
                onTabChange={setActiveSubMenuItem}
                onSelectSession={handleSelectSession}
                onCreateSessionFromPlan={handleCreateSessionFromPlan}
              />
            </div>
          )}
        </div>

        <SessionEditor
          session={editingSession}
          isOpen={isEditorOpen}
          onSave={handleSaveSession}
          onCancel={() => {
            setIsEditorOpen(false);
            setEditingSession(undefined);
          }}
        />
      </div>
    </div>
  );
};
