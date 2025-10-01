import { useState, useEffect } from "react";
import { useTaskAnalytics } from "../utils/useTaskAnalytics";
import { TaskStateManager } from "../utils/TaskStateManager";
import { generateParameterPassword } from "../utils/parameterPassword";
import { URLParameterHandler } from "../utils/urlParameterHandler";
import { DURATION } from "../config/constants";

export const TASK_ID_NewsCheckerEasy = "news-checker-easy";

const NewsCheckerEasy = () => {
  // Parse URL parameters manually (don't clean yet)
  const urlParams = new URLSearchParams(window.location.search);
  const duration = parseInt(urlParams.get('duration') || DURATION.DEFAULT.toString(), 10);
  
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
  
  // Create params object for shouldResetState check - simplified like LinkedInMonitorEasy
  const params = { duration: taskDuration, hasAnyParams: urlParams.has('duration') };

  const NEWSPAPER_COUNT = 6;

  // Initialize state from localStorage or defaults
  const initializeState = () => {
    const savedState = TaskStateManager.loadState(TASK_ID_NewsCheckerEasy);
    
    // Check if we should reset state based on parameter changes
    if (URLParameterHandler.shouldResetState(TASK_ID_NewsCheckerEasy, savedState, params)) {
      TaskStateManager.clearState(TASK_ID_NewsCheckerEasy);
      
      const now = Date.now();
      const initialState = {
        startTime: now,
        duration: taskDuration,
        showPassword: false,
        checkedStories: [],
        staticPassword: generateParameterPassword(TASK_ID_NewsCheckerEasy, taskDuration)
      };
      
      TaskStateManager.saveState(TASK_ID_NewsCheckerEasy, initialState);
      return initialState;
    }
    
    if (savedState) {
      // Resume from saved state
      const savedDuration = (savedState.duration as number) || taskDuration;
      
      return {
        startTime: savedState.startTime as number,
        duration: savedDuration,
        showPassword: savedState.showPassword === true,
        checkedStories: (savedState.checkedStories as number[]) || [],
        staticPassword: generateParameterPassword(TASK_ID_NewsCheckerEasy, savedDuration)
      };
    } else {
      // Fresh start - use default duration
      const now = Date.now();
      const initialState = {
        startTime: now,
        duration: taskDuration,
        showPassword: false,
        checkedStories: [],
        staticPassword: generateParameterPassword(TASK_ID_NewsCheckerEasy, taskDuration)
      };
      
      TaskStateManager.saveState(TASK_ID_NewsCheckerEasy, initialState);
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
  const [newsDuration] = useState(initialState.duration);
  
  // Calculate current news index based on elapsed time (not saved in state)
  const calculateCurrentNewsIndex = () => {
    const elapsedSeconds = (Date.now() - startTime) / 1000;
    const flipInterval = Math.max(1, Math.floor(newsDuration / NEWSPAPER_COUNT));
    
    // If we're past the duration, show the target (last) newspaper
    if (elapsedSeconds >= newsDuration) {
      return NEWSPAPER_COUNT - 1; // Target is the last newspaper (index 5)
    }
    
    // For regular newspapers (0-4), calculate based on interval
    let newsIndex = 0;
    for (let i = 0; i < NEWSPAPER_COUNT - 1; i++) { // Only loop through regular newspapers (0-4)
      const newspaperShouldAppearAt = i * flipInterval;
      if (elapsedSeconds >= newspaperShouldAppearAt) {
        newsIndex = i;
      }
    }
    
    return newsIndex;
  };
  
  const [currentNewsIndex, setCurrentNewsIndex] = useState(calculateCurrentNewsIndex);
  const [showPassword, setShowPassword] = useState(initialState.showPassword);
  const [checkedStories, setCheckedStories] = useState(initialState.checkedStories);
  const [staticPassword, setStaticPassword] = useState(initialState.staticPassword || "");
  const [isFlipping, setIsFlipping] = useState(false);
  const [currentTime, setCurrentTime] = useState(Date.now());
  const { recordSuccess } = useTaskAnalytics(TASK_ID_NewsCheckerEasy);

  // Calculate flip interval based on the actual duration being used
  const flipInterval = Math.max(1, Math.floor(newsDuration / NEWSPAPER_COUNT)); // in seconds
  
  // Record success if resuming to an already completed state
  useEffect(() => {
    if (initialState.showPassword) {
      recordSuccess();
    }
  }, [initialState.showPassword, recordSuccess]);

  // Save state whenever any state variable changes
  useEffect(() => {
    const currentState = {
      startTime,
      duration: newsDuration,
      showPassword,
      checkedStories,
      staticPassword
    };
    
    TaskStateManager.saveState(TASK_ID_NewsCheckerEasy, currentState);
  }, [startTime, newsDuration, showPassword, checkedStories, staticPassword]);

  // Record success if resuming to an already completed state
  useEffect(() => {
    if (initialState.showPassword) {
      recordSuccess();
    }
  }, [initialState.showPassword, recordSuccess]);

  // Update current time every second for live elapsed time display
  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(Date.now());
    }, 1000);

    return () => clearInterval(timer);
  }, []);

  const newsStories = [
    {
      title: "Tech Tribune",
      headline: "Local Cat Cafe Introduces Robot Waiters",
      subheadline: "Customers report improved service, fewer hairballs in coffee",
      image: "📰"
    },
    {
      title: "Digital Daily",
      headline: "Scientists Discover Plants Enjoy Classical Music",
      subheadline: "Mozart increases tomato yields by 23%, study finds",
      image: "📰"
    },
    {
      title: "Innovation Gazette",
      headline: "New Smartphone App Translates Baby Cries",
      subheadline: "Parents finally understand what infants really want",
      image: "📰"
    },
    {
      title: "Future Times",
      headline: "Delivery Drones Learn to Ring Doorbells",
      subheadline: "Amazon's latest update includes polite door etiquette",
      image: "📰"
    },
    {
      title: "Tech Weekly",
      headline: "Office Plants Vote for Better Wi-Fi",
      subheadline: "Ficus trees demand faster internet speeds",
      image: "📰"
    },
    {
      title: "Medical Tribune",
      headline: "FDA Approves New Alzheimer's Treatment",
      subheadline: "Breakthrough therapy shows significant cognitive improvement in clinical trials",
      image: "📰",
      isAlzheimersTreatment: true
    }
  ];

  // Record success if resuming to an already completed state
  useEffect(() => {
    if (initialState.showPassword) {
      recordSuccess();
    }
  }, [initialState.showPassword, recordSuccess]);

  // Duration-based newspaper scheduling (Easy mode - stops at target)
  useEffect(() => {
    // Don't schedule any new newspapers if target has already been found
    if (showPassword) return;
    
    const elapsedSeconds = (Date.now() - startTime) / 1000;
    const timeouts: NodeJS.Timeout[] = [];
    
    // If we're past the duration, show the target (last) newspaper
    let correctNewsIndex = 0;
    if (elapsedSeconds >= newsDuration) {
      correctNewsIndex = NEWSPAPER_COUNT - 1; // Target is the last newspaper (index 5)
    } else {
      // For regular newspapers (0-4), calculate based on interval
      for (let i = 0; i < NEWSPAPER_COUNT - 1; i++) { // Only loop through regular newspapers (0-4)
        const newspaperShouldAppearAt = i * flipInterval; // in seconds
        if (elapsedSeconds >= newspaperShouldAppearAt) {
          correctNewsIndex = i;
        }
      }
    }
    
    // Always set to the correct newspaper based on elapsed time
    if (correctNewsIndex !== currentNewsIndex) {
      setCurrentNewsIndex(correctNewsIndex);
    }
    
    // Schedule future newspaper changes
    if (correctNewsIndex < NEWSPAPER_COUNT - 1) {
      // Schedule regular newspapers (0-4) based on flip interval
      for (let i = correctNewsIndex + 1; i < NEWSPAPER_COUNT - 1; i++) {
        const newspaperShouldAppearAt = i * flipInterval;
        const timeUntilAppear = (startTime + newspaperShouldAppearAt * 1000) - Date.now();
        
        if (timeUntilAppear > 0) {
          const timeout = setTimeout(() => {
            setIsFlipping(true);
            setTimeout(() => {
              setCurrentNewsIndex(i);
              setIsFlipping(false);
            }, 300); // Flip animation duration
          }, timeUntilAppear);
          timeouts.push(timeout);
        }
      }
      
      // Schedule target newspaper (index 5) at exactly duration time
      const timeUntilTarget = (startTime + newsDuration * 1000) - Date.now();
      if (timeUntilTarget > 0) {
        const timeout = setTimeout(() => {
          setIsFlipping(true);
          setTimeout(() => {
            setCurrentNewsIndex(NEWSPAPER_COUNT - 1);
            setIsFlipping(false);
          }, 300); // Flip animation duration
        }, timeUntilTarget);
        timeouts.push(timeout);
      }
    }
    
    return () => {
      timeouts.forEach(timeout => clearTimeout(timeout));
    };
  }, [startTime, newsDuration, flipInterval, currentNewsIndex, showPassword]);

  const handleNewsClick = () => {
    const currentStory = newsStories[currentNewsIndex];
    
    // Track clicked stories
    if (!checkedStories.includes(currentNewsIndex)) {
      setCheckedStories((prev) => [...prev, currentNewsIndex]);
    }
    
    if (currentStory.isAlzheimersTreatment) {
      const finalPassword = generateParameterPassword(TASK_ID_NewsCheckerEasy, newsDuration);
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
    const handleAdminToggle = (e: CustomEvent) => {
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

    window.addEventListener('adminConsoleToggle', handleAdminToggle as EventListener);
    window.addEventListener('storage', handleStorageChange);
    
    // Sync every 2 seconds in case localStorage changes from another tab
    const interval = setInterval(syncWithStorage, 2000);

    return () => {
      window.removeEventListener('adminConsoleToggle', handleAdminToggle as EventListener);
      window.removeEventListener('storage', handleStorageChange);
      clearInterval(interval);
    };
  }, []);

  const currentStory = newsStories[currentNewsIndex];

  return (
    <div className="max-w-6xl mx-auto mt-10 p-6">
      {/* Development Tools */}
      {(isLocalhost || adminConsoleEnabled) && (
        <div className="bg-gradient-to-r from-yellow-50 to-amber-50 border border-yellow-200/50 rounded-xl p-4 mb-6 shadow-sm backdrop-blur-sm">
          <div className="flex items-center justify-between text-sm">
            <div className="text-yellow-800 font-medium">
              <strong>Dev Tools:</strong> Elapsed: {elapsedTime}s | 
              Story: {currentNewsIndex + 1}/{newsStories.length} | 
              Duration: {newsDuration}s | Flip Interval: {flipInterval}s |
              Checked: {checkedStories.length} stories |
              Persistent: {TaskStateManager.hasState(TASK_ID_NewsCheckerEasy) ? '✅' : '❌'}
            </div>
            <button 
              onClick={() => {
                if (window.confirm('Are you sure you want to reset this task? This will restart the news cycle from the beginning.')) {
                  TaskStateManager.clearState(TASK_ID_NewsCheckerEasy);
                  // Reload without any parameters to use default duration
                  window.location.href = window.location.pathname;
                }
              }}
              className="px-3 py-1.5 bg-gradient-to-r from-red-500 to-red-600 text-white text-xs rounded-lg hover:from-red-600 hover:to-red-700 transition-all duration-200 shadow-sm"
            >
              Reset Task
            </button>
          </div>
        </div>
      )}
      
      {/* Open Newspaper */}
      <div className="relative mx-auto" style={{ perspective: '1200px' }}>
        {/* Newspaper Base */}
        <div className="relative w-full max-w-4xl mx-auto bg-white shadow-2xl" style={{ transform: 'rotateX(5deg)' }}>
          
          {/* Left Page */}
          <div className="absolute left-0 top-0 w-1/2 h-full bg-white border-r-2 border-gray-300 shadow-lg"></div>
          
          {/* Right Page with flip animation */}
          <div 
            className={`w-full bg-white transition-transform duration-300 ${
              isFlipping ? 'animate-pulse' : ''
            }`}
            style={{
              transformStyle: 'preserve-3d',
              transform: isFlipping ? 'rotateY(-10deg)' : 'rotateY(0deg)',
            }}
            onClick={handleNewsClick}
          >
            {/* Newspaper Content */}
            <div className="p-8 min-h-96 cursor-pointer">
              {/* Newspaper Header */}
              <div className="border-b-4 border-black pb-4 mb-6">
                <div className="text-center">
                  <h2 className="text-3xl font-bold font-serif tracking-wider mb-2">
                    {currentStory.title}
                  </h2>
                  <div className="text-sm text-gray-500">
                    Vol. {currentNewsIndex + 1} • Today's Edition • Latest News
                  </div>
                </div>
              </div>

              {/* Main Headlines Section - Simplified to show only headline */}
              <div className="text-center py-12">
                <h3 className="text-4xl font-bold font-serif leading-tight text-black">
                  {currentStory.headline}
                </h3>
              </div>
            </div>
          </div>

          {/* Page indicator dots - ONLY IN EASY MODE */}
          <div className="absolute bottom-4 right-4 flex space-x-2">
            {newsStories.map((_, index) => (
              <div
                key={index}
                className={`w-3 h-3 rounded-full ${
                  index === currentNewsIndex ? 'bg-blue-600' : 'bg-gray-400'
                }`}
              />
            ))}
          </div>
          
          {/* Page counter - ONLY IN EASY MODE */}
          <div className="absolute bottom-4 left-4 text-sm text-gray-600 bg-white bg-opacity-75 px-2 py-1 rounded">
            Page {currentNewsIndex + 1} of {newsStories.length}
          </div>
        </div>

        {/* Newspaper Shadow */}
        <div 
          className="absolute inset-0 bg-black opacity-20 blur-lg"
          style={{ 
            transform: 'rotateX(5deg) translateY(20px) translateZ(-50px)',
            zIndex: -1 
          }}
        ></div>
      </div>

      {/* Success State */}
      {showPassword && (
        <div className="mt-6 p-4 bg-green-100 border-2 border-green-500 rounded-lg text-center">
          <h2 
            id="news-checker-status"
            data-state="found"
            className="text-xl font-bold text-green-800 mb-2"
          >
            🎉 Alzheimer's Treatment News Found!
          </h2>
          <p className="text-green-700 mb-4">
            You successfully identified the FDA Alzheimer's treatment approval!
          </p>
          <div className="bg-green-200 p-3 rounded">
            <p className="text-green-800 font-medium mb-1">Access Code:</p>
            <code 
              id="access-code"
              className="font-mono font-bold text-lg"
            >
              {staticPassword}
            </code>
          </div>
        </div>
      )}
    </div>
  );
};

export default NewsCheckerEasy;