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
                    ? "border-l-2 border-magenta-800 bg-secondary"
                    : ""
                }`}
                onClick={() => !isLoading && onSelectSession(s)}
              >
                <div className="flex min-w-0 flex-1 items-center gap-2">
                  <span className="truncate text-sm">{s.name}</span>
                  {s.id && (
                    <SessionRunStatusIndicator
                      status={sessionRunStatuses[s.id]}
                    />
                  )}
                </div>
                <div className="flex w-8 flex-shrink-0 justify-end gap-2 opacity-0 transition-opacity group-hover:opacity-100">
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
                          <Edit className="-mt-0.5 mr-1.5 inline-block h-4 w-4" />{" "}
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
                          <StopCircle className="-mt-0.5 mr-1.5 inline-block h-4 w-4" />{" "}
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
                          <Trash2 className="-mt-0.5 mr-1.5 inline-block h-4 w-4" />{" "}
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
                      icon={<MoreVertical className="h-4 w-4" />}
                      onClick={(e) => e.stopPropagation()}
                      className="h-6 min-w-[24px] !p-0"
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
    ],
  );

  const content = useMemo(
    () => (
      <div className="scroll h-[calc(100%-200px)] overflow-y-auto">
        {sortedSessions.length === 0 ? (
          <div className="mr-2 rounded border border-dashed p-2 text-center text-sm text-secondary">
            <InfoIcon className="-mt-0.5 mr-1.5 inline-block h-4 w-4" />
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
    [sortedSessions, groupedSessions, renderSessionGroup],
  );

  return content;
};
