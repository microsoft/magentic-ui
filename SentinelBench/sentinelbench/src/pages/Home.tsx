import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import DifficultySelector from "../components/DifficultySelector";
import { routes, RouteConfig } from "../router/routes";
import { recordTaskView } from "../utils/analytics";
import { TaskStateManager } from "../utils/TaskStateManager";

export default function Home() {
  const [showSettingsDropdown, setShowSettingsDropdown] = useState(false);
  const [adminConsoleEnabled, setAdminConsoleEnabled] = useState(() => {
    return localStorage.getItem('adminConsoleEnabled') === 'true';
  });
  const [degroupTaskVariants, setDegroupTaskVariants] = useState(() => {
    return localStorage.getItem('degroupTaskVariants') === 'true';
  });
  const [selectedTask, setSelectedTask] = useState<RouteConfig | null>(null);
  const [showDifficultySelector, setShowDifficultySelector] = useState(false);

  useEffect(() => {
    (async () => {
      await recordTaskView("home", Date.now());
    })();
  }, []);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (showSettingsDropdown && !(event.target as Element).closest('.relative')) {
        setShowSettingsDropdown(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [showSettingsDropdown]);
  const [searchParams] = useSearchParams();
  const isLocalhost = window.location.hostname === "localhost";
  const showDownloads =
    searchParams.get("showDownloads") === "true" || isLocalhost;

  // Filter sentinel tasks
  const sentinelTasks = routes.filter(route => 
    route.tags?.includes("sentinel") && 
    route.path !== "sentinel-visualization" &&
    route.component !== null && // Only include routes that have actual components
    route.password !== undefined // Must have a password to be a real task
  );

  const visibleRoutes = degroupTaskVariants ? 
    // When degrouped, show all task variants as individual panels
    sentinelTasks
      .sort((a, b) => {
        // First sort by base_task, then by difficulty
        const baseTaskCompare = (a.base_task || a.path).localeCompare(b.base_task || b.path);
        if (baseTaskCompare !== 0) return baseTaskCompare;
        
        const difficultyOrder = { easy: 0, medium: 1, hard: 2 };
        return (difficultyOrder[a.difficulty as keyof typeof difficultyOrder] || 0) - 
               (difficultyOrder[b.difficulty as keyof typeof difficultyOrder] || 0);
      })
      .map(route => ({
        ...route,
        // Show the full title with difficulty for individual variants
        title: route.title,
        variants: undefined // No variants when degrouped
      }))
    :
    // When grouped, use the original grouping logic
    (() => {
      const groupedRoutes = new Map<string, typeof routes>();
      
      sentinelTasks.forEach(route => {
        const baseTask = route.base_task || route.path;
        if (!groupedRoutes.has(baseTask)) {
          groupedRoutes.set(baseTask, []);
        }
        groupedRoutes.get(baseTask)!.push(route);
      });

      // Convert grouped routes to display format
      return Array.from(groupedRoutes.entries()).map(([, taskRoutes]) => {
        // Sort variants by difficulty
        const sortedVariants = taskRoutes.sort((a, b) => {
          const difficultyOrder = { easy: 0, medium: 1, hard: 2 };
          return (difficultyOrder[a.difficulty as keyof typeof difficultyOrder] || 0) - 
                 (difficultyOrder[b.difficulty as keyof typeof difficultyOrder] || 0);
        });
        
        // Use the first (easiest) variant as the main route, with variants containing all
        const mainRoute = sortedVariants[0];
        return {
          ...mainRoute,
          // Override title to be more general if there are multiple variants
          title: sortedVariants.length > 1 ? mainRoute.title.replace(/ \((Easy|Medium|Hard)\)/, '') : mainRoute.title,
          description: mainRoute.description,
          variants: sortedVariants.length > 1 ? sortedVariants
            .filter(variant => variant.component !== null && variant.password !== undefined)
            .map(variant => ({
              path: variant.path,
              title: variant.difficulty === 'easy' ? 'Easy' : 
                     variant.difficulty === 'medium' ? 'Medium' : 'Hard',
              component: variant.component!,
              password: variant.password!,
              difficulty: variant.difficulty
            })) : undefined
        };
      });
    })();

  const downloadChallengesJSONL = () => {
    // Export all individual routes with proper task metadata
    const allSentinelRoutes = routes.filter(route => 
      route.tags?.includes("sentinel") && 
      route.path !== "sentinel-visualization" &&
      route.component !== null && // Only include routes that have actual components
      route.password !== undefined // Must have a password to be a real task
    );
    
    const jsonl = allSentinelRoutes
      .map((route) => {
        // Clean up the route object for testing
        const cleanRoute = {
          id: route.path,
          path: route.path,
          title: route.title,
          description: route.description,
          url: route.url,
          icon: route.icon,
          tags: route.tags,
          password: route.password,
          difficulty: route.difficulty,
          base_task: route.base_task,
          // Include all dimension data directly
          criteria: route.criteria,
          activity: route.activity,
          distraction: route.distraction,
          realism: route.realism,
          relative_vs_absolute: route.relative_vs_absolute || "",
          adversarial_attacks: route.adversarial_attacks || false,
          penalties: route.penalties || false
        };
        
        // Remove undefined/null values to keep JSONL clean
        Object.keys(cleanRoute).forEach(key => {
          if (cleanRoute[key as keyof typeof cleanRoute] === undefined || cleanRoute[key as keyof typeof cleanRoute] === null) {
            delete cleanRoute[key as keyof typeof cleanRoute];
          }
        });
        
        return JSON.stringify(cleanRoute);
      })
      .join("\n");

    const blob = new Blob([jsonl], { type: "application/x-jsonlines" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "sentinelbench-v1-challenges.jsonl";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    // Development logging only
    if (process.env.NODE_ENV === 'development') {
      console.log(`✅ Exported ${allSentinelRoutes.length} Sentinel tasks to sentinelbench-v1-challenges.jsonl`);
      console.log('Task breakdown by difficulty:', {
        easy: allSentinelRoutes.filter(r => r.difficulty === 'easy').length,
        medium: allSentinelRoutes.filter(r => r.difficulty === 'medium').length,
        hard: allSentinelRoutes.filter(r => r.difficulty === 'hard').length
      });
    }
  };

  const downloadChallengesCSV = () => {
    // Export all individual routes, not the grouped ones
    const allSentinelRoutes = routes.filter(route => 
      route.tags?.includes("sentinel") && route.path !== "sentinel-visualization"
    );
    
    const headers = [
      "id",
      "title",
      "description",
      "path",
      "password",
      "tags",
      "difficulty",
      "base_task",
    ];
    const csvContent = [
      headers.join(","),
      ...allSentinelRoutes.map((route) => {
        return [
          route.path,
          `"${route.title.replace(/"/g, '""')}"`,
          `"${route.description.replace(/"/g, '""')}"`,
          route.path,
          route.password,
          route.difficulty,
          route.base_task,
          `"${(route.tags || []).join(";")}"`,
        ].join(",");
      }),
    ].join("\n");

    const blob = new Blob([csvContent], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "sentinelbench-v1-challenges.csv";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const isOnMicrosoftDomain =
    window.location.hostname.includes("microsoft.com") || window.location.hostname.includes("msft.ai");

  const resetAllTaskStates = () => {
    if (window.confirm('Are you sure you want to reset ALL task states? This will clear all progress from all Sentinel tasks and cannot be undone.')) {
      // Get all saved task IDs
      const savedTasks = TaskStateManager.listSavedTasks();
      
      // Clear each task's state
      savedTasks.forEach(taskId => {
        TaskStateManager.clearState(taskId);
      });
      
      alert(`Reset complete! Cleared state for ${savedTasks.length} task(s). Refresh individual task pages to see the reset.`);
      setShowSettingsDropdown(false);
    }
  };

  const toggleAdminConsole = () => {
    const newState = !adminConsoleEnabled;
    setAdminConsoleEnabled(newState);
    localStorage.setItem('adminConsoleEnabled', newState.toString());
    
    // Dispatch custom event to notify other components
    window.dispatchEvent(new CustomEvent('adminConsoleToggle', { 
      detail: { enabled: newState } 
    }));
    
    setShowSettingsDropdown(false);
  };

  const toggleDegroupTaskVariants = () => {
    const newState = !degroupTaskVariants;
    setDegroupTaskVariants(newState);
    localStorage.setItem('degroupTaskVariants', newState.toString());
    setShowSettingsDropdown(false);
  };

  return (
    <div>
      <div className="bg-gradient-to-b from-purple-600/10 via-purple-500/5 to-white border-b border-purple-600/10">
        <div className="container mx-auto px-2 py-16">
          <div className="flex flex-col sm:flex-row justify-between items-center mb-6 gap-4">
            <div className="flex flex-col sm:flex-row items-center sm:items-baseline gap-4">
              <h1 className="text-5xl font-bold bg-gradient-to-br from-purple-600 via-purple-700 to-purple-800 bg-clip-text text-transparent">
                SentinelBench
              </h1>
            </div>
            <div className="flex gap-4 items-center">
              {isOnMicrosoftDomain && (
                <a
                  href="https://github.com/microsoft/SentinelBench"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hidden sm:block px-4 py-2 text-sm font-mono text-gray-400 hover:text-gray-600 transition-colors duration-200"
                >
                  <span className="flex items-center gap-2">
                    <svg
                      className="w-4 h-4"
                      viewBox="0 0 24 24"
                      fill="currentColor"
                    >
                      <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
                    </svg>
                    GitHub
                  </span>
                </a>
              )}
              {showDownloads && (
                <div className="hidden sm:flex gap-2">
                  <button
                    onClick={downloadChallengesJSONL}
                    className="px-4 py-2 text-sm font-mono text-gray-400 hover:text-gray-600 transition-colors duration-200"
                  >
                    ↓ Challenges JSONL
                  </button>
                  <button
                    onClick={downloadChallengesCSV}
                    className="px-4 py-2 text-sm font-mono text-gray-400 hover:text-gray-600 transition-colors duration-200"
                  >
                    ↓ Challenges CSV
                  </button>
                </div>
              )}
              
              {/* Settings Dropdown */}
              <div className="relative">
                <button
                  onClick={() => setShowSettingsDropdown(!showSettingsDropdown)}
                  className="px-4 py-2 text-sm font-mono text-gray-400 hover:text-gray-600 transition-colors duration-200 border border-gray-300 rounded"
                >
                  ⚙️ Settings
                </button>
                
                {showSettingsDropdown && (
                  <div className="absolute right-0 mt-2 w-56 bg-white border border-gray-200 rounded-lg shadow-xl z-50">
                    <div className="py-2">
                      
                      <button
                        onClick={toggleAdminConsole}
                        className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-100 flex items-center justify-between"
                      >
                        <span>🔧 Admin Console</span>
                        <span className={`text-xs px-2 py-1 rounded ${adminConsoleEnabled ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                          {adminConsoleEnabled ? 'ON' : 'OFF'}
                        </span>
                      </button>
                      
                      <button
                        onClick={toggleDegroupTaskVariants}
                        className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-100 flex items-center justify-between"
                      >
                        <span>📋 Show All Variants</span>
                        <span className={`text-xs px-2 py-1 rounded ${degroupTaskVariants ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                          {degroupTaskVariants ? 'ON' : 'OFF'}
                        </span>
                      </button>
                      
                      {isLocalhost && (
                        <button
                          onClick={resetAllTaskStates}
                          className="w-full px-4 py-2 text-left text-sm text-red-600 hover:bg-red-50 flex items-center"
                        >
                          <span>🗑️ Reset All Tasks</span>
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
          <div className="max-w-2xl">
            <p className="text-lg text-gray-600 text-left">
              <span className="sm:hidden">
                <span>
                  Benchmark AI agent performance on monitoring and persistent tasks. 
                  Measure success rates and completion latency across different time scales.
                </span>
              </span>
              <span className="hidden sm:inline">
                Benchmark AI agent performance on monitoring and persistent tasks. 
                Measure success rates and completion latency across different time scales.
              </span>
            </p>
          </div>
        </div>
      </div>
      <div className="bg-blue-50/40">
        <div className="container mx-auto px-2 py-8">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {visibleRoutes.map((route, index) => {
              const hasVariants = route.variants && route.variants.length > 0;
              
              if (hasVariants) {
                return (
                  <button
                    key={route.path}
                    onClick={() => {
                      setSelectedTask(route);
                      setShowDifficultySelector(true);
                    }}
                    className="group flex gap-3 p-4 bg-white hover:bg-gray-50 border border-gray-200 hover:border-blue-500 rounded-lg shadow-md hover:shadow-lg transition-all duration-100 ease-in-out relative text-left"
                  >
                    <div className="shrink-0 w-10 flex items-start pt-1">
                      <span
                        className="text-2xl group-hover:scale-110 transition-transform duration-100"
                        role="img"
                        aria-label={route.title}
                      >
                        {route.icon}
                      </span>
                    </div>
                    <div>
                      <div className="flex items-baseline gap-2">
                        <span className="text-xs font-medium text-gray-400">
                          {String(index + 1).padStart(2, "0")}
                        </span>
                        <h2 className="text-sm font-medium text-gray-900">
                          {route.title}
                        </h2>
                      </div>
                      <p className="mt-1 text-sm text-gray-500 line-clamp-2">
                        {route.description}
                      </p>
                    </div>
                  </button>
                );
              }
              
              return (
                <Link
                  key={route.path}
                  to={route.path}
                  className="group flex gap-3 p-4 bg-white hover:bg-gray-50 border border-gray-200 hover:border-blue-500 rounded-lg shadow-md hover:shadow-lg transition-all duration-100 ease-in-out relative"
                >
                  <div className="shrink-0 w-10 flex items-start pt-1">
                    <span
                      className="text-2xl group-hover:scale-110 transition-transform duration-100"
                      role="img"
                      aria-label={route.title}
                    >
                      {route.icon}
                    </span>
                  </div>
                  <div>
                    <div className="flex items-baseline gap-2">
                      <span className="text-xs font-medium text-gray-400">
                        {String(index + 1).padStart(2, "0")}
                      </span>
                      <h2 className="text-sm font-medium text-gray-900">
                        {route.title}
                      </h2>
                    </div>
                    <p className="mt-1 text-sm text-gray-500 line-clamp-2">
                      {route.description}
                    </p>
                  </div>
                </Link>
              );
            })}
          </div>
          <footer className="mt-8 text-center text-sm text-gray-500">
            Built by{" "}
            <span className="font-semibold">Microsoft AI Frontiers</span>
          </footer>
        </div>
      </div>
      
      {selectedTask && (
        <DifficultySelector
          isOpen={showDifficultySelector}
          onClose={() => {
            setShowDifficultySelector(false);
            setSelectedTask(null);
          }}
          taskTitle={selectedTask.title}
          taskIcon={selectedTask.icon}
          variants={selectedTask.variants || []}
        />
      )}
    </div>
  );
}
