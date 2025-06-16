import React from "react";
import { List, Tooltip } from "antd";
import { PlayCircle as PlayCircleIcon } from "lucide-react";

interface RelevantPlansProps {
  isSearching: boolean;
  relevantPlans: any[];
  darkMode: string;
  onUsePlan: (plan: any) => void;
}

const RelevantPlans: React.FC<RelevantPlansProps> = ({
  isSearching,
  relevantPlans,
  darkMode,
  onUsePlan,
}) => {
  if (isSearching) {
    return (
      <div
        className={`text-xs text-opacity-70 ml-2 mb-1 ${
          darkMode === "dark" ? "text-gray-400" : "text-gray-500"
        }`}
      >
        Finding relevant plans...
      </div>
    );
  }

  if (relevantPlans.length === 0) {
    return null;
  }

  return (
    <div
      className={`ml-2 mb-1 ${
        darkMode === "dark"
          ? "bg-[#333333] border border-gray-700"
          : "bg-white border border-gray-200"
      } rounded-md shadow-md absolute z-10 max-w-xl`}
      style={{
        maxHeight: "300px",
        bottom: "100%", // Position above the input
        marginBottom: "8px", // Add some space between dropdown and input
      }}
    >
      {/* Header */}
      <div
        className={`py-2 px-4 font-medium text-sm border-b ${
          darkMode === "dark"
            ? "border-gray-700 bg-gray-800"
            : "border-gray-200 bg-gray-50"
        }`}
      >
        Found relevant plans:
      </div>

      {/* Plans list */}
      <List
        size="small"
        dataSource={relevantPlans}
        renderItem={(plan) => (
          <List.Item
            onClick={() => onUsePlan(plan)}
            className={`cursor-pointer hover:${
              darkMode === "dark" ? "bg-gray-700" : "bg-gray-100"
            } px-4 py-2 border-b ${
              darkMode === "dark" ? "border-gray-700" : "border-gray-100"
            } last:border-b-0`}
          >
            <div className="flex items-center justify-between w-full">
              <div className="flex-1 overflow-hidden text-left">
                <div className="text-sm font-normal truncate">{plan.task}</div>
                <div className="text-xs text-gray-500">
                  {plan.steps?.length || 0} steps
                </div>
              </div>
              <Tooltip title="Attach Plan to query">
                <div className="ml-3 flex-shrink-0">
                  <PlayCircleIcon
                    className={`h-5 w-5 ${
                      darkMode === "dark" ? "text-blue-400" : "text-blue-500"
                    } hover:scale-110 transition-transform cursor-pointer`}
                  />
                </div>
              </Tooltip>
            </div>
          </List.Item>
        )}
      />
    </div>
  );
};

export default RelevantPlans;
