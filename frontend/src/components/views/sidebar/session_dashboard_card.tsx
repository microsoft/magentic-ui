import React from "react";
import { Dropdown, Menu } from "antd";
import { Edit, Trash2, StopCircle, MoreVertical } from "lucide-react";
import type { Session, RunStatus } from "../../types/datamodel";
import { SessionRunStatusIndicator } from "../statusicon";
import LearnPlanButton from "../../features/Plans/LearnPlanButton";
import { Button } from "../../common/Button";

interface SessionDashboardCardProps {
  session: Session;
  isActive: boolean;
  isCurrent: boolean;
  isLoading?: boolean;
  status?: RunStatus;
  onSelect: () => void;
  onEdit: () => void;
  onStop: () => void;
  onDelete: () => void;
}

export const SessionDashboardCard: React.FC<SessionDashboardCardProps> = ({
  session,
  isActive,
  isCurrent,
  isLoading = false,
  status,
  onSelect,
  onEdit,
  onStop,
  onDelete,
}) => {
  return (
    <div
      className={`group relative w-full p-2 text-sm ${
        isLoading
          ? "pointer-events-none opacity-50"
          : "cursor-pointer hover:bg-tertiary"
      } ${isCurrent ? "border-l-2 border-magenta-800 bg-secondary" : ""}`}
      onClick={() => !isLoading && onSelect()}
    >
      <div className="flex min-w-0 items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="mb-1 max-w-[180px] truncate text-sm font-medium">
            {session.name}
          </div>
          {session.created_at && (
            <div className="text-xs text-secondary">
              {new Date(session.created_at).toLocaleDateString()}
            </div>
          )}
        </div>

        <div className="flex flex-shrink-0 items-center gap-2">
          {session.id && <SessionRunStatusIndicator status={status} />}
          <Dropdown
            trigger={["click"]}
            overlay={
              <Menu>
                <Menu.Item
                  key="edit"
                  onClick={(e) => {
                    e.domEvent.stopPropagation();
                    onEdit();
                  }}
                >
                  <Edit className="-mt-0.5 mr-1.5 inline-block h-4 w-4" /> Edit
                </Menu.Item>
                <Menu.Item
                  key="stop"
                  onClick={(e) => {
                    e.domEvent.stopPropagation();
                    if (isActive) onStop();
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
                    onDelete();
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
                    sessionId={Number(session.id)}
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
              className="h-6 min-w-[24px] !p-0 opacity-0 transition-opacity group-hover:opacity-100"
            />
          </Dropdown>
        </div>
      </div>
    </div>
  );
};
