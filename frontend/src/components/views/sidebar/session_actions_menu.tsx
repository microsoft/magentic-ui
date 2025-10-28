import React from "react";
import { Dropdown, Menu } from "antd";
import { Edit, Trash2, StopCircle, MoreVertical } from "lucide-react";
import LearnPlanButton from "../../features/Plans/LearnPlanButton";
import { Button } from "../../common/Button";

interface SessionActionsMenuProps {
  sessionId: number;
  isActive: boolean;
  onEdit: () => void;
  onStop: () => void;
  onDelete: () => void;
  className?: string;
}

export const SessionActionsMenu: React.FC<SessionActionsMenuProps> = ({
  sessionId,
  isActive,
  onEdit,
  onStop,
  onDelete,
  className = "",
}) => {
  return (
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
            <Trash2 className="-mt-0.5 mr-1.5 inline-block h-4 w-4" /> Delete
          </Menu.Item>
          <Menu.Item
            key="learn-plan"
            onClick={(e) => e.domEvent.stopPropagation()}
          >
            <LearnPlanButton sessionId={sessionId} messageId={-1} />
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
        className={`h-6 min-w-[24px] !p-0 ${className}`}
      />
    </Dropdown>
  );
};
