import React, { useMemo } from "react";
import { InfoIcon } from "lucide-react";
import type {
  Session,
  GroupedSessions,
  RunStatus,
} from "../../types/datamodel";
import { SessionDashboardCard } from "./session_dashboard_card";

interface SessionDashboardProps {
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

export const SessionDashboard: React.FC<SessionDashboardProps> = ({
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
  // Helper function to render session cards
  const renderSessionCards = (sessions: Session[]) => (
    <div className="space-y-2">
      {sessions.map((s) => {
        const status = s.id ? sessionRunStatuses[s.id] : undefined;
        const isActive = status
          ? ["active", "awaiting_input", "pausing", "paused"].includes(status)
          : false;
        return (
          <SessionDashboardCard
            key={s.id}
            session={s}
            isActive={isActive}
            isCurrent={currentSession?.id === s.id}
            isLoading={isLoading}
            status={status}
            onSelect={() => onSelectSession(s)}
            onEdit={() => onEditSession(s)}
            onStop={() => s.id && onStopSession(s.id)}
            onDelete={() => s.id && onDeleteSession(s.id)}
          />
        );
      })}
    </div>
  );

  return (
    <div className="overflow-y-auto h-[calc(100%-200px)] scroll w-full">
      {sortedSessions.length === 0 ? (
        <div className="p-2 mr-2 text-center text-secondary text-sm border border-dashed rounded">
          <InfoIcon className="w-4 h-4 inline-block mr-1.5 -mt-0.5" />
          No recent sessions found
        </div>
      ) : (
        <div className="space-y-4">
          {groupedSessions.today.length > 0 && (
            <div>
              <div className="py-2 text-sm text-secondary font-medium">
                Today
              </div>
              {renderSessionCards(groupedSessions.today)}
            </div>
          )}
          {groupedSessions.yesterday.length > 0 && (
            <div>
              <div className="py-2 text-sm text-secondary font-medium">
                Yesterday
              </div>
              {renderSessionCards(groupedSessions.yesterday)}
            </div>
          )}
          {groupedSessions.last7Days.length > 0 && (
            <div>
              <div className="py-2 text-sm text-secondary font-medium">
                Last 7 Days
              </div>
              {renderSessionCards(groupedSessions.last7Days)}
            </div>
          )}
          {groupedSessions.last30Days.length > 0 && (
            <div>
              <div className="py-2 text-sm text-secondary font-medium">
                Last 30 Days
              </div>
              {renderSessionCards(groupedSessions.last30Days)}
            </div>
          )}
          {groupedSessions.older.length > 0 && (
            <div>
              <div className="py-2 text-sm text-secondary font-medium">
                Older
              </div>
              {renderSessionCards(groupedSessions.older)}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
