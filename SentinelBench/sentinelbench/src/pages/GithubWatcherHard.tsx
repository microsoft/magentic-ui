import { useState, useEffect, useRef } from "react";
import { useTaskAnalytics } from "../utils/useTaskAnalytics";
import { TaskStateManager } from "../utils/TaskStateManager";
import { generateParameterPassword } from "../utils/parameterPassword";
import { URLParameterHandler } from "../utils/urlParameterHandler";
import { DURATION } from "../config/constants";

export const TASK_ID_GithubWatcherHard = "github-watcher-hard";

const GithubWatcherHard = () => {
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
    const savedState = TaskStateManager.loadState(TASK_ID_GithubWatcherHard);
    
    // Check if we should reset state based on parameter changes
    if (URLParameterHandler.shouldResetState(TASK_ID_GithubWatcherHard, savedState, params)) {
      TaskStateManager.clearState(TASK_ID_GithubWatcherHard);
      
      const now = Date.now();
      const initialState = {
        startTime: now,
        duration: taskDuration,
        stars: 3,
        forks: 1,
        issues: 12,
        contributors: 4,
        watchers: 8,
        pullRequests: 3,
        showPassword: false,
        tenKReached: false,
        currentCommitIndex: 0,
        staticPassword: generateParameterPassword(TASK_ID_GithubWatcherHard, taskDuration),
        currentFolderPath: "",
        showFakeMilestone: false,
        showPopup: false,
        popupType: "",
        layoutShift: false
      };
      
      TaskStateManager.saveState(TASK_ID_GithubWatcherHard, initialState);
      return initialState;
    }
    
    if (savedState) {
      // Resume from saved state with proper type casting
      const savedDuration = (savedState.duration as number) || taskDuration;
      
      return {
        startTime: savedState.startTime as number,
        duration: savedDuration,
        stars: (savedState.stars as number) || 3,
        forks: (savedState.forks as number) || 1,
        issues: (savedState.issues as number) || 12,
        contributors: (savedState.contributors as number) || 4,
        watchers: (savedState.watchers as number) || 8,
        pullRequests: (savedState.pullRequests as number) || 3,
        showPassword: (savedState.showPassword as boolean) || false,
        tenKReached: (savedState.tenKReached as boolean) || false,
        currentCommitIndex: (savedState.currentCommitIndex as number) || 0,
        staticPassword: generateParameterPassword(TASK_ID_GithubWatcherHard, savedDuration),
        currentFolderPath: (savedState.currentFolderPath as string) || "",
        showFakeMilestone: (savedState.showFakeMilestone as boolean) || false,
        showPopup: (savedState.showPopup as boolean) || false,
        popupType: (savedState.popupType as string) || "",
        layoutShift: (savedState.layoutShift as boolean) || false
      };
    } else {
      // Fresh start - same as reset case
      const now = Date.now();
      const initialState = {
        startTime: now,
        duration: taskDuration,
        stars: 3,
        forks: 1,
        issues: 12,
        contributors: 4,
        watchers: 8,
        pullRequests: 3,
        showPassword: false,
        tenKReached: false,
        currentCommitIndex: 0,
        staticPassword: generateParameterPassword(TASK_ID_GithubWatcherHard, taskDuration),
        currentFolderPath: "",
        showFakeMilestone: false,
        showPopup: false,
        popupType: "",
        layoutShift: false
      };
      
      TaskStateManager.saveState(TASK_ID_GithubWatcherHard, initialState);
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
  const [forks, setForks] = useState(initialState.forks);
  const [issues, setIssues] = useState(initialState.issues);
  const [contributors, setContributors] = useState(initialState.contributors);
  const [watchers, setWatchers] = useState(initialState.watchers);
  const [pullRequests, setPullRequests] = useState(initialState.pullRequests);
  const [showPassword, setShowPassword] = useState(initialState.showPassword);
  const [tenKReached, setTenKReached] = useState(initialState.tenKReached || false);
  const [currentCommitIndex, setCurrentCommitIndex] = useState(initialState.currentCommitIndex);
  const [staticPassword, setStaticPassword] = useState(initialState.staticPassword || "");
  const [currentTime, setCurrentTime] = useState(Date.now());
  const [currentFolderPath, setCurrentFolderPath] = useState(initialState.currentFolderPath || "");
  const [showFakeMilestone, setShowFakeMilestone] = useState(initialState.showFakeMilestone || false);
  const [showPopup, setShowPopup] = useState(initialState.showPopup || false);
  const [popupType, setPopupType] = useState(initialState.popupType || "");
  const [layoutShift, setLayoutShift] = useState(initialState.layoutShift || false);
  const timerRef = useRef<number | null>(null);
  const { recordSuccess } = useTaskAnalytics(TASK_ID_GithubWatcherHard);
  
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

  const commits = [
    { message: "feat: add neural network models for brain imaging", author: "sarah-dev", time: "2 minutes ago" },
    { message: "fix: resolve blood analysis calibration issues", author: "simon-miller", time: "8 minutes ago" },
    { message: "docs: update diagnostic API documentation", author: "justin-ojah", time: "15 minutes ago" },
    { message: "refactor: optimize neural network inference", author: "raul-valle", time: "23 minutes ago" },
    { message: "feat: add MRI scan preprocessing pipeline", author: "jenny-imaging", time: "31 minutes ago" },
    { message: "test: add unit tests for diagnostic algorithms", author: "simon-miller", time: "42 minutes ago" },
    { message: "ci: update ML model deployment pipeline", author: "devops-bot", time: "1 hour ago" },
    { message: "security: implement HIPAA compliance checks", author: "justin-ojah", time: "2 hours ago" },
    { message: "perf: reduce model inference time by 15%", author: "raul-valle", time: "3 hours ago" },
    { message: "feat: implement blood biomarker analysis", author: "simon-miller", time: "4 hours ago" }
  ];

  // Expanded file structure with nested README
  const fileStructure = {
    "": [
      { name: ".github", type: "folder", updated: "3 days ago" },
      { name: "models", type: "folder", updated: "2 hours ago" },
      { name: "data", type: "folder", updated: "1 day ago" },
      { name: "analysis", type: "folder", updated: "5 hours ago" },
      { name: "tests", type: "folder", updated: "1 hour ago" },
      { name: "scripts", type: "folder", updated: "2 days ago" },
      { name: "datasets", type: "folder", updated: "1 week ago" },
      { name: "build", type: "folder", updated: "30 minutes ago" },
      { name: ".gitignore", type: "file", updated: "1 week ago" },
      { name: "requirements.txt", type: "file", updated: "2 hours ago" },
      { name: "setup.py", type: "file", updated: "3 days ago" },
      { name: "config.yaml", type: "file", updated: "1 day ago" },
      { name: "LICENSE", type: "file", updated: "2 weeks ago" },
      { name: "CONTRIBUTING.md", type: "file", updated: "5 days ago" },
      { name: "CHANGELOG.md", type: "file", updated: "3 days ago" }
    ],
    "models": [
      { name: "brain_imaging", type: "folder", updated: "2 days ago" },
      { name: "blood_analysis", type: "folder", updated: "1 day ago" },
      { name: "neural_networks", type: "folder", updated: "3 days ago" },
      { name: "model_config.py", type: "file", updated: "1 week ago" },
      { name: "training.py", type: "file", updated: "2 days ago" }
    ],
    "models/brain_imaging": [
      { name: "mri_analysis", type: "folder", updated: "1 day ago" },
      { name: "ct_processing", type: "folder", updated: "3 days ago" },
      { name: "diagnostics", type: "folder", updated: "1 week ago" },
      { name: "preprocessing.py", type: "file", updated: "2 days ago" }
    ],
    "models/brain_imaging/diagnostics": [
      { name: "alzheimer_detection.py", type: "file", updated: "2 days ago" },
      { name: "stroke_analysis.py", type: "file", updated: "1 day ago" },
      { name: "README.md", type: "file", updated: "1 day ago" }, // This is the real one!
      { name: "model_weights.pkl", type: "file", updated: "3 days ago" }
    ]
  };

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
      stars,
      forks,
      issues,
      contributors,
      watchers,
      pullRequests,
      showPassword,
      tenKReached,
      currentCommitIndex,
      staticPassword,
      currentFolderPath,
      showFakeMilestone,
      showPopup,
      popupType,
      layoutShift,
      duration: githubDuration
    };
    
    TaskStateManager.saveState(TASK_ID_GithubWatcherHard, currentState);
  }, [startTime, stars, forks, issues, contributors, watchers, pullRequests, showPassword, tenKReached, currentCommitIndex, staticPassword, currentFolderPath, showFakeMilestone, showPopup, popupType, layoutShift, githubDuration]);

  useEffect(() => {
    const interval = setInterval(() => {
      const elapsedSeconds = (Date.now() - startTime) / 1000;
      const newStars = calculateStars(elapsedSeconds);
      
      setStars(newStars);
      
      // Check if we reached 10k stars (but don't show password automatically)
      if (newStars >= 10000 && !tenKReached) {
        setTenKReached(true);
      }
      
      // Show fake milestone celebrations
      if (newStars >= 5000 && newStars < 5100 && !showFakeMilestone) {
        setShowFakeMilestone(true);
        setPopupType("5k");
        setShowPopup(true);
        setTimeout(() => setShowPopup(false), 5000);
      }
      if (newStars >= 7000 && newStars < 7100 && showFakeMilestone) {
        setPopupType("7k");
        setShowPopup(true);
        setTimeout(() => setShowPopup(false), 5000);
      }
      
      // Rapid updates for all metrics (every 2-3 seconds)
      if (Math.floor(elapsedSeconds * 3) % 7 === 0) {
        setForks((prev: number) => prev + Math.floor(Math.random() * 3));
      }
      
      if (Math.floor(elapsedSeconds * 3) % 8 === 0) {
        setIssues((prev: number) => prev + Math.floor(Math.random() * 4) - 1);
      }
      
      if (Math.floor(elapsedSeconds * 3) % 12 === 0) {
        setContributors((prev: number) => prev + (Math.random() > 0.6 ? 1 : 0));
      }
      
      if (Math.floor(elapsedSeconds * 3) % 6 === 0) {
        setWatchers((prev: number) => prev + Math.floor(Math.random() * 3));
      }
      
      if (Math.floor(elapsedSeconds * 3) % 9 === 0) {
        setPullRequests((prev: number) => prev + Math.floor(Math.random() * 2));
      }
      
      // Rotate commits every 5 seconds (not 20)
      if (Math.floor(elapsedSeconds * 3) % 15 === 0) {
        setCurrentCommitIndex((prev: number) => (prev + 1) % commits.length);
      }
      
      // Random popup distractions
      if (Math.floor(elapsedSeconds) % 25 === 0 && Math.random() > 0.7) {
        const popups = ["security", "release", "ci-failure", "merge-conflict"];
        setPopupType(popups[Math.floor(Math.random() * popups.length)]);
        setShowPopup(true);
        setTimeout(() => setShowPopup(false), 3000);
      }
      
      // Layout shifts occasionally
      if (Math.floor(elapsedSeconds) % 30 === 0 && Math.random() > 0.8) {
        setLayoutShift(true);
        setTimeout(() => setLayoutShift(false), 1000);
      }
      
    }, 200); // Update every 200ms for smooth animation

    return () => clearInterval(interval);
  }, [startTime, tenKReached, showFakeMilestone]);

  const handleResetTask = () => {
    if (window.confirm('Are you sure you want to reset this task? This will restart the star counting from the beginning.')) {
      TaskStateManager.clearState(TASK_ID_GithubWatcherHard);
      window.location.reload();
    }
  };

  const handleFileClick = (fileName: string, isFolder: boolean) => {
    if (isFolder) {
      const newPath = currentFolderPath ? `${currentFolderPath}/${fileName}` : fileName;
      setCurrentFolderPath(newPath);
    } else if (fileName === 'README.md' && currentFolderPath === 'docs/guides/getting-started') {
      // This is the real README that works!
      if (tenKReached && !showPassword) {
        const finalPassword = generateParameterPassword(TASK_ID_GithubWatcherHard, githubDuration);
        setStaticPassword(finalPassword);
        setShowPassword(true);
        recordSuccess();
      }
    }
    // Other README files do nothing (decoys)
  };

  const handleBreadcrumbClick = (pathIndex: number) => {
    const pathParts = currentFolderPath.split('/');
    const newPath = pathParts.slice(0, pathIndex + 1).join('/');
    setCurrentFolderPath(newPath);
  };

  const getCurrentFiles = () => {
    return fileStructure[currentFolderPath as keyof typeof fileStructure] || [];
  };

  const getBreadcrumbs = () => {
    if (!currentFolderPath) return [{ name: 'bbd-diagnostics', path: '' }];
    
    const parts = currentFolderPath.split('/');
    const breadcrumbs = [{ name: 'bbd-diagnostics', path: '' }];
    
    parts.forEach((part, index) => {
      const path = parts.slice(0, index + 1).join('/');
      breadcrumbs.push({ name: part, path });
    });
    
    return breadcrumbs;
  };

  const dismissPopup = () => {
    setShowPopup(false);
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
              Path: {currentFolderPath || 'root'} |
              Persistent: {TaskStateManager.hasState(TASK_ID_GithubWatcherHard) ? '✅' : '❌'}
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
      <div className={`px-6 py-6 border-b border-gray-200 transition-all duration-500 ${layoutShift ? 'transform translate-x-2' : ''}`}>
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
              👁️ Watch {watchers}
            </button>
            <button className="px-3 py-1 text-sm border border-gray-300 rounded-md hover:bg-gray-50">
              🍴 Fork {forks}
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
            <span>{forks}</span>
          </div>
          <div className="flex items-center space-x-1">
            <span>⚠️</span>
            <span>{issues} issues</span>
          </div>
          <div className="flex items-center space-x-1">
            <span>🔄</span>
            <span>{pullRequests} pull requests</span>
          </div>
          <div className="flex items-center space-x-1">
            <span>👥</span>
            <span>{contributors} contributors</span>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex">
        {/* Left Side - Code Browser */}
        <div className="flex-1 px-6 py-4">
          <div className="border border-gray-200 rounded-lg">
            {/* File Browser Header with Breadcrumbs */}
            <div className="bg-gray-50 px-4 py-2 border-b border-gray-200 text-sm">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-1">
                  <span className="font-medium">📁</span>
                  {getBreadcrumbs().map((crumb, index) => (
                    <span key={index} className="flex items-center space-x-1">
                      <span 
                        className="text-blue-600 hover:underline cursor-pointer"
                        onClick={() => handleBreadcrumbClick(index - 1)}
                      >
                        {crumb.name}
                      </span>
                      {index < getBreadcrumbs().length - 1 && <span>/</span>}
                    </span>
                  ))}
                </div>
                <span className="text-gray-500">Latest commit 2 hours ago</span>
              </div>
            </div>
            
            {/* File List */}
            <div className="divide-y divide-gray-200">
              {getCurrentFiles().map((file, index) => (
                <div 
                  key={index} 
                  className="px-4 py-2 hover:bg-gray-50 flex items-center justify-between cursor-pointer"
                  onClick={() => handleFileClick(file.name, file.type === 'folder')}
                >
                  <div className="flex items-center space-x-2">
                    <span>{file.type === 'folder' ? '📁' : '📄'}</span>
                    <span className="text-blue-600 hover:underline">
                      {file.name}
                    </span>
                  </div>
                  <span className="text-sm text-gray-500">{file.updated}</span>
                </div>
              ))}
            </div>
          </div>

          {/* README Preview - only show in root or if we're looking at the real README */}
          {(!currentFolderPath || (currentFolderPath === 'docs/guides/getting-started')) && (
            <div className="mt-6 border border-gray-200 rounded-lg">
              <div 
                className="bg-gray-50 px-4 py-2 border-b border-gray-200 cursor-pointer hover:bg-gray-100"
                onClick={() => {
                  if (currentFolderPath === 'docs/guides/getting-started') {
                    handleFileClick('README.md', false);
                  }
                }}
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
                  <li>Neural network brain imaging analysis</li>
                  <li>Blood biomarker interpretation</li>
                  <li>Clinical decision support</li>
                  <li>Real-time diagnostic processing</li>
                  <li>HIPAA-compliant data handling</li>
                </ul>
              </div>
            </div>
          )}
        </div>

        {/* Right Side - Chaotic Activity Panel */}
        <div className={`w-80 bg-gray-50 px-4 py-4 border-l border-gray-200 transition-all duration-500 ${layoutShift ? 'transform -translate-x-2' : ''}`}>
          <div className="mb-6">
            <h3 className="text-sm font-semibold text-gray-900 mb-3">🔥 Recent Activity</h3>
            <div className="space-y-3">
              {commits.slice(currentCommitIndex, currentCommitIndex + 4).map((commit, index) => (
                <div key={index} className="text-sm">
                  <div className="flex items-start space-x-2">
                    <div className="w-2 h-2 bg-green-500 rounded-full mt-2 flex-shrink-0"></div>
                    <div>
                      <p className="text-gray-900 font-medium">{commit.message}</p>
                      <p className="text-gray-500 text-xs">
                        by <span className="font-medium">{commit.author}</span> • {commit.time}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="mb-6">
            <h3 className="text-sm font-semibold text-gray-900 mb-3">📊 Insights</h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-600">Commits this month</span>
                <span className="font-medium">{47 + Math.floor(elapsedTime / 10)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Code frequency</span>
                <span className="text-green-600">↗️ +{15 + Math.floor(Math.random() * 10)}%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Languages</span>
                <span className="font-medium">TS, CSS, MD</span>
              </div>
            </div>
          </div>

          <div className="mb-6">
            <h3 className="text-sm font-semibold text-gray-900 mb-3">🚨 Security</h3>
            <div className="space-y-2 text-xs">
              <div className="flex items-center space-x-2 p-2 bg-red-50 rounded">
                <span className="text-red-500">⚠️</span>
                <span className="text-red-700">3 vulnerabilities found</span>
              </div>
              <div className="flex items-center space-x-2 p-2 bg-yellow-50 rounded">
                <span className="text-yellow-500">🔍</span>
                <span className="text-yellow-700">Dependency scan in progress</span>
              </div>
            </div>
          </div>

          <div>
            <h3 className="text-sm font-semibold text-gray-900 mb-3">🏷️ Releases</h3>
            <div className="text-sm text-gray-600">
              <div className="flex items-center space-x-2 mb-2">
                <span className="w-2 h-2 bg-blue-500 rounded-full"></span>
                <span>v2.1.{Math.floor(elapsedTime / 30)} - Latest</span>
              </div>
              <p className="text-xs text-gray-500 ml-4">
                Released {Math.floor(Math.random() * 5)} hours ago
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Popup Distractions */}
      {showPopup && (
        <div className="fixed top-4 right-4 bg-white border p-4 rounded-lg shadow-lg max-w-sm z-50">
          <div className="flex items-start justify-between">
            <div className="flex items-start space-x-3">
              <div className="text-xl">
                {popupType === '5k' && '🎉'}
                {popupType === '7k' && '🚀'}
                {popupType === 'security' && '🔒'}
                {popupType === 'release' && '📦'}
                {popupType === 'ci-failure' && '❌'}
                {popupType === 'merge-conflict' && '⚡'}
              </div>
              <div>
                <h3 className="font-semibold text-gray-900 mb-1">
                  {popupType === '5k' && '5K Stars Reached!'}
                  {popupType === '7k' && '7K Stars Milestone!'}
                  {popupType === 'security' && 'Security Alert'}
                  {popupType === 'release' && 'New Release Available'}
                  {popupType === 'ci-failure' && 'CI Pipeline Failed'}
                  {popupType === 'merge-conflict' && 'Merge Conflict Detected'}
                </h3>
                <p className="text-sm text-gray-600">
                  {popupType === '5k' && 'Time to update the README! Click here to celebrate.'}
                  {popupType === '7k' && 'Amazing growth! Ready for the final milestone?'}
                  {popupType === 'security' && 'Critical vulnerability detected in dependencies.'}
                  {popupType === 'release' && 'Version 2.2.0 is now available for download.'}
                  {popupType === 'ci-failure' && 'Build #447 failed. Click to view details.'}
                  {popupType === 'merge-conflict' && 'Pull request #23 has conflicts that need resolution.'}
                </p>
              </div>
            </div>
            <button 
              onClick={dismissPopup}
              className="text-gray-400 hover:text-gray-600 ml-2"
            >
              ✕
            </button>
          </div>
        </div>
      )}

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
                {staticPassword || generateParameterPassword(TASK_ID_GithubWatcherHard, githubDuration)}
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
            <p><strong className="text-yellow-400">📁 Target Path:</strong> <code className="bg-gray-700 px-2 py-1 rounded">docs/guides/getting-started/README.md</code></p>
          </div>
        </div>
      )}
    </div>
  );
};

export default GithubWatcherHard;