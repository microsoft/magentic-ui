import { useState, useEffect, useRef } from "react";
import { useTaskAnalytics } from "../utils/useTaskAnalytics";
import { TaskStateManager } from "../utils/TaskStateManager";
import { generateParameterPassword } from "../utils/parameterPassword";
import { URLParameterHandler } from "../utils/urlParameterHandler";
import { DURATION } from "../config/constants";

export const TASK_ID_GithubWatcherEasy = "github-watcher-easy";

const GithubWatcherEasy = () => {
  // Parse URL parameters manually (don't clean yet)
  const urlParams = new URLSearchParams(window.location.search);
  const duration = parseInt(urlParams.get('duration') || DURATION.DEFAULT.toString(), 10);
  const showHints = urlParams.get('hints') === 'true';
  
  // Validate duration parameter
  const taskDuration = (duration >= 1 && duration <= 86400) ? duration : DURATION.DEFAULT;
  
  // Check if validation failed and emit error for toast
  useEffect(() => {
    if (urlParams.has('duration') && taskDuration !== duration) {
      // Validation failed, emit error for toast
      const errors = [{
        parameter: 'duration',
        providedValue: urlParams.get('duration') || '',
        defaultUsed: DURATION.DEFAULT,
        reason: duration < 1 ? 'Value must be at least 1' : 
                duration > 86400 ? 'Value must be at most 86,400' :
                isNaN(duration) ? 'Value must be a valid number' : 'Invalid value'
      }];
      
      // Use the existing validation error system
      setTimeout(() => {
        URLParameterHandler.emitValidationError(errors);
      }, 100);
    }
  }, []); // Run once on mount
  
  // Create params object for shouldResetState check
  const params = { duration: taskDuration, hasAnyParams: urlParams.has('duration') };

  // Initialize state from localStorage or defaults
  const initializeState = () => {
    const savedState = TaskStateManager.loadState(TASK_ID_GithubWatcherEasy);
    
    // Check if we should reset state based on parameter changes
    if (URLParameterHandler.shouldResetState(TASK_ID_GithubWatcherEasy, savedState, params)) {
      TaskStateManager.clearState(TASK_ID_GithubWatcherEasy);
      
      const now = Date.now();
      const initialState = {
        startTime: now,
        duration: taskDuration,
        stars: 3,
        showPassword: false,
        tenKReached: false,
        staticPassword: generateParameterPassword(TASK_ID_GithubWatcherEasy, taskDuration)
      };
      
      TaskStateManager.saveState(TASK_ID_GithubWatcherEasy, initialState);
      return initialState;
    }
    
    if (savedState) {
      // Resume from saved state with proper type casting
      const savedDuration = (savedState.duration as number) || taskDuration;
      
      return {
        startTime: savedState.startTime as number,
        duration: savedDuration,
        stars: (savedState.stars as number) || 3,
        showPassword: (savedState.showPassword as boolean) || false,
        tenKReached: (savedState.tenKReached as boolean) || false,
        staticPassword: generateParameterPassword(TASK_ID_GithubWatcherEasy, savedDuration)
      };
    } else {
      // Fresh start - same as reset case
      const now = Date.now();
      const initialState = {
        startTime: now,
        duration: taskDuration,
        stars: 3,
        showPassword: false,
        tenKReached: false,
        staticPassword: generateParameterPassword(TASK_ID_GithubWatcherEasy, taskDuration)
      };
      
      TaskStateManager.saveState(TASK_ID_GithubWatcherEasy, initialState);
      return initialState;
    }
  };

  const initialState = initializeState();
  
  // Clean URL after state is initialized
  useEffect(() => {
    if (params.hasAnyParams) {
      const cleanUrl = window.location.pathname;
      window.history.replaceState({}, '', cleanUrl);
    }
  }, []);
  
  const [startTime] = useState(initialState.startTime);
  const [githubDuration] = useState(initialState.duration);
  const [stars, setStars] = useState(initialState.stars);
  const [showPassword, setShowPassword] = useState(initialState.showPassword);
  const [tenKReached, setTenKReached] = useState(initialState.tenKReached || false);
  const [staticPassword, setStaticPassword] = useState(initialState.staticPassword || "");
  const [currentTime, setCurrentTime] = useState(Date.now());
  const timerRef = useRef<number | null>(null);
  const { recordSuccess } = useTaskAnalytics(TASK_ID_GithubWatcherEasy);
  
  // Record success if resuming to an already completed state
  useEffect(() => {
    if (initialState.tenKReached && initialState.showPassword) {
      recordSuccess();
    }
  }, [initialState.tenKReached, initialState.showPassword, recordSuccess]);

  // Update current time every second for live elapsed time display
  useEffect(() => {
    timerRef.current = window.setInterval(() => {
      setCurrentTime(Date.now());
    }, 1000);

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, []);

  // S-curve function for star growth over configurable duration
  const calculateStars = (elapsedSeconds: number) => {
    const totalTime = githubDuration;
    const minStars = 3;
    const maxStars = 10000;
    
    // Handle edge cases
    if (elapsedSeconds <= 0) return minStars;
    if (elapsedSeconds >= totalTime) return maxStars;
    
    // Sigmoid function parameters - calibrated to reach 10k at totalTime
    const k = 8 / totalTime; // Steepness scaled to duration
    const midPoint = totalTime * 0.7; // 70% through duration for realistic S-curve
    
    // Normalize time
    const normalizedTime = k * (elapsedSeconds - midPoint);
    
    // Sigmoid function: 1 / (1 + e^(-x))
    const sigmoidValue = 1 / (1 + Math.exp(-normalizedTime));
    
    // Scale to star range
    const starCount = Math.round(minStars + (maxStars - minStars) * sigmoidValue);
    
    return Math.min(starCount, maxStars);
  };

  // Save state whenever any state variable changes
  useEffect(() => {
    const currentState = {
      startTime,
      duration: githubDuration,
      stars,
      showPassword,
      tenKReached,
      staticPassword
    };
    
    TaskStateManager.saveState(TASK_ID_GithubWatcherEasy, currentState);
  }, [startTime, githubDuration, stars, showPassword, tenKReached, staticPassword]);

  useEffect(() => {
    const interval = setInterval(() => {
      const elapsedSeconds = (Date.now() - startTime) / 1000;
      const newStars = calculateStars(elapsedSeconds);
      
      setStars(newStars);
      
      // Check if we reached 10k stars (but don't show password automatically)
      if (newStars >= 10000 && !tenKReached) {
        setTenKReached(true);
      }
      
    }, 200); // Update every 200ms for smooth animation

    return () => clearInterval(interval);
  }, [startTime, tenKReached]);

  const handleResetTask = () => {
    if (window.confirm('Are you sure you want to reset this task? This will restart the star counting from the beginning.')) {
      TaskStateManager.clearState(TASK_ID_GithubWatcherEasy);
      window.location.reload();
    }
  };

  const handleReadmeClick = () => {
    if (tenKReached && !showPassword) {
      const finalPassword = generateParameterPassword(TASK_ID_GithubWatcherEasy, githubDuration);
      setStaticPassword(finalPassword);
      setShowPassword(true);
      recordSuccess();
    }
  };

  const elapsedTime = Math.floor((currentTime - startTime) / 1000);
  const isLocalhost = window.location.hostname === 'localhost';
  const [adminConsoleEnabled, setAdminConsoleEnabled] = useState(() => {
    const stored = localStorage.getItem('adminConsoleEnabled');
    return stored === 'true';
  });

  // Listen for admin console toggle events and sync with localStorage
  useEffect(() => {
    const handleAdminConsoleToggle = (e: CustomEvent) => {
      setAdminConsoleEnabled(e.detail.enabled);
    };

    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'adminConsoleEnabled') {
        setAdminConsoleEnabled(e.newValue === 'true');
      }
    };

    // Check for updates to localStorage value periodically
    const syncWithStorage = () => {
      const currentValue = localStorage.getItem('adminConsoleEnabled') === 'true';
      setAdminConsoleEnabled(currentValue);
    };

    window.addEventListener('adminConsoleToggle', handleAdminConsoleToggle as EventListener);
    window.addEventListener('storage', handleStorageChange);
    window.addEventListener('focus', syncWithStorage);
    
    return () => {
      window.removeEventListener('adminConsoleToggle', handleAdminConsoleToggle as EventListener);
      window.removeEventListener('storage', handleStorageChange);
      window.removeEventListener('focus', syncWithStorage);
    };
  }, []);

  return (
    <div className="max-w-6xl mx-auto mt-6 bg-white min-h-screen">
      {/* Development Tools */}
      {(isLocalhost || adminConsoleEnabled) && (
        <div className="bg-gradient-to-r from-yellow-50 to-amber-50 border border-yellow-200/50 rounded-xl p-4 mb-6 shadow-sm backdrop-blur-sm">
          <div className="flex items-center justify-between text-sm">
            <div className="text-yellow-800 font-medium">
              <strong>Dev Tools:</strong> Elapsed: {elapsedTime}s | 
              Stars: {stars} | 
              Persistent: {TaskStateManager.hasState(TASK_ID_GithubWatcherEasy) ? '✅' : '❌'}
            </div>
            <button 
              onClick={handleResetTask}
              className="px-3 py-1.5 bg-gradient-to-r from-red-500 to-red-600 text-white text-xs rounded-lg hover:from-red-600 hover:to-red-700 transition-all duration-200 shadow-sm"
            >
              Reset Task
            </button>
          </div>
        </div>
      )}
      
      {/* GitHub Header */}
      <div className="border-b border-gray-200 bg-gray-50 px-6 py-4">
        <div className="flex items-center space-x-2 text-sm text-gray-600">
          <span>🏠</span>
          <span>/</span>
          <span className="text-blue-600 hover:underline cursor-pointer">drewsmith</span>
          <span>/</span>
          <span className="font-semibold text-gray-900">bbd-diagnostics</span>
        </div>
      </div>

      {/* Repository Header */}
      <div className="px-6 py-6 border-b border-gray-200">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center space-x-2 mb-2">
              <span className="text-2xl">📦</span>
              <h1 className="text-2xl font-bold text-gray-900">bbd-diagnostics</h1>
              <span className="px-2 py-1 text-xs bg-gray-100 text-gray-700 rounded border">Public</span>
            </div>
            <p className="text-gray-600 mb-4">
Brain and Blood Diagnostics platform using advanced neural networks for medical analysis and clinical decision support
            </p>
          </div>
          
          <div className="flex space-x-2">
            <button className="px-3 py-1 text-sm border border-gray-300 rounded-md hover:bg-gray-50">
              📌 Pin
            </button>
            <button className="px-3 py-1 text-sm border border-gray-300 rounded-md hover:bg-gray-50">
              👁️ Watch 8
            </button>
            <button className="px-3 py-1 text-sm border border-gray-300 rounded-md hover:bg-gray-50">
              🍴 Fork 1
            </button>
          </div>
        </div>

        {/* Repository Stats */}
        <div className="flex items-center space-x-6 text-sm text-gray-600">
          <div className="flex items-center space-x-1">
            <button className="flex items-center space-x-1 px-3 py-1 border border-gray-300 rounded-md hover:bg-gray-50">
              <span>⭐</span>
              <span>{stars.toLocaleString()}</span>
            </button>
          </div>
          <div className="flex items-center space-x-1">
            <span>🍴</span>
            <span>1</span>
          </div>
          <div className="flex items-center space-x-1">
            <span>⚠️</span>
            <span>12 issues</span>
          </div>
          <div className="flex items-center space-x-1">
            <span>👥</span>
            <span>4 contributors</span>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex">
        {/* Left Side - Code Browser */}
        <div className="flex-1 px-6 py-4">
          <div className="border border-gray-200 rounded-lg">
            {/* File Browser Header */}
            <div className="bg-gray-50 px-4 py-2 border-b border-gray-200 text-sm">
              <div className="flex items-center justify-between">
                <span className="font-medium">📁 Files</span>
                <span className="text-gray-500">Latest commit 2 hours ago</span>
              </div>
            </div>
            
            {/* File List - Only README.md */}
            <div className="divide-y divide-gray-200">
              <div 
                className="px-4 py-2 hover:bg-gray-50 flex items-center justify-between"
                onClick={handleReadmeClick}
              >
                <div className="flex items-center space-x-2">
                  <span>📄</span>
                  <span className={`text-blue-600 hover:underline cursor-pointer ${tenKReached && !showPassword ? 'animate-pulse font-bold' : ''}`}>
                    README.md
                  </span>
                </div>
                <span className="text-sm text-gray-500">1 day ago</span>
              </div>
            </div>
          </div>

          {/* README Preview */}
          <div className="mt-6 border border-gray-200 rounded-lg">
            <div 
              className={`bg-gray-50 px-4 py-2 border-b border-gray-200 cursor-pointer hover:bg-gray-100 ${tenKReached && !showPassword ? 'animate-pulse bg-blue-50' : ''}`}
              onClick={handleReadmeClick}
            >
              <span className="font-medium text-sm">📖 README.md</span>
            </div>
            <div className="p-6">
              <h2 className="text-xl font-bold mb-4">🧠 BBD Biotech</h2>
              <p className="text-gray-700 mb-4">
                Advanced diagnostic platform leveraging neural networks and machine learning for 
                brain imaging analysis and blood test interpretation.
              </p>
              <h3 className="text-lg font-semibold mb-2">✨ Features</h3>
              <ul className="list-disc list-inside text-gray-700 space-y-1">
                <li>Physics-based component positioning</li>
                <li>Blood biomarker interpretation</li>
                <li>Intuitive drag-and-drop mechanics</li>
                <li>Responsive design system</li>
                <li>TypeScript support</li>
              </ul>
            </div>
          </div>
        </div>

        {/* Right Side - Static Activity Panel */}
        <div className="w-80 bg-gray-50 px-4 py-4 border-l border-gray-200">
          <div className="mb-6">
            <h3 className="text-sm font-semibold text-gray-900 mb-3">🔥 Recent Activity</h3>
            <div className="space-y-3">
              <div className="text-sm">
                <div className="flex items-start space-x-2">
                  <div className="w-2 h-2 bg-green-500 rounded-full mt-2 flex-shrink-0"></div>
                  <div>
                    <p className="text-gray-900 font-medium">feat: add neural network models for brain imaging</p>
                    <p className="text-gray-500 text-xs">
                      by <span className="font-medium">sarah-dev</span> • 2 minutes ago
                    </p>
                  </div>
                </div>
              </div>
              <div className="text-sm">
                <div className="flex items-start space-x-2">
                  <div className="w-2 h-2 bg-green-500 rounded-full mt-2 flex-shrink-0"></div>
                  <div>
                    <p className="text-gray-900 font-medium">fix: resolve blood analysis calibration issues</p>
                    <p className="text-gray-500 text-xs">
                      by <span className="font-medium">simon-miller</span> • 8 minutes ago
                    </p>
                  </div>
                </div>
              </div>
              <div className="text-sm">
                <div className="flex items-start space-x-2">
                  <div className="w-2 h-2 bg-green-500 rounded-full mt-2 flex-shrink-0"></div>
                  <div>
                    <p className="text-gray-900 font-medium">docs: update diagnostic API documentation</p>
                    <p className="text-gray-500 text-xs">
                      by <span className="font-medium">justin-ojah</span> • 15 minutes ago
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="mb-6">
            <h3 className="text-sm font-semibold text-gray-900 mb-3">📊 Insights</h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-600">Commits this month</span>
                <span className="font-medium">47</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Code frequency</span>
                <span className="text-green-600">↗️ +15%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Languages</span>
                <span className="font-medium">TS, CSS, MD</span>
              </div>
            </div>
          </div>

          <div>
            <h3 className="text-sm font-semibold text-gray-900 mb-3">🏷️ Releases</h3>
            <div className="text-sm text-gray-600">
              <div className="flex items-center space-x-2 mb-2">
                <span className="w-2 h-2 bg-blue-500 rounded-full"></span>
                <span>v2.1.0 - Latest</span>
              </div>
              <p className="text-xs text-gray-500 ml-4">
                Released 3 days ago
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* README Update Notice */}
      {showPassword && (
        <div className="fixed top-4 right-4 bg-white border-l-4 border-green-500 p-4 rounded-lg shadow-lg max-w-sm z-50">
          <div className="flex items-start space-x-3">
            <div className="text-green-500 text-xl">📝</div>
            <div>
              <h3 className="font-semibold text-gray-900 mb-1">README Updated!</h3>
              <p className="text-sm text-gray-600 mb-2">
                The repository reached 10k stars. README update code:
              </p>
              <code className="text-xs font-mono bg-gray-100 px-2 py-1 rounded block">
                {staticPassword || generateParameterPassword(TASK_ID_GithubWatcherEasy, githubDuration)}
              </code>
            </div>
          </div>
        </div>
      )}

      {/* Technical Details */}
      {showHints && (
        <div className="bg-gray-900 text-green-400 rounded-lg p-6 mt-6 border-2 border-green-500 font-mono">
          <h3 className="font-bold text-green-300 mb-3 text-lg">🛠️ TECHNICAL SPECIFICATIONS</h3>
          <div className="text-sm space-y-2">
            <p><strong className="text-yellow-400">🎯 Status Element:</strong> <code className="bg-gray-700 px-2 py-1 rounded">#github-status</code></p>
            <p><strong className="text-yellow-400">✅ Completion State:</strong> <code className="bg-gray-700 px-2 py-1 rounded">data-state="completed"</code></p>
            <p><strong className="text-yellow-400">🔓 Code Element:</strong> <code className="bg-gray-700 px-2 py-1 rounded">#github-code</code></p>
            <p><strong className="text-yellow-400">⏱️ Timer:</strong> {githubDuration} seconds ({Math.floor(githubDuration / 60)}:{(githubDuration % 60).toString().padStart(2, '0')}) to reach 10k stars</p>
          </div>
        </div>
      )}
    </div>
  );
};

export default GithubWatcherEasy;