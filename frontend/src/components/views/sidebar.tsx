import React, { useMemo, useState } from "react";
import { Tooltip } from "antd";
import { Plus, RefreshCcw, Archive, Server } from "lucide-react";
import type {
  Session,
  GroupedSessions,
  UIRunStatus,
  UIRun,
} from "../types/datamodel";
import SubMenu from "../common/SubMenu";
import { SessionList } from "./sidebar/session_list";
import { SessionDashboard } from "./sidebar/session_dashboard";
import { Button } from "../common/Button";

interface SidebarProps {
  isOpen: boolean;
  sessions: Session[];
  currentSession: Session | null;
  onToggle: () => void;
  onSelectSession: (session: Session) => void;
  onEditSession: (session?: Session) => void;
  onDeleteSession: (sessionId: number) => void;
  isLoading?: boolean;
  sessionRunStatuses: { [sessionId: number]: UIRunStatus };
  sessionRunData: { [sessionId: number]: Partial<UIRun> };
  activeSubMenuItem: string;
  onSubMenuChange: (tabId: string) => void;
  onStopSession: (sessionId: number) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  isOpen,
  sessions,
  currentSession,
  onToggle,
  onSelectSession,
  onEditSession,
  onDeleteSession,
  isLoading = false,
  sessionRunStatuses,
  sessionRunData,
  activeSubMenuItem,
  onSubMenuChange,
  onStopSession,
}) => {
  // Session view mode: active, needs_attention, or history
  const [sessionsViewMode, setSessionsViewMode] = useState<
    "active" | "needs_attention" | "history"
  >("active");

  // Group sessions by time period
  const groupSessions = (sessions: Session[]): GroupedSessions => {
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    const last7Days = new Date(today);
    last7Days.setDate(last7Days.getDate() - 7);
    const last30Days = new Date(today);
    last30Days.setDate(last30Days.getDate() - 30);

    return {
      today: sessions.filter((s) => {
        const date = new Date(s.created_at || "");
        return date >= today;
      }),
      yesterday: sessions.filter((s) => {
        const date = new Date(s.created_at || "");
        return date >= yesterday && date < today;
      }),
      last7Days: sessions.filter((s) => {
        const date = new Date(s.created_at || "");
        return date >= last7Days && date < yesterday;
      }),
      last30Days: sessions.filter((s) => {
        const date = new Date(s.created_at || "");
        return date >= last30Days && date < last7Days;
      }),
      older: sessions.filter((s) => {
        const date = new Date(s.created_at || "");
        return date < last30Days;
      }),
    };
  };

  // Sort sessions by date in descending order (most recent first)
  const sortedSessions = useMemo(
    () =>
      [...sessions].sort((a, b) => {
        return (
          new Date(b.created_at || "").getTime() -
          new Date(a.created_at || "").getTime()
        );
      }),
    [sessions],
  );

  const groupedSessions = useMemo(
    () => groupSessions(sortedSessions),
    [sortedSessions],
  );

  // Filter sessions based on current tab
  const filteredSessions = useMemo(() => {
    if (sessionsViewMode === "active") {
      // Active: sessions that are currently running (not completed or timeout)
      return sortedSessions.filter((s) => {
        const status = s.id ? sessionRunStatuses[s.id] : undefined;
        return (
          status &&
          [
            "created",
            "active",
            "awaiting_input",
            "error",
            "paused",
            "pausing",
            "resuming",
            "connected",
            "final_answer_awaiting_input",
          ].includes(status)
        );
      });
    } else if (sessionsViewMode === "needs_attention") {
      // Needs Attention: sessions awaiting input, paused, or have errors
      return sortedSessions.filter((s) => {
        const status = s.id ? sessionRunStatuses[s.id] : undefined;
        return status && ["awaiting_input", "error"].includes(status);
      });
    } else {
      // History: all sessions
      return sortedSessions;
    }
  }, [sortedSessions, sessionsViewMode, sessionRunStatuses, sessionRunData]);

  const sidebarContent = useMemo(() => {
    if (!isOpen) {
      return null;
    }

    return (
      <div className="h-full w-full overflow-hidden border-r border-secondary px-3">
        <div className="mb-4">
          <SubMenu
            items={[
              {
                id: "mcp_servers",
                label: "MCP Servers",
                icon: <Server className="h-4 w-4" />,
              },
              {
                id: "saved_plan",
                label: "Saved Plans",
                icon: <Archive className="h-4 w-4" />,
              },
            ]}
            activeItem={activeSubMenuItem}
            onClick={onSubMenuChange}
          />
        </div>

        {
          <>
            <div className="flex items-center justify-between border-secondary py-2">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-primary">
                  Sessions
                </span>

                <span className="text-xs text-secondary">
                  {sortedSessions.length}
                </span>

                {isLoading && (
                  <RefreshCcw className="h-3 w-3 animate-spin text-secondary" />
                )}
              </div>

              {/* Session tabs */}
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setSessionsViewMode("active")}
                  className={`rounded px-2 py-1 text-xs transition-colors ${
                    sessionsViewMode === "active"
                      ? "bg-magenta-active outline-magenta-900/50 text-magenta-700 outline outline-1"
                      : "text-secondary hover:text-primary"
                  }`}
                >
                  Active
                </button>
                <button
                  onClick={() => setSessionsViewMode("needs_attention")}
                  className={`rounded px-2 py-1 text-xs transition-colors ${
                    sessionsViewMode === "needs_attention"
                      ? "bg-magenta-active outline-magenta-900/50 text-magenta-700 outline outline-1"
                      : "text-secondary hover:text-primary"
                  }`}
                >
                  Needs Attention
                </button>
                <button
                  onClick={() => setSessionsViewMode("history")}
                  className={`rounded px-2 py-1 text-xs transition-colors ${
                    sessionsViewMode === "history"
                      ? "bg-magenta-active outline-magenta-900/50 text-magenta-700 outline outline-1"
                      : "text-secondary hover:text-primary"
                  }`}
                >
                  History
                </button>
              </div>
            </div>

            <div className="my-4 flex text-sm">
              <Tooltip title="Create new session">
                <Button
                  className="w-full"
                  variant="primary"
                  size="md"
                  icon={<Plus className="h-4 w-4" />}
                  onClick={() => onEditSession()}
                  disabled={isLoading}
                >
                  New Session
                </Button>
              </Tooltip>
            </div>

            {sessionsViewMode === "history" ? (
              <SessionList
                groupedSessions={groupedSessions}
                currentSession={currentSession}
                isLoading={isLoading}
                onSelectSession={onSelectSession}
                onEditSession={onEditSession}
                onStopSession={onStopSession}
                onDeleteSession={onDeleteSession}
                sessionRunStatuses={sessionRunStatuses}
                sessionRunData={sessionRunData}
              />
            ) : (
              <SessionDashboard
                filteredSessions={filteredSessions}
                currentSession={currentSession}
                isLoading={isLoading}
                onSelectSession={onSelectSession}
                onEditSession={onEditSession}
                onStopSession={onStopSession}
                onDeleteSession={onDeleteSession}
                sessionRunStatuses={sessionRunStatuses}
                sessionRunData={sessionRunData}
              />
            )}
          </>
        }
      </div>
    );
  }, [
    isOpen,
    activeSubMenuItem,
    onSubMenuChange,
    sortedSessions,
    groupedSessions,
    filteredSessions,
    isLoading,
    onEditSession,
    onSelectSession,
    onStopSession,
    onDeleteSession,
    sessionRunStatuses,
    sessionRunData,
    currentSession,
    sessionsViewMode,
  ]);

  return sidebarContent;
};
