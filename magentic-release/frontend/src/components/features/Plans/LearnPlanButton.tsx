import React, { useState, useContext } from "react";
import { message, Spin, Tooltip } from "antd";
import { appContext } from "../../../hooks/provider";
import { PlanAPI } from "../../views/api";
import { LightBulbIcon, CheckCircleIcon } from "@heroicons/react/24/outline";

interface LearnPlanButtonProps {
  sessionId: number;
  messageId: number;
  userId?: string;
  onSuccess?: (planId: string) => void;
}

export const LearnPlanButton: React.FC<LearnPlanButtonProps> = ({
  sessionId,
  messageId,
  userId,
  onSuccess,
}) => {
  const [isLearning, setIsLearning] = useState(false);
  const [isLearned, setIsLearned] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { user, darkMode } = useContext(appContext);
  const planAPI = new PlanAPI();

  const effectiveUserId = userId || user?.email;

  React.useEffect(() => {
    if (messageId !== -1) {
      const learnedPlans = JSON.parse(
        localStorage.getItem("learned_plans") || "{}"
      );
      if (learnedPlans[`${sessionId}-${messageId}`]) {
        setIsLearned(true);
      }
    }
  }, [sessionId, messageId]);

  const handleLearnPlan = async () => {
    if (!sessionId || !effectiveUserId) {
      message.error("Missing session or user information");
      return;
    }

    try {
      setIsLearning(true);
      setError(null);
      message.loading({
        content: "Creating plan from conversation...",
        key: "learnPlan",
      });

      const response = await planAPI.learnPlan(sessionId, effectiveUserId);

      if (response && response.status) {
        message.success({
          content: "Plan created successfully!",
          key: "learnPlan",
          duration: 2,
        });

        if (onSuccess && response.data?.id) {
          onSuccess(response.data.id);
        }

        // Mark as learned when successful
        setIsLearned(true);
        const learnedPlans = JSON.parse(
          localStorage.getItem("learned_plans") || "{}"
        );
        learnedPlans[`${sessionId}-${messageId}`] = true;
        localStorage.setItem("learned_plans", JSON.stringify(learnedPlans));
      } else {
        throw new Error(response?.message || "Failed to create plan");
      }
    } catch (error) {
      console.error("Error creating plan:", error);
      setError(error instanceof Error ? error.message : "Unknown error");
      message.error({
        content: `Failed to create plan: ${
          error instanceof Error ? error.message : "Unknown error"
        }`,
        key: "learnPlan",
      });
    } finally {
      setIsLearning(false);
    }
  };

  // If already learned, show success message
  if (isLearned) {
    return (
      <Tooltip title="This plan has been saved to your library">
        <div
          className={`inline-flex items-center px-3 py-1.5 rounded-md ${
            darkMode === "dark"
              ? "bg-green-900/30 text-green-400 border border-green-700"
              : "bg-green-100 text-green-700 border border-green-200"
          }`}
        >
          <CheckCircleIcon className="h-4 w-4 mr-1.5" />
          <span className="text-sm font-medium">Plan Learned</span>
        </div>
      </Tooltip>
    );
  }

  // If learning, show spinner
  if (isLearning) {
    return (
      <Tooltip title="Creating a plan from this conversation">
        <button
          disabled
          className={`inline-flex items-center px-3 py-1.5 rounded-md transition-colors ${
            darkMode === "dark"
              ? "bg-blue-800/30 text-blue-400 border border-blue-700"
              : "bg-blue-100 text-blue-800 border border-blue-200"
          } cursor-wait`}
        >
          <Spin size="small" className="mr-2" />
          <span className="text-sm font-medium">Learning Plan...</span>
        </button>
      </Tooltip>
    );
  }

  // Default state - ready to learn
  return (
    <Tooltip title="Learn a reusable plan from this conversation and save it to your library">
      <button
        onClick={handleLearnPlan}
        disabled={!sessionId || !effectiveUserId}
        className={`inline-flex items-center px-3 py-1.5 rounded-md transition-colors ${
          darkMode === "dark"
            ? "bg-blue-700/20 text-blue-400 border border-blue-400/50 hover:bg-blue-700/30 hover:border-blue-700"
            : "bg-blue-400 text-blue-800 border border-blue-200 hover:bg-blue-100 hover:border-blue-300"
        } ${
          !sessionId || !effectiveUserId
            ? "opacity-50 cursor-not-allowed"
            : "cursor-pointer"
        }`}
      >
        <LightBulbIcon
          className={`h-4 w-4 mr-1.5 ${
            darkMode === "dark" ? "text-blue-400" : "text-blue-800"
          }`}
        />
        <span className="text-sm font-medium">Learn Plan</span>
      </button>
    </Tooltip>
  );
};

export default LearnPlanButton;
