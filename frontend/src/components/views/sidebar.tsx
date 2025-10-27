import React, { useMemo, useState } from "react";
import { Tooltip } from "antd";
import {
  Plus,
  Edit,
  Trash2,
  InfoIcon,
  RefreshCcw,
  Loader2,
  FileText,
  Archive,
  MoreVertical,
  StopCircle,
  Server,
  AlignJustify,
  LayoutGrid,
} from "lucide-react";
import type { Session, GroupedSessions, RunStatus } from "../types/datamodel";
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
  sessionRunStatuses: { [sessionId: number]: RunStatus };
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
  activeSubMenuItem,
  onSubMenuChange,
  onStopSession,
}) => {
  // DEV: Toggle between SessionList and SessionDashboard
  const [sessionsViewMode, setSessionsViewMode] = useState<
    "list" | "dashboard"
  >("list");

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

  const sidebarContent = useMemo(() => {
    if (!isOpen) {
      return null;
    }

    return (
      <div className="h-full w-full overflow-hidden border-r border-secondary">
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
                <span className="font-medium text-primary">Sessions</span>

                {isLoading ? (
                  <div className="flex py-2 text-sm text-secondary">
                    Loading...{" "}
                    <RefreshCcw className="ml-2 inline-block h-4 w-4 animate-spin" />
                  </div>
                ) : (
                  <span className="bg-accent/10 rounded py-2 text-sm text-secondary">
                    {sortedSessions.length}
                  </span>
                )}
              </div>

              {/* DEV: Toggle view mode */}
              <div className="flex gap-1">
                <Button
                  variant={sessionsViewMode === "list" ? "primary" : "tertiary"}
                  size="sm"
                  icon={<AlignJustify className="h-4 w-4" />}
                  onClick={() => setSessionsViewMode("list")}
                  title="List View"
                  className="min-w-[28px] !p-1"
                />
                <Button
                  variant={
                    sessionsViewMode === "dashboard" ? "primary" : "tertiary"
                  }
                  size="sm"
                  icon={<LayoutGrid className="h-4 w-4" />}
                  onClick={() => setSessionsViewMode("dashboard")}
                  title="Dashboard View"
                  className="min-w-[28px] !p-1"
                />
              </div>
            </div>

            <div className="my-4 flex text-sm">
              <div className="mr-2 w-full">
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
            </div>

            {sessionsViewMode === "list" ? (
              <SessionList
                sortedSessions={sortedSessions}
                groupedSessions={groupedSessions}
                currentSession={currentSession}
                isLoading={isLoading}
                onSelectSession={onSelectSession}
                onEditSession={onEditSession}
                onStopSession={onStopSession}
                onDeleteSession={onDeleteSession}
                sessionRunStatuses={sessionRunStatuses}
              />
            ) : (
              <SessionDashboard
                sortedSessions={sortedSessions}
                groupedSessions={groupedSessions}
                currentSession={currentSession}
                isLoading={isLoading}
                onSelectSession={onSelectSession}
                onEditSession={onEditSession}
                onStopSession={onStopSession}
                onDeleteSession={onDeleteSession}
                sessionRunStatuses={sessionRunStatuses}
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
    isLoading,
    onEditSession,
    onSelectSession,
    onStopSession,
    onDeleteSession,
    sessionRunStatuses,
    currentSession,
    sessionsViewMode,
  ]);

  return sidebarContent;
};
