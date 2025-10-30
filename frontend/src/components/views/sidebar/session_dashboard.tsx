import React, { useMemo, useCallback } from "react";
import { InfoIcon } from "lucide-react";
import type { Session, UIRunStatus, UIRun } from "../../types/datamodel";
import { SessionDashboardCard } from "./session_dashboard_card";

interface SessionDashboardProps {
  filteredSessions: Session[];
  currentSession: Session | null;
  isLoading?: boolean;
  onSelectSession: (session: Session) => void;
  onStopSession: (sessionId: number) => void;
  onEditSession: (session?: Session) => void;
  onDeleteSession: (sessionId: number) => void;
  sessionRunStatuses: { [sessionId: number]: UIRunStatus };
  sessionRunData: { [sessionId: number]: Partial<UIRun> };
}

export const SessionDashboard: React.FC<SessionDashboardProps> = ({
  filteredSessions,
  currentSession,
  isLoading = false,
  onSelectSession,
  onStopSession,
  onEditSession,
  onDeleteSession,
  sessionRunStatuses,
  sessionRunData,
}) => {
  // Stable callback handlers that accept sessionId
  const handleSelect = useCallback(
    (session: Session) => {
      onSelectSession(session);
    },
    [onSelectSession],
  );

  const handleEdit = useCallback(
    (session: Session) => {
      onEditSession(session);
    },
    [onEditSession],
  );

  const handleStop = useCallback(
    (sessionId: number) => {
      onStopSession(sessionId);
    },
    [onStopSession],
  );

  const handleDelete = useCallback(
    (sessionId: number) => {
      onDeleteSession(sessionId);
    },
    [onDeleteSession],
  );

  return (
    <div className="scroll h-[calc(100%-200px)] w-full overflow-y-auto">
      {filteredSessions.length === 0 ? (
        <div className="mr-2 rounded border border-dashed p-2 text-center text-sm text-secondary">
          <InfoIcon className="-mt-0.5 mr-1.5 inline-block h-4 w-4" />
          No sessions found
        </div>
      ) : (
        <div className="space-y-2">
          {filteredSessions.map((s) => {
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
                currentStep={runData?.current_step}
                totalSteps={runData?.total_steps}
                currentStepTitle={runData?.current_step_title}
                currentInstruction={runData?.current_instruction}
                finalAnswer={runData?.final_answer}
                stopReason={runData?.stop_reason}
                onSelect={handleSelect}
                onEdit={handleEdit}
                onStop={handleStop}
                onDelete={handleDelete}
              />
            );
          })}
        </div>
      )}
    </div>
  );
};
