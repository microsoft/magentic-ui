import { UIRun, Message } from "../../types/datamodel";
import { IPlanStep } from "../../types/plan";
import { messageUtils } from "./rendermessage";

/**
 * Extract final answer and stop reason from messages and team result
 */
export const extractFinalAnswerInfo = (
  messages: Message[],
  teamResult?: UIRun["team_result"],
): { finalAnswer?: string; stopReason?: string } => {
  // Look for final answer in messages (reverse order to find latest)
  const finalAnswerMsg = [...messages]
    .reverse()
    .find(
      (msg) =>
        typeof msg.config?.content === "string" &&
        messageUtils.isFinalAnswer(msg.config?.metadata),
    );

  let finalAnswer: string | undefined;
  if (finalAnswerMsg && typeof finalAnswerMsg.config.content === "string") {
    finalAnswer = finalAnswerMsg.config.content
      .substring("Final Answer:".length)
      .trim();
  }

  // Get stop reason from team_result if available
  const stopReason = teamResult?.task_result?.stop_reason;

  return { finalAnswer, stopReason };
};

/**
 * Get effective plan (user-edited plan takes priority over original plan)
 */
export const getEffectivePlan = (
  updatedPlan: IPlanStep[],
  currentPlan?: { steps: IPlanStep[] },
): IPlanStep[] | undefined => {
  return updatedPlan.length > 0 ? updatedPlan : currentPlan?.steps;
};

/**
 * Calculate step progress information for dashboard display
 */
export const calculateStepProgress = (
  isPlanExecuting: boolean,
  currentStep: number,
  totalStepsFromBackend: number,
  effectivePlan?: IPlanStep[],
  currentInstruction?: string,
): {
  current_step?: number;
  total_steps?: number;
  current_step_title?: string;
  current_instruction?: string;
} => {
  const hasPlan = effectivePlan && effectivePlan.length > 0;

  // Get current step info from effectivePlan (user-edited or original)
  const currentStepInfo =
    currentStep >= 0 && effectivePlan?.[currentStep]
      ? effectivePlan[currentStep]
      : undefined;

  // Use actual executing total steps from backend if available, otherwise use effective plan length
  const total_steps =
    isPlanExecuting && totalStepsFromBackend > 0
      ? totalStepsFromBackend
      : hasPlan
        ? effectivePlan.length // Safe because hasPlan ensures length exists and > 0
        : undefined;

  return {
    // Only include step info if plan is executing
    current_step: isPlanExecuting ? currentStep : undefined,
    total_steps,
    current_step_title: isPlanExecuting ? currentStepInfo?.title : undefined,
    current_instruction: isPlanExecuting ? currentInstruction : undefined,
  };
};
