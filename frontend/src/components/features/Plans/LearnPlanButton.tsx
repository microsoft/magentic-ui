import React, { useState, useContext } from "react";
import { message, Spin, Tooltip } from "antd";
import { useTranslation } from "react-i18next";
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
  const { t } = useTranslation();
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
      message.error(t("learnPlanButton.missingSessionOrUser"));
      return;
    }

    try {
      setIsLearning(true);
      setError(null);
      message.loading({
        content: t("learnPlanButton.creatingPlan"),
        key: "learnPlan",
      });

      const response = await planAPI.learnPlan(sessionId, effectiveUserId);

      if (response && response.status) {
        message.success({
          content: t("learnPlanButton.planCreatedSuccessfully"),
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
        throw new Error(response?.message || t("learnPlanButton.failedToCreatePlan"));
      }
    } catch (error) {
      console.error("Error creating plan:", error);
      setError(error instanceof Error ? error.message : t("learnPlanButton.unknownError"));
      message.error({
        content: `${t("learnPlanButton.failedToCreatePlan")}: ${
          error instanceof Error ? error.message : t("learnPlanButton.unknownError")
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
      <Tooltip title={t("learnPlanButton.planSavedToLibrary")}>
        <div
          className={`inline-flex items-center px-3 py-1.5 rounded-md ${
            darkMode === "dark"
              ? "bg-green-900/30 text-green-400 border border-green-700"
              : darkMode === "light"
              ? "bg-green-100 text-green-700 border border-green-200"
              : darkMode === "spirits"
              ? "bg-green-100 text-green-700 border border-green-200"
              : "bg-green-100 text-green-700 border border-green-200"
          }`}
        >
          <CheckCircleIcon className="h-4 w-4 mr-1.5" />
          <span className="text-sm font-medium">{t("learnPlanButton.planLearned")}</span>
        </div>
      </Tooltip>
    );
  }

  // If learning, show spinner
  if (isLearning) {
    return (
      <Tooltip title={t("learnPlanButton.creatingPlanFromConversation")}>
        <button
          disabled
          className={`inline-flex items-center px-3 py-1.5 rounded-md transition-colors ${
            darkMode === "dark"
              ? "bg-blue-800/30 text-blue-400 border border-blue-700"
              : darkMode === "light"
              ? "bg-blue-100 text-blue-800 border border-blue-200"
              : darkMode === "spirits"
              ? "bg-blue-100 text-blue-800 border border-blue-200"
              : "bg-blue-100 text-blue-800 border border-blue-200"
          } cursor-wait`}
        >
          <Spin size="small" className="mr-2" />
          <span className="text-sm font-medium">{t("learnPlanButton.learningPlan")}</span>
        </button>
      </Tooltip>
    );
  }

  // Default state - ready to learn
  return (
          <Tooltip title={t("learnPlanButton.learnReusablePlan")}>
      <button
        onClick={handleLearnPlan}
        disabled={!sessionId || !effectiveUserId}
        className={`inline-flex items-center px-3 py-1.5 rounded-md transition-colors ${
          darkMode === "dark"
            ? "bg-blue-700/20 text-blue-400 border border-blue-400/50 hover:bg-blue-700/30 hover:border-blue-700"
            : darkMode === "light"
            ? "bg-blue-400 text-blue-800 border border-blue-200 hover:bg-blue-100 hover:border-blue-300"
            : darkMode === "spirits"
            ? "bg-blue-400 text-blue-800 border border-blue-200 hover:bg-blue-100 hover:border-blue-300"
            : "bg-blue-400 text-blue-800 border border-blue-200 hover:bg-blue-100 hover:border-blue-300"
        } ${
          !sessionId || !effectiveUserId
            ? "opacity-50 cursor-not-allowed"
            : "cursor-pointer"
        }`}
      >
        <LightBulbIcon
          className={`h-4 w-4 mr-1.5 ${
            darkMode === "dark" ? "text-blue-400" : darkMode === "spirits" ? "text-blue-800" : "text-blue-800"
          }`}
        />
        <span className="text-sm font-medium">{t("learnPlanButton.learnPlan")}</span>
      </button>
    </Tooltip>
  );
};

export default LearnPlanButton;
