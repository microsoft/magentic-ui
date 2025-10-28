import React, { useMemo } from "react";
import { InfoIcon } from "lucide-react";
import type { Session, SidebarRunStatus, Run } from "../../types/datamodel";
import { SessionDashboardCard } from "./session_dashboard_card";

interface SessionDashboardProps {
  sortedSessions: Session[];
  currentSession: Session | null;
  isLoading?: boolean;
  onSelectSession: (session: Session) => void;
  onStopSession: (sessionId: number) => void;
  onEditSession: (session?: Session) => void;
  onDeleteSession: (sessionId: number) => void;
  sessionRunStatuses: { [sessionId: number]: SidebarRunStatus };
  sessionRunData: { [sessionId: number]: Partial<Run> };
}

export const SessionDashboard: React.FC<SessionDashboardProps> = ({
  sortedSessions,
  currentSession,
  isLoading = false,
  onSelectSession,
  onStopSession,
  onEditSession,
  onDeleteSession,
  sessionRunStatuses,
  sessionRunData,
}) => {
  return (
    <div className="scroll h-[calc(100%-200px)] w-full overflow-y-auto">
      {sortedSessions.length === 0 ? (
        <div className="mr-2 rounded border border-dashed p-2 text-center text-sm text-secondary">
          <InfoIcon className="-mt-0.5 mr-1.5 inline-block h-4 w-4" />
          No sessions found
        </div>
      ) : (
        <div className="space-y-2">
          {sortedSessions.map((s) => {
            const status = s.id ? sessionRunStatuses[s.id] : undefined;
            const runData = s.id ? sessionRunData[s.id] : undefined;
            const isActive = status
              ? ["active", "awaiting_input", "pausing", "paused"].includes(
                  status,
                )
              : false;
            return (
              <SessionDashboardCard
                key={s.id}
                session={s}
                isActive={isActive}
                isCurrent={currentSession?.id === s.id}
                isLoading={isLoading}
                status={status}
                inputRequest={runData?.input_request}
                errorMessage={runData?.error_message}
                onSelect={() => onSelectSession(s)}
                onEdit={() => onEditSession(s)}
                onStop={() => s.id && onStopSession(s.id)}
                onDelete={() => s.id && onDeleteSession(s.id)}
              />
            );
          })}
        </div>
      )}
    </div>
  );
};
