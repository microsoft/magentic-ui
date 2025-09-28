import { useState, useEffect } from "react";
import { useTaskAnalytics } from "../utils/useTaskAnalytics";
import { TaskStateManager } from "../utils/TaskStateManager";
import { generateParameterPassword } from "../utils/parameterPassword";
import { URLParameterHandler } from "../utils/urlParameterHandler";
import { DURATION } from "../config/constants";

export const TASK_ID_NewsCheckerHard = "news-checker-hard";

const NewsCheckerHard = () => {
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

  const NEWSPAPER_COUNT = 12;

  // Initialize state from localStorage or defaults
  const initializeState = () => {
    const savedState = TaskStateManager.loadState(TASK_ID_NewsCheckerHard);
    
    // Check if we should reset state based on parameter changes
    if (URLParameterHandler.shouldResetState(TASK_ID_NewsCheckerHard, savedState, params)) {
      TaskStateManager.clearState(TASK_ID_NewsCheckerHard);
      
      const now = Date.now();
      const initialState = {
        startTime: now,
        duration: taskDuration,
        showPassword: false,
        checkedStories: [],
        staticPassword: generateParameterPassword(TASK_ID_NewsCheckerHard, taskDuration),
        showBreakingNews: false,
        showAdPopup: false,
        showVideoThumbnail: false,
        tickerPosition: 100,
        stockPrices: [
          { symbol: "BRPX", price: 384.52, change: "+2.1%" },
          { symbol: "AAPL", price: 189.43, change: "-0.8%" },
          { symbol: "GOOGL", price: 142.37, change: "+1.3%" }
        ]
      };
      
      TaskStateManager.saveState(TASK_ID_NewsCheckerHard, initialState);
      return initialState;
    }
    
    if (savedState) {
      // Resume from saved state - only restore core newspaper state
      const savedDuration = (savedState.duration as number) || taskDuration;
      
      return {
        startTime: savedState.startTime as number,
        duration: savedDuration,
        showPassword: savedState.showPassword === true,
        checkedStories: (savedState.checkedStories as number[]) || [],
        staticPassword: generateParameterPassword(TASK_ID_NewsCheckerHard, savedDuration),
        showBreakingNews: (savedState.showBreakingNews as boolean) || false,
        showAdPopup: (savedState.showAdPopup as boolean) || false,
        showVideoThumbnail: (savedState.showVideoThumbnail as boolean) || false,
        tickerPosition: (savedState.tickerPosition as number) || 100,
        stockPrices: (savedState.stockPrices as Array<{symbol: string; price: number; change: string}>) || [
          { symbol: "BRPX", price: 384.52, change: "+2.1%" },
          { symbol: "AAPL", price: 189.43, change: "-0.8%" },
          { symbol: "GOOGL", price: 142.37, change: "+1.3%" }
        ]
      };
    } else {
      // Fresh start - use default duration
      const now = Date.now();
      const initialState = {
        startTime: now,
        duration: taskDuration,
        showPassword: false,
        checkedStories: [],
        staticPassword: generateParameterPassword(TASK_ID_NewsCheckerHard, taskDuration),
        showBreakingNews: false,
        showAdPopup: false,
        showVideoThumbnail: false,
        tickerPosition: 100,
        stockPrices: [
          { symbol: "BRPX", price: 384.52, change: "+2.1%" },
          { symbol: "AAPL", price: 189.43, change: "-0.8%" },
          { symbol: "GOOGL", price: 142.37, change: "+1.3%" }
        ]
      };
      
      TaskStateManager.saveState(TASK_ID_NewsCheckerHard, initialState);
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
  
  // Calculate current news index based on elapsed time (not saved in state) - Hard mode with cycling
  const calculateCurrentNewsIndex = () => {
    const elapsedSeconds = (Date.now() - startTime) / 1000;
    const flipInterval = Math.max(1, Math.floor(newsDuration / NEWSPAPER_COUNT));
    
    if (elapsedSeconds >= newsDuration) {
      // At exactly duration time, show target post (11) first
      if (elapsedSeconds < newsDuration + 60) { // Show target for 60 seconds
        return NEWSPAPER_COUNT - 1; // Target post (11)
      }
      
      // After showing target, start continuous cycling from newspaper 0
      const cycleTime = elapsedSeconds - (newsDuration + 60); // Subtract the 60 seconds for target display
      const fullCycleDuration = NEWSPAPER_COUNT * flipInterval;
      const cyclePosition = cycleTime % fullCycleDuration;
      return Math.floor(cyclePosition / flipInterval);
    } else {
      // Before duration time
      if (newsDuration < NEWSPAPER_COUNT) {
        // If duration is less than 12 seconds, stay on first newspaper
        return 0; // Stay on first newspaper until duration is reached
      } else {
        // Normal case: show newspapers in sequence (0 to 10)
        let newsIndex = 0;
        for (let i = 0; i < NEWSPAPER_COUNT - 1; i++) { // Only cycle through 0-10
          const newspaperShouldAppearAt = i * flipInterval;
          if (elapsedSeconds >= newspaperShouldAppearAt) {
            newsIndex = i;
          }
        }
        return newsIndex;
      }
    }
  };
  
  const [currentNewsIndex, setCurrentNewsIndex] = useState(() => calculateCurrentNewsIndex());
  const [showPassword, setShowPassword] = useState(initialState.showPassword);
  const [checkedStories, setCheckedStories] = useState(initialState.checkedStories);
  const [staticPassword, setStaticPassword] = useState(initialState.staticPassword || "");
  const [isFlipping, setIsFlipping] = useState(false);
  const [currentTime, setCurrentTime] = useState(Date.now());
  const [showBreakingNews, setShowBreakingNews] = useState(initialState.showBreakingNews);
  const [showAdPopup, setShowAdPopup] = useState(initialState.showAdPopup);
  const [showVideoThumbnail, setShowVideoThumbnail] = useState(initialState.showVideoThumbnail);

  // Calculate flip interval based on the actual duration being used
  const flipInterval = Math.max(1, Math.floor(newsDuration / NEWSPAPER_COUNT)); // in seconds
  const [tickerPosition, setTickerPosition] = useState(initialState.tickerPosition);
  const [stockPrices, setStockPrices] = useState(initialState.stockPrices);
  const { recordSuccess } = useTaskAnalytics(TASK_ID_NewsCheckerHard);
  
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
      title: "Hardware Weekly",
      headline: "New Magnetic Storage Drives Hit Market",
      subheadline: "Traditional magnetic technology shows 40% speed improvement",
      image: "📰",
      isMagneticDistractor: true
    },
    {
      title: "MagneticUI Inc.",
      headline: "MagneticUI Inc. Releases Design Tools",
      subheadline: "Startup company launches new interface builder for developers",
      image: "📰",
      isFalsePositive: true
    },
    {
      title: "Apple News",
      headline: "Apple Unveils Next-Gen UI Framework",
      subheadline: "Revolutionary interface design system for iOS applications and development",
      image: "📰",
      isCompetitorDistractor: true
    },
    {
      title: "Google Research",
      headline: "Google Develops Advanced Interface AI",
      subheadline: "Machine learning models improve user interface generation and optimization",
      image: "📰",
      isCompetitorDistractor: true
    },
    {
      title: "Meta Design",
      headline: "Meta's New VR Interface Standards",
      subheadline: "Virtual reality interface guidelines reshape immersive experience design",
      image: "📰",
      isCompetitorDistractor: true
    },
    {
      title: "Innovation Gazette",
      headline: "Smart Home Magnetic Sensors Launch",
      subheadline: "IoT devices use magnetic field detection for enhanced automation",
      image: "📰",
      isMagneticDistractor: true
    },
    {
      title: "Future Times",
      headline: "Delivery Drones Learn to Ring Doorbells",
      subheadline: "Amazon's latest update includes polite door etiquette protocols",
      image: "📰"
    },
    {
      title: "Business Daily",
      headline: "Startup Raises $50M for Magnetic Levitation",
      subheadline: "Transportation company focuses on magnetic rail technology advancement",
      image: "📰",
      isMagneticDistractor: true
    },
    {
      title: "Design Trends",
      headline: "Framework Wars Heat Up in Tech Industry",
      subheadline: "Competition intensifies between major interface design framework providers",
      image: "📰",
      isUIDistractor: true
    },
    {
      title: "Silicon Valley",
      headline: "Magnetic Field Research Breakthrough",
      subheadline: "Scientists discover new applications for magnetic field manipulation in computing",
      image: "📰",
      isMagneticDistractor: true
    },
    {
      title: "Research Journal",
      headline: "Cognitive Therapy Shows Promise in Memory Studies",
      subheadline: "Federal research team develops breakthrough treatment for progressive memory decline in clinical applications",
      image: "📰",
      isAlzheimersTreatment: true,
      isSubtle: true
    }
  ];

  // Save state whenever any state variable changes (debounced to prevent race conditions)
  useEffect(() => {
    const saveState = () => {
      const currentState = {
        startTime,
        duration: newsDuration,
        showPassword,
        checkedStories,
        staticPassword,
        showBreakingNews,
        showAdPopup,
        showVideoThumbnail,
        tickerPosition,
        stockPrices
      };
      
      TaskStateManager.saveState(TASK_ID_NewsCheckerHard, currentState);
    };

    // Debounce rapid state updates (especially from ticker and stock updates)
    const debounceTimer = setTimeout(saveState, 100);
    
    return () => clearTimeout(debounceTimer);
  }, [startTime, newsDuration, showPassword, checkedStories, staticPassword, showBreakingNews, showAdPopup, showVideoThumbnail, tickerPosition, stockPrices]);

  // Record success if resuming to an already completed state
  useEffect(() => {
    if (initialState.showPassword) {
      recordSuccess();
    }
  }, [initialState.showPassword, recordSuccess]);

  // Simplified newspaper scheduling using interval timer
  useEffect(() => {
    const updateNewspaper = () => {
      const elapsedSeconds = (Date.now() - startTime) / 1000;
      let newIndex = 0;
      
      if (elapsedSeconds >= newsDuration) {
        // Show target post (11) for 60 seconds after duration
        if (elapsedSeconds < newsDuration + 60) {
          newIndex = NEWSPAPER_COUNT - 1; // Target post (11)
        } else {
          // After target display, cycle through all newspapers
          const cycleTime = elapsedSeconds - (newsDuration + 60);
          const cyclePosition = Math.floor(cycleTime / flipInterval) % NEWSPAPER_COUNT;
          newIndex = cyclePosition;
        }
      } else {
        // Before duration: cycle through newspapers 0-10
        if (newsDuration < NEWSPAPER_COUNT) {
          newIndex = 0; // Stay on first newspaper if duration is very short
        } else {
          newIndex = Math.min(Math.floor(elapsedSeconds / flipInterval), NEWSPAPER_COUNT - 2);
        }
      }
      
      if (newIndex !== currentNewsIndex) {
        setIsFlipping(true);
        setTimeout(() => {
          setCurrentNewsIndex(newIndex);
          setIsFlipping(false);
        }, 150);
      }
    };

    // Update immediately, then every second
    updateNewspaper();
    const interval = setInterval(updateNewspaper, 1000);
    
    return () => clearInterval(interval);
  }, [startTime, newsDuration, flipInterval, currentNewsIndex]);

  // Moving news ticker
  useEffect(() => {
    const ticker = setInterval(() => {
      setTickerPosition((prev) => {
        if (prev <= -100) return 100;
        return prev - 0.8;
      });
    }, 50);

    return () => clearInterval(ticker);
  }, []);

  // Breaking news banner
  useEffect(() => {
    const breakingTimer = setInterval(() => {
      setShowBreakingNews(true);
      setTimeout(() => {
        setShowBreakingNews(false);
      }, 8000);
    }, 35000); // Show every 35 seconds

    return () => clearInterval(breakingTimer);
  }, []);

  // Ad popup timer
  useEffect(() => {
    const adTimer = setInterval(() => {
      setShowAdPopup(true);
      setTimeout(() => {
        setShowAdPopup(false);
      }, 6000);
    }, 30000); // Show every 30 seconds

    return () => clearInterval(adTimer);
  }, []);

  // Video thumbnail
  useEffect(() => {
    const videoTimer = setInterval(() => {
      setShowVideoThumbnail(true);
      setTimeout(() => {
        setShowVideoThumbnail(false);
      }, 4000);
    }, 25000); // Show every 25 seconds

    return () => clearInterval(videoTimer);
  }, []);

  // Stock price updates
  useEffect(() => {
    const stockTimer = setInterval(() => {
      setStockPrices(prev => prev.map(stock => ({
        ...stock,
        price: parseFloat((stock.price + (Math.random() - 0.5) * 2).toFixed(2)),
        change: Math.random() > 0.5 ? `+${(Math.random() * 3).toFixed(1)}%` : `-${(Math.random() * 2).toFixed(1)}%`
      })));
    }, 10000);

    return () => clearInterval(stockTimer);
  }, []);

  const handleNewsClick = () => {
    const currentStory = newsStories[currentNewsIndex];
    
    // Track clicked stories
    if (!checkedStories.includes(currentNewsIndex)) {
      setCheckedStories((prev) => [...prev, currentNewsIndex]);
    }
    
    if (currentStory.isAlzheimersTreatment) {
      const finalPassword = generateParameterPassword(TASK_ID_NewsCheckerHard, newsDuration);
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
    <div className="max-w-6xl mx-auto mt-10 p-6 relative">
      {/* Development Tools */}
      {(isLocalhost || adminConsoleEnabled) && (
        <div className="bg-gradient-to-r from-yellow-50 to-amber-50 border border-yellow-200/50 rounded-xl p-4 mb-6 shadow-sm backdrop-blur-sm">
          <div className="flex items-center justify-between text-sm">
            <div className="text-yellow-800 font-medium">
              <strong>Dev Tools:</strong> Elapsed: {elapsedTime}s | 
              Story: {currentNewsIndex + 1}/{newsStories.length} | 
              Duration: {newsDuration}s | Flip Interval: {flipInterval}s |
              Checked: {checkedStories.length} stories |
              Persistent: {TaskStateManager.hasState(TASK_ID_NewsCheckerHard) ? '✅' : '❌'}
            </div>
            <button 
              onClick={() => {
                if (window.confirm('Are you sure you want to reset this task? This will restart the news cycle from the beginning.')) {
                  TaskStateManager.clearState(TASK_ID_NewsCheckerHard);
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

      {/* Breaking News Banner */}
      {showBreakingNews && (
        <div className="fixed top-0 left-0 right-0 bg-red-600 text-white py-2 z-50 animate-pulse">
          <div className="text-center font-bold">
            🚨 BREAKING: Major tech announcement expected today • Market volatility continues • Stay tuned for updates
          </div>
        </div>
      )}

      {/* Ad Popup */}
      {showAdPopup && (
        <div className="fixed top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 bg-blue-600 text-white p-6 rounded-lg shadow-2xl z-50 max-w-sm">
          <button 
            onClick={() => setShowAdPopup(false)}
            className="absolute top-2 right-2 text-white hover:text-gray-200 text-xl"
          >
            ✕
          </button>
          <div className="text-center">
            <h3 className="text-xl font-bold mb-2">📰 Premium News!</h3>
            <p className="mb-4">Subscribe for unlimited access to breaking tech news and market analysis</p>
            <button className="bg-white text-blue-600 px-4 py-2 rounded font-bold">
              Subscribe Now - $9.99/mo
            </button>
          </div>
        </div>
      )}

      {/* Video Thumbnail */}
      {showVideoThumbnail && (
        <div className="fixed bottom-4 right-4 bg-black rounded-lg overflow-hidden shadow-lg z-40 w-64">
          <div className="relative">
            <div className="bg-gray-800 h-36 flex items-center justify-center">
              <div className="text-white text-4xl">▶️</div>
            </div>
            <button 
              onClick={() => setShowVideoThumbnail(false)}
              className="absolute top-2 right-2 text-white hover:text-gray-300 text-sm"
            >
              ✕
            </button>
          </div>
          <div className="p-3 bg-white">
            <p className="text-sm font-semibold">Tech Industry Update</p>
            <p className="text-xs text-gray-600">Live: Framework competition heats up</p>
          </div>
        </div>
      )}
      
      {/* Stock Ticker */}
      <div className="bg-black text-green-400 py-1 mb-4 overflow-hidden font-mono text-sm">
        <div 
          className="whitespace-nowrap transition-transform duration-75"
          style={{ transform: `translateX(${tickerPosition}%)` }}
        >
          {stockPrices.map((stock, index) => (
            <span key={index} className="mr-8">
              {stock.symbol}: ${stock.price} ({stock.change})
            </span>
          ))}
          <span className="mr-8">• DOW: 34,521.22 (+0.4%) • NASDAQ: 13,987.45 (-0.2%) • S&P: 4,456.78 (+0.1%)</span>
        </div>
      </div>

      {/* Moving News Ticker */}
      <div className="bg-red-600 text-white py-2 mb-6 overflow-hidden">
        <div 
          className="whitespace-nowrap transition-transform duration-75"
          style={{ transform: `translateX(${tickerPosition}%)` }}
        >
          <span className="font-bold">URGENT:</span> System maintenance scheduled 3PM • Framework updates available • Market volatility expected • Tech conferences this week • Breaking developments
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
                    BREAKING • TECH INDUSTRY • MARKET ANALYSIS • INNOVATION WATCH
                  </div>
                </div>
              </div>

              {/* Main Headlines Section with Heavy Noise */}
              <div className="grid grid-cols-3 gap-6">
                {/* Left Column - Main Story */}
                <div className="col-span-2">
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

                {/* Right Column - Heavy Secondary Content */}
                <div>
                  <div className="space-y-4">
                    <div className="border border-gray-300 p-3">
                      <h4 className="text-sm font-bold mb-2">📊 Market Watch</h4>
                      <div className="text-xs space-y-1">
                        <div>BRPX: $384.52 (+2.1%)</div>
                        <div>AAPL: $189.43 (-0.8%)</div>
                        <div>GOOGL: $142.37 (+1.3%)</div>
                      </div>
                    </div>
                    
                    <div className="border border-gray-300 p-3">
                      <h4 className="text-sm font-bold mb-2">🔥 Trending</h4>
                      <div className="text-xs space-y-1">
                        <div>• Apple's new framework</div>
                        <div>• Google AI advances</div>
                        <div>• Meta VR updates</div>
                        <div>• Magnetic storage</div>
                      </div>
                    </div>

                    <div className="border border-gray-300 p-3">
                      <h4 className="text-sm font-bold mb-2">⚡ Quick Hits</h4>
                      <div className="text-xs space-y-1">
                        <div>Framework competition intensifies across major tech companies</div>
                        <div>Interface design standards evolve with new technologies</div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Additional Noise Section */}
              <div className="mt-6 pt-4 border-t-2 border-gray-300">
                <div className="grid grid-cols-4 gap-4 text-xs">
                  <div>
                    <h5 className="font-bold mb-1">🌟 Innovation</h5>
                    <p>Startup ecosystem thrives with new magnetic technologies and interface innovations</p>
                  </div>
                  <div>
                    <h5 className="font-bold mb-1">🏢 Enterprise</h5>
                    <p>Major corporations announce partnerships in UI development space</p>
                  </div>
                  <div>
                    <h5 className="font-bold mb-1">🔬 Research</h5>
                    <p>Academic institutions collaborate on next-generation interface systems</p>
                  </div>
                  <div>
                    <h5 className="font-bold mb-1">📱 Mobile</h5>
                    <p>Mobile interface frameworks see major updates across platforms</p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* NO PAGE INDICATORS IN HARD MODE */}
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
            You successfully identified the FDA Alzheimer's treatment approval announcement!
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

export default NewsCheckerHard;