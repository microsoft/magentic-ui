import React, { useMemo } from "react";
import { Tooltip, Dropdown, Menu } from "antd";
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
} from "lucide-react";
import type { Session, RunStatus } from "../types/datamodel";
import SubMenu from "../common/SubMenu";
import { SessionRunStatusIndicator } from "./statusicon";
import LearnPlanButton from "../features/Plans/LearnPlanButton";
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
  // Group sessions by time period
  const groupSessions = (sessions: Session[]) => {
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
    [sessions]
  );

  const groupedSessions = useMemo(
    () => groupSessions(sortedSessions),
    [sortedSessions]
  );

  // Helper function to render session group
  const renderSessionGroup = (sessions: Session[]) => (
    <>
      {sessions.map((s) => {
        const status = s.id ? sessionRunStatuses[s.id] : undefined;
        const isActive = status ? [
          "active",
          "awaiting_input",
          "pausing",
          "paused",
        ].includes(status) : false;
        return (
          <div key={s.id} className="relative">
            <div
              className={`group flex items-center p-2 py-1 text-sm ${
                isLoading
                  ? "pointer-events-none opacity-50"
                  : "cursor-pointer hover:bg-tertiary"
              } ${
                currentSession?.id === s.id
                  ? " border-l-2 border-magenta-800 bg-secondary"
                  : ""
              }`}
              onClick={() => !isLoading && onSelectSession(s)}
            >
              <div className="flex items-center gap-2 flex-1 min-w-0">
                <span className="truncate text-sm max-w-[140px]">
                  {s.name}
                </span>
                {s.id && (
                  <SessionRunStatusIndicator
                    status={sessionRunStatuses[s.id]}
                  />
                )}
              </div>
              <div className="flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity w-8 justify-end flex-shrink-0">
                <Dropdown
                  trigger={["click"]}
                  overlay={
                    <Menu>
                      <Menu.Item
                        key="edit"
                        onClick={(e) => {
                          e.domEvent.stopPropagation();
                          onEditSession(s);
                        }}
                      >
                        <Edit className="w-4 h-4 inline-block mr-1.5 -mt-0.5" />{" "}
                        Edit
                      </Menu.Item>
                      <Menu.Item
                        key="stop"
                        onClick={(e) => {
                          e.domEvent.stopPropagation();
                          if (isActive && s.id) onStopSession(s.id);
                        }}
                        disabled={!isActive}
                        danger
                      >
                        <StopCircle className="w-4 h-4 inline-block mr-1.5 -mt-0.5" />{" "}
                        Disconnect
                      </Menu.Item>
                      <Menu.Item
                        key="delete"
                        onClick={(e) => {
                          e.domEvent.stopPropagation();
                          if (s.id) onDeleteSession(s.id);
                        }}
                        danger
                      >
                        <Trash2 className="w-4 h-4 inline-block mr-1.5 -mt-0.5" />{" "}
                        Delete
                      </Menu.Item>
                      <Menu.Item
                        key="learn-plan"
                        onClick={(e) => e.domEvent.stopPropagation()}
                      >
                        <LearnPlanButton
                          sessionId={Number(s.id)}
                          messageId={-1}
                        />
                      </Menu.Item>
                    </Menu>
                  }
                  placement="bottomRight"
                >
                  <Button
                    variant="tertiary"
                    size="sm"
                    icon={<MoreVertical className="w-4 h-4" />}
                    onClick={(e) => e.stopPropagation()}
                    className="!p-0 min-w-[24px] h-6"
                  />
                </Dropdown>
              </div>
            </div>
          </div>
        );
      })}
    </>
  );

  const sidebarContent = useMemo(() => {
    if (!isOpen) {
      return null;
    }

    return (
      <div className="h-full border-r border-secondary">
        <div className="mb-4">
          <SubMenu
            items={[
              {
                id: "current_session",
                label: "Current Session",
                icon: <FileText className="w-4 h-4" />,
              },
              {
                id: "saved_plan",
                label: "Saved Plans",
                icon: <Archive className="w-4 h-4" />,
              },
            ]}
            activeItem={activeSubMenuItem}
            onClick={onSubMenuChange}
          />
        </div>

        {
          <>
            <div className="flex items-center justify-between py-2 border-secondary">
              <div className="flex items-center gap-2">
                <span className="text-primary font-medium">Sessions</span>

                {isLoading ? (
                  <div className="py-2 flex text-sm text-secondary">
                    Loading...{" "}
                    <RefreshCcw className="w-4 h-4 inline-block ml-2 animate-spin" />
                  </div>
                ) : (
                  <span className="py-2 bg-accent/10 text-sm text-secondary rounded">
                    {sortedSessions.length}
                  </span>
                )}
              </div>
            </div>

            <div className="my-4 flex text-sm">
              <div className="mr-2 w-full">
                <Tooltip title="Create new session">
                  <Button
                    className="w-full"
                    variant="primary"
                    size="md"
                    icon={<Plus className="w-4 h-4" />}
                    onClick={() => onEditSession()}
                    disabled={isLoading}
                  >
                    New Session
                  </Button>
                </Tooltip>
              </div>
            </div>

            <div className="overflow-y-auto h-[calc(100%-200px)] scroll">
              {sortedSessions.length === 0 ? (
                <div className="p-2 mr-2 text-center text-secondary text-sm border border-dashed rounded">
                  <InfoIcon className="w-4 h-4 inline-block mr-1.5 -mt-0.5" />
                  No recent sessions found
                </div>
              ) : (
                <>
                  {groupedSessions.today.length > 0 && (
                    <div>
                      <div className="py-2 text-sm text-secondary">Today</div>
                      {renderSessionGroup(groupedSessions.today)}
                    </div>
                  )}
                  {groupedSessions.yesterday.length > 0 && (
                    <div>
                      <div className="py-2 text-sm text-secondary">
                        Yesterday
                      </div>
                      {renderSessionGroup(groupedSessions.yesterday)}
                    </div>
                  )}
                  {groupedSessions.last7Days.length > 0 && (
                    <div>
                      <div className="py-2 text-sm text-secondary">
                        Last 7 Days
                      </div>
                      {renderSessionGroup(groupedSessions.last7Days)}
                    </div>
                  )}
                  {groupedSessions.last30Days.length > 0 && (
                    <div>
                      <div className="py-2 text-sm text-secondary">
                        Last 30 Days
                      </div>
                      {renderSessionGroup(groupedSessions.last30Days)}
                    </div>
                  )}
                  {groupedSessions.older.length > 0 && (
                    <div>
                      <div className="py-2 text-sm text-secondary">Older</div>
                      {renderSessionGroup(groupedSessions.older)}
                    </div>
                  )}
                </>
              )}
            </div>
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
    renderSessionGroup,
  ]);

  return sidebarContent;
};
