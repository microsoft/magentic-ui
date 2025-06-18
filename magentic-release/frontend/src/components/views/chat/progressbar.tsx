import * as React from "react";
import { CheckCircle2, RotateCw } from "lucide-react";
import { Tooltip } from "antd";

interface Plan {
  task: string;
  steps: Array<{
    title: string;
    details: string;
    agent_name?: string;
  }>;
  response?: string;
  plan_summary?: string;
}

interface ProgressBarProps {
  isPlanning: boolean;
  progress: {
    currentStep: number;
    totalSteps: number;
    plan?: Plan;
  };
  hasFinalAnswer: boolean;
}

export default function ProgressBar({
  isPlanning,
  progress,
  hasFinalAnswer,
}: ProgressBarProps) {
  // Adjust progress when we have final answer
  const adjustedProgress = React.useMemo(() => {
    if (hasFinalAnswer && progress.plan?.steps) {
      return {
        ...progress,
        currentStep: progress.plan.steps.length - 1,
        totalSteps: progress.plan.steps.length,
      };
    }
    return progress;
  }, [hasFinalAnswer, progress]);

  return (
    <div className="w-3/5 max-w-3xl mx-auto overflow-hidden flex flex-col">
      {isPlanning ? (
        <div className="flex justify-center w-full">
          <div className="w-full max-w-xs px-4 py-2">
            <div className="text-sm text-gray-500 mt-1 text-center font-medium">
              Planning...
            </div>
          </div>
        </div>
      ) : (
        adjustedProgress.totalSteps > 0 && (
          <div className="flex justify-center w-full">
            <div className="w-full px-4 py-2">
              <div className="relative w-full">
                {/* Progress bar */}
                <div className="w-full bg-gray-200 rounded-full h-1 dark:bg-gray-700">
                  <div className="relative w-full h-full">
                    {/* Completed section - full width when hasFinalAnswer */}
                    <div
                      className="absolute bg-green-600 h-1 rounded-full transition-all duration-300"
                      style={{
                        width: hasFinalAnswer
                          ? "100%"
                          : `${
                              (adjustedProgress.currentStep /
                                adjustedProgress.totalSteps) *
                              100
                            }%`,
                      }}
                    />
                    {/* Current section - hidden when hasFinalAnswer */}
                    {!hasFinalAnswer && (
                      <div
                        className="absolute bg-magenta-800 h-1 transition-all duration-300"
                        style={{
                          left: `${
                            (adjustedProgress.currentStep /
                              adjustedProgress.totalSteps) *
                            100
                          }%`,
                          width: `${(1 / adjustedProgress.totalSteps) * 100}%`,
                        }}
                      />
                    )}
                    {/* Remaining section - hidden when hasFinalAnswer */}
                    {!hasFinalAnswer && (
                      <div
                        className="absolute bg-gray-300 h-1 rounded-r-full transition-all duration-300"
                        style={{
                          left: `${
                            ((adjustedProgress.currentStep + 1) /
                              adjustedProgress.totalSteps) *
                            100
                          }%`,
                          width: `${
                            ((adjustedProgress.totalSteps -
                              adjustedProgress.currentStep -
                              1) /
                              adjustedProgress.totalSteps) *
                            100
                          }%`,
                        }}
                      />
                    )}
                  </div>
                </div>

                {/* Hoverable step sections */}
                <div
                  className="absolute w-full flex"
                  style={{ top: "-12px", height: "24px" }}
                >
                  {Array.from(
                    { length: adjustedProgress.totalSteps },
                    (_, index) => {
                      const step = adjustedProgress.plan?.steps[index];
                      const tooltipContent = step ? (
                        <div>
                          <div className="font-medium">
                            Step {index + 1}: {step.title}
                          </div>
                          <div className="text-xs mt-1">{step.details}</div>
                        </div>
                      ) : (
                        `Step ${index + 1}`
                      );

                      return (
                        <Tooltip
                          key={index}
                          title={tooltipContent}
                          placement="top"
                          overlayStyle={{ maxWidth: "300px" }}
                        >
                          <div
                            className="absolute h-full cursor-help"
                            style={{
                              left: `${
                                (index / adjustedProgress.totalSteps) * 100
                              }%`,
                              width: `${
                                (1 / adjustedProgress.totalSteps) * 100
                              }%`,
                            }}
                          />
                        </Tooltip>
                      );
                    }
                  )}
                </div>

                {/* Step markers */}
                <div
                  className="absolute w-full flex justify-between px-2"
                  style={{ top: "-7px" }}
                >
                  {Array.from(
                    { length: adjustedProgress.totalSteps },
                    (_, index) => {
                      const step = adjustedProgress.plan?.steps[index];
                      const tooltipContent = step ? (
                        <div>
                          <div className="font-medium">
                            Step {index + 1}: {step.title}
                          </div>
                          <div className="text-xs mt-1">{step.details}</div>
                        </div>
                      ) : (
                        `Step ${index + 1}`
                      );

                      return (
                        <div
                          key={index}
                          className="absolute"
                          style={{
                            left: `${
                              ((index + 0.5) / adjustedProgress.totalSteps) *
                              100
                            }%`,
                            transform: "translateX(-50%)",
                          }}
                        >
                          <Tooltip
                            title={tooltipContent}
                            placement="top"
                            overlayStyle={{ maxWidth: "300px" }}
                          >
                            <div
                              className={`w-5 h-5 rounded-full flex items-center justify-center cursor-help
                              ${
                                hasFinalAnswer ||
                                index < adjustedProgress.currentStep
                                  ? "bg-green-600 text-white"
                                  : index === adjustedProgress.currentStep
                                  ? "bg-magenta-800 text-white"
                                  : "bg-gray-400 text-white"
                              }`}
                            >
                              {hasFinalAnswer ||
                              index < adjustedProgress.currentStep ? (
                                <CheckCircle2 className="w-4 h-4" />
                              ) : index === adjustedProgress.currentStep ? (
                                <RotateCw className="w-4 h-4 animate-spin" />
                              ) : (
                                <span className="text-xs font-medium">
                                  {index + 1}
                                </span>
                              )}
                            </div>
                          </Tooltip>
                        </div>
                      );
                    }
                  )}
                </div>

                {/* Status text */}
                <div className="text-sm text-gray-500 mt-5 text-center">
                  {hasFinalAnswer ? (
                    <span className="text-green-600 font-medium">
                      Task Completed
                    </span>
                  ) : adjustedProgress.plan?.task ? (
                    <span>
                      Step {adjustedProgress.currentStep + 1} of{" "}
                      {adjustedProgress.totalSteps}
                      {adjustedProgress.plan?.steps[
                        adjustedProgress.currentStep
                      ]?.title &&
                        `: ${adjustedProgress.plan.steps[
                          adjustedProgress.currentStep
                        ].title.substring(0, 30)}...`}
                    </span>
                  ) : (
                    <span>
                      Step {adjustedProgress.currentStep + 1} of{" "}
                      {adjustedProgress.totalSteps}
                      {adjustedProgress.plan?.steps[
                        adjustedProgress.currentStep
                      ]?.title &&
                        `: ${adjustedProgress.plan.steps[
                          adjustedProgress.currentStep
                        ].title.substring(0, 30)}...`}
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>
        )
      )}
    </div>
  );
}
