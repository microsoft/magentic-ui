import React, { useState, useEffect } from "react";

interface SampleTasksProps {
  onSelect: (task: string) => void;
}

const SAMPLE_TASKS = [
  "When does the post office near me close today?",
  "Find the latest publications from the the Microsoft Research AI Frontiers Lab on Human-Agent interaction",
  "Which commit of Microsoft/markitdown repo introduced MCP support?",
  "Tell me when Bitcoin price drops 5% below its current value",
  "Order me a custom pizza from Tangle Town Pub with sausage, pineapple, and black olives",
  "Search arXiv for the latest papers on computer use agents",
];

const SampleTasks: React.FC<SampleTasksProps> = ({ onSelect }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [windowWidth, setWindowWidth] = useState(0);

  useEffect(() => {
    const handleResize = () => setWindowWidth(window.innerWidth);
    handleResize(); // Initial width
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  const isLargeScreen = windowWidth >= 1024; // lg breakpoint
  const tasksPerRow = windowWidth >= 640 ? 2 : 1; // 2 columns on sm, 1 on mobile
  const defaultVisibleTasks = tasksPerRow * 2;
  const maxVisibleTasks = isLargeScreen
    ? SAMPLE_TASKS.length
    : isExpanded
      ? SAMPLE_TASKS.length
      : defaultVisibleTasks;
  const visibleTasks = SAMPLE_TASKS.slice(0, maxVisibleTasks);
  const shouldShowToggle =
    !isLargeScreen && SAMPLE_TASKS.length > defaultVisibleTasks;

  return (
    <div className="mb-6">
      <div className="mb-2 mt-4 text-sm text-secondary opacity-70">
        or try a sample task from below{" "}
      </div>
      <div className="flex w-full flex-col gap-2">
        <div className="inline-flex w-full flex-wrap justify-center gap-2">
          {visibleTasks.map((task, idx) => (
            <button
              key={idx}
              className="w-80 rounded bg-tertiary px-4 py-2 text-left text-primary transition-colors hover:bg-secondary"
              onClick={() => onSelect(task)}
              type="button"
            >
              {task}
            </button>
          ))}
        </div>
        {shouldShowToggle && (
          <button
            className="mt-1 text-sm font-medium text-primary transition-colors hover:text-secondary"
            onClick={() => setIsExpanded(!isExpanded)}
            type="button"
          >
            {isExpanded ? "Show less..." : "Show more sample tasks..."}
          </button>
        )}
      </div>
    </div>
  );
};

export default SampleTasks;
