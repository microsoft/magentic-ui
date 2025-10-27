import React, { useMemo, useCallback } from "react";
import { Dropdown, Menu } from "antd";
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
} from "lucide-react";
import type {
  Session,
  GroupedSessions,
  RunStatus,
} from "../../types/datamodel";
import { SessionRunStatusIndicator } from "../statusicon";
import LearnPlanButton from "../../features/Plans/LearnPlanButton";
import { Button } from "../../common/Button";

interface SessionListProps {
  sortedSessions: Session[];
  groupedSessions: GroupedSessions;
  currentSession: Session | null;
  isLoading?: boolean;
  onSelectSession: (session: Session) => void;
  onStopSession: (sessionId: number) => void;
  onEditSession: (session?: Session) => void;
  onDeleteSession: (sessionId: number) => void;
  sessionRunStatuses: { [sessionId: number]: RunStatus };
}

export const SessionList: React.FC<SessionListProps> = ({
  sortedSessions,
  groupedSessions,
  currentSession,
  isLoading = false,
  onSelectSession,
  onStopSession,
  onEditSession,
  onDeleteSession,
  sessionRunStatuses,
}) => {
  // Helper function to render session group
  const renderSessionGroup = useCallback(
    (sessions: Session[]) => (
      <>
        {sessions.map((s) => {
          const status = s.id ? sessionRunStatuses[s.id] : undefined;
          const isActive = status
            ? ["active", "awaiting_input", "pausing", "paused"].includes(status)
            : false;
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
    ),
    [
      sessionRunStatuses,
      isLoading,
      currentSession,
      onSelectSession,
      onStopSession,
      onEditSession,
      onDeleteSession,
    ]
  );

  const content = useMemo(
    () => (
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
                <div className="py-2 text-sm text-secondary">Yesterday</div>
                {renderSessionGroup(groupedSessions.yesterday)}
              </div>
            )}
            {groupedSessions.last7Days.length > 0 && (
              <div>
                <div className="py-2 text-sm text-secondary">Last 7 Days</div>
                {renderSessionGroup(groupedSessions.last7Days)}
              </div>
            )}
            {groupedSessions.last30Days.length > 0 && (
              <div>
                <div className="py-2 text-sm text-secondary">Last 30 Days</div>
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
    ),
    [sortedSessions, groupedSessions, renderSessionGroup]
  );

  return content;
};
