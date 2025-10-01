import { useState, useEffect } from "react";
import { useTaskAnalytics } from "../utils/useTaskAnalytics";
import { TaskStateManager } from "../utils/TaskStateManager";
import { generateParameterPassword } from "../utils/parameterPassword";
import { URLParameterHandler } from "../utils/urlParameterHandler";
import { DURATION, TIMEOUT, COMMON } from "../config/constants";

export const TASK_ID_NewsCheckerMedium = "news-checker-medium";

const NewsCheckerMedium = () => {
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
  
  // Create params object for shouldResetState check
  const params = { duration: taskDuration, hasAnyParams: urlParams.has('duration') };

  const NEWSPAPER_COUNT = 8;

  // Initialize state from localStorage or defaults
  const initializeState = () => {
    const savedState = TaskStateManager.loadState(TASK_ID_NewsCheckerMedium);
    
    // Check if we should reset state based on parameter changes
    if (URLParameterHandler.shouldResetState(TASK_ID_NewsCheckerMedium, savedState, params)) {
      TaskStateManager.clearState(TASK_ID_NewsCheckerMedium);
      
      const now = Date.now();
      const initialState = {
        startTime: now,
        duration: taskDuration,
        showPassword: false,
        checkedStories: [],
        staticPassword: generateParameterPassword(TASK_ID_NewsCheckerMedium, taskDuration),
        showFriendRequest: false,
        tickerPosition: COMMON.TICKER_START_POS
      };
      
      TaskStateManager.saveState(TASK_ID_NewsCheckerMedium, initialState);
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
        staticPassword: generateParameterPassword(TASK_ID_NewsCheckerMedium, savedDuration),
        showFriendRequest: (savedState.showFriendRequest as boolean) || false,
        tickerPosition: (savedState.tickerPosition as number) || COMMON.TICKER_START_POS
      };
    } else {
      // Fresh start - use default duration
      const now = Date.now();
      const initialState = {
        startTime: now,
        duration: taskDuration,
        showPassword: false,
        checkedStories: [],
        staticPassword: generateParameterPassword(TASK_ID_NewsCheckerMedium, taskDuration),
        showFriendRequest: false,
        tickerPosition: COMMON.TICKER_START_POS
      };
      
      TaskStateManager.saveState(TASK_ID_NewsCheckerMedium, initialState);
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
      return NEWSPAPER_COUNT - 1; // Target is the last newspaper (index 7)
    }
    
    // For regular newspapers (0-6), calculate based on interval
    let newsIndex = 0;
    for (let i = 0; i < NEWSPAPER_COUNT - 1; i++) { // Only loop through regular newspapers (0-6)
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
  const [showFriendRequest, setShowFriendRequest] = useState(initialState.showFriendRequest);
  const [tickerPosition, setTickerPosition] = useState(initialState.tickerPosition);
  const { recordSuccess } = useTaskAnalytics(TASK_ID_NewsCheckerMedium);

  // Calculate flip interval based on the actual duration being used
  const flipInterval = Math.max(1, Math.floor(newsDuration / NEWSPAPER_COUNT)); // in seconds
  
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
    }, TIMEOUT.SHORT);

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
      title: "Hardware Weekly",
      headline: "New Magnetic Storage Drives Hit Market",
      subheadline: "Traditional magnetic technology shows 40% speed improvement",
      image: "📰",
      isMagneticDistractor: true
    },
    {
      title: "Innovation Gazette",
      headline: "Smart Home UI Gets Major Update",
      subheadline: "Interface improvements focus on user experience design",
      image: "📰",
      isUIDistractor: true
    },
    {
      title: "Future Times",
      headline: "Delivery Drones Learn to Ring Doorbells",
      subheadline: "Amazon's latest update includes polite door etiquette",
      image: "📰"
    },
    {
      title: "Business Daily",
      headline: "Startup Raises $50M for Magnetic Levitation",
      subheadline: "Transportation company focuses on magnetic rail technology",
      image: "📰",
      isMagneticDistractor: true
    },
    {
      title: "Design Trends",
      headline: "UI/UX Trends Reshape Digital Interfaces",
      subheadline: "Modern interface design patterns gain popularity across platforms",
      image: "📰",
      isUIDistractor: true
    },
    {
      title: "Research Herald",
      headline: "Medical Breakthrough in Memory Treatment",
      subheadline: "New FDA-approved therapy enables significant cognitive recovery in Alzheimer's patients",
      image: "📰",
      isAlzheimersTreatment: true
    }
  ];

  // Save state whenever any state variable changes
  useEffect(() => {
    const currentState = {
      startTime,
      duration: newsDuration,
      showPassword,
      checkedStories,
      staticPassword,
      showFriendRequest,
      tickerPosition
    };
    
    TaskStateManager.saveState(TASK_ID_NewsCheckerMedium, currentState);
  }, [startTime, newsDuration, showPassword, checkedStories, staticPassword, showFriendRequest, tickerPosition]);

  // Record success if resuming to an already completed state
  useEffect(() => {
    if (initialState.showPassword) {
      recordSuccess();
    }
  }, [initialState.showPassword, recordSuccess]);

  // Duration-based newspaper scheduling (Medium mode - stops at target)
  useEffect(() => {
    // Don't schedule any new newspapers if target has already been found
    if (showPassword) return;
    
    const elapsedSeconds = (Date.now() - startTime) / 1000;
    const timeouts: NodeJS.Timeout[] = [];
    
    // Determine which newspaper should be showing based on elapsed time
    let targetNewsIndex = 0;
    for (let i = 0; i < NEWSPAPER_COUNT; i++) {
      const newspaperShouldAppearAt = i * flipInterval; // in seconds
      if (elapsedSeconds >= newspaperShouldAppearAt) {
        targetNewsIndex = i;
      }
    }
    
    // If we're past the duration, show the target (last) newspaper
    if (elapsedSeconds >= newsDuration) {
      targetNewsIndex = NEWSPAPER_COUNT - 1; // Target is the last newspaper (index 7)
    }
    
    // Update to the correct newspaper if different from current
    if (targetNewsIndex !== currentNewsIndex) {
      setCurrentNewsIndex(targetNewsIndex);
    }
    
    // Schedule future newspaper changes (only if we haven't reached the target)
    if (targetNewsIndex < NEWSPAPER_COUNT - 1) {
      for (let i = targetNewsIndex + 1; i < NEWSPAPER_COUNT; i++) {
        const newspaperShouldAppearAt = i === NEWSPAPER_COUNT - 1 ? newsDuration : i * flipInterval;
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
    }
    
    return () => {
      timeouts.forEach(timeout => clearTimeout(timeout));
    };
  }, [startTime, newsDuration, flipInterval, currentNewsIndex, showPassword]);

  // Moving news ticker
  useEffect(() => {
    const ticker = setInterval(() => {
      setTickerPosition((prev) => {
        if (prev <= COMMON.TICKER_RESET_POS) return COMMON.TICKER_START_POS;
        return prev - 0.5;
      });
    }, 50);

    return () => clearInterval(ticker);
  }, []);

  // Friend request popup timer
  useEffect(() => {
    const friendTimer = setInterval(() => {
      setShowFriendRequest(true);
      setTimeout(() => {
        setShowFriendRequest(false);
      }, TIMEOUT.TICKER_ANIMATION);
    }, 45000); // Show every 45 seconds

    return () => clearInterval(friendTimer);
  }, []);

  const handleNewsClick = () => {
    const currentStory = newsStories[currentNewsIndex];
    
    // Track clicked stories
    if (!checkedStories.includes(currentNewsIndex)) {
      setCheckedStories((prev) => [...prev, currentNewsIndex]);
    }
    
    if (currentStory.isAlzheimersTreatment) {
      const finalPassword = generateParameterPassword(TASK_ID_NewsCheckerMedium, newsDuration);
      setStaticPassword(finalPassword);
      setShowPassword(true);
      recordSuccess();
    }
  };

  const elapsedTime = Math.floor((currentTime - startTime) / COMMON.MILLISECONDS_PER_SECOND);
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
              Persistent: {TaskStateManager.hasState(TASK_ID_NewsCheckerMedium) ? '✅' : '❌'}
            </div>
            <button 
              onClick={() => {
                if (window.confirm('Are you sure you want to reset this task? This will restart the news cycle from the beginning.')) {
                  TaskStateManager.clearState(TASK_ID_NewsCheckerMedium);
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

      {/* Friend Request Popup */}
      {showFriendRequest && (
        <div className="fixed top-4 right-4 bg-blue-500 text-white p-4 rounded-lg shadow-lg z-50 max-w-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-semibold">👥 Sarah Chen wants to connect</p>
              <p className="text-sm opacity-90">Medical Researcher at Johns Hopkins</p>
            </div>
            <button 
              onClick={() => setShowFriendRequest(false)}
              className="ml-4 text-white hover:text-gray-200"
            >
              ✕
            </button>
          </div>
          <div className="mt-2 space-x-2">
            <button className="bg-white text-blue-500 px-3 py-1 rounded text-sm">Accept</button>
            <button className="bg-blue-600 text-white px-3 py-1 rounded text-sm">Ignore</button>
          </div>
        </div>
      )}
      
      {/* Moving News Ticker */}
      <div className="bg-red-600 text-white py-2 mb-6 overflow-hidden">
        <div 
          className="whitespace-nowrap transition-transform duration-75"
          style={{ transform: `translateX(${tickerPosition}%)` }}
        >
          <span className="font-bold">BREAKING NEWS:</span> Market updates • Weather alerts • Sports scores • Tech developments • Global events
        </div>
      </div>

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
                    Latest Technology News • Market Analysis • Breaking Updates
                  </div>
                </div>
              </div>

              {/* Main Headlines Section */}
              <div className="grid grid-cols-2 gap-8">
                {/* Left Column - Main Story */}
                <div>
                  <h3 className="text-2xl font-bold font-serif leading-tight mb-3 text-black">
                    {currentStory.headline}
                  </h3>
                  <p className="text-gray-800 text-base font-serif leading-relaxed mb-4">
                    {currentStory.subheadline}
                  </p>
                  
                  {/* Fake article text */}
                  <div className="space-y-2 text-xs text-gray-700 font-serif leading-relaxed">
                    <p>In a groundbreaking development that has captured the attention of industry experts worldwide, researchers have made significant strides in understanding the underlying mechanisms that drive innovation in modern technology sectors.</p>
                    <p>The implications of these findings extend far beyond initial expectations, with potential applications spanning multiple industries and creating new opportunities for collaboration between different sectors.</p>
                    <p>According to leading scientists, this breakthrough represents a fundamental shift in how we approach complex problems and could reshape our understanding of core principles.</p>
                  </div>
                </div>

                {/* Right Column - Secondary Stories */}
                <div>
                  <div className="border-l-2 border-gray-300 pl-6">
                    <h4 className="text-lg font-bold font-serif mb-2">Tech Updates</h4>
                    <div className="space-y-4 text-xs text-gray-600 font-serif">
                      <div>
                        <h5 className="font-semibold mb-1">🔧 Framework News</h5>
                        <p>New interface development tools are changing how developers approach user experience design across multiple platforms and devices.</p>
                      </div>
                      <div>
                        <h5 className="font-semibold mb-1">📊 Market Analysis</h5>
                        <p>Technology stocks continue to show resilience amid changing market conditions, with interface and UI companies leading growth.</p>
                      </div>
                      <div>
                        <h5 className="font-semibold mb-1">🚀 Innovation Hub</h5>
                        <p>Research institutions announce collaborative projects focusing on next-generation magnetic technologies and smart systems.</p>
                      </div>
                      <div>
                        <h5 className="font-semibold mb-1">⚡ Quick Updates</h5>
                        <p>Various companies announce partnerships in the interface design space, bringing new capabilities to development teams worldwide.</p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* NO PAGE INDICATORS IN MEDIUM MODE */}
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

export default NewsCheckerMedium;