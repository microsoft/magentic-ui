import { useState, useEffect, useRef } from "react";
import { useTaskAnalytics } from "../utils/useTaskAnalytics";
import { TaskStateManager } from "../utils/TaskStateManager";
import { generateParameterPassword } from "../utils/parameterPassword";
import { URLParameterHandler } from "../utils/urlParameterHandler";
import { DURATION } from "../config/constants";

export const TASK_ID_ReactorEasy = "reactor-easy";

const ReactorEasy = () => {
  // Parse URL parameters manually (don't clean yet)
  const urlParams = new URLSearchParams(window.location.search);
  const duration = parseInt(urlParams.get('duration') || DURATION.DEFAULT.toString(), 10);
  const showHints = urlParams.get('hints') === 'true';
  
  // Validate duration parameter
  const taskDuration = (duration >= 1 && duration <= 86400) ? duration : 30;
  
  // Check if validation failed and emit error for toast
  useEffect(() => {
    if (urlParams.has('duration') && taskDuration !== duration) {
      // Validation failed, emit error for toast
      const errors = [{
        parameter: 'duration',
        providedValue: urlParams.get('duration') || '',
        defaultUsed: 30,
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
    const savedState = TaskStateManager.loadState(TASK_ID_ReactorEasy);
    
    // Check if we should reset state based on parameter changes
    if (URLParameterHandler.shouldResetState(TASK_ID_ReactorEasy, savedState, params)) {
      TaskStateManager.clearState(TASK_ID_ReactorEasy);
      
      const now = Date.now();
      const initialState = {
        startTime: now,
        duration: taskDuration,
        timeLeft: taskDuration,
        isExploded: false,
        showExplosion: false,
        showDebris: false,
        showPassword: false,
        staticPassword: generateParameterPassword(TASK_ID_ReactorEasy, taskDuration)
      };
      
      TaskStateManager.saveState(TASK_ID_ReactorEasy, initialState);
      return initialState;
    }
    
    if (savedState) {
      // Resume from saved state
      const savedDuration = (savedState.duration as number) || duration;
      const elapsedTime = Math.floor((Date.now() - (savedState.startTime as number)) / 1000);
      const remainingTime = Math.max(0, savedDuration - elapsedTime);
      
      const hasExploded = (savedState.isExploded as boolean) || remainingTime === 0;
      
      return {
        startTime: savedState.startTime as number,
        duration: savedDuration,
        timeLeft: remainingTime,
        isExploded: hasExploded,
        showExplosion: (savedState.showExplosion as boolean) || false,
        showDebris: (savedState.showDebris as boolean) || false,
        showPassword: (savedState.showPassword as boolean) || hasExploded,
        staticPassword: generateParameterPassword(TASK_ID_ReactorEasy, savedDuration)
      };
    } else {
      // Fresh start - use default duration
      const now = Date.now();
      const initialState = {
        startTime: now,
        duration: taskDuration,
        timeLeft: taskDuration,
        isExploded: false,
        showExplosion: false,
        showDebris: false,
        showPassword: false,
        staticPassword: generateParameterPassword(TASK_ID_ReactorEasy, taskDuration)
      };
      
      TaskStateManager.saveState(TASK_ID_ReactorEasy, initialState);
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
  const [reactorDuration] = useState(initialState.duration);
  const [showPassword, setShowPassword] = useState(initialState.showPassword);
  const [staticPassword, setStaticPassword] = useState(initialState.staticPassword || "");
  const [timeLeft, setTimeLeft] = useState(initialState.timeLeft);
  const [isExploded, setIsExploded] = useState(initialState.isExploded);
  const [showExplosion, setShowExplosion] = useState(initialState.showExplosion);
  const [showDebris, setShowDebris] = useState(initialState.showDebris);
  const countdownRef = useRef<number | null>(null);
  const explosionTimeoutRef = useRef<number | null>(null);
  const debrisTimeoutRef = useRef<number | null>(null);
  const { recordSuccess } = useTaskAnalytics(TASK_ID_ReactorEasy);
  
  // Record success if resuming to an already completed state
  useEffect(() => {
    if (initialState.isExploded && initialState.showPassword) {
      recordSuccess();
    }
  }, [initialState.isExploded, initialState.showPassword, recordSuccess]);

  // Save state whenever any state variable changes
  useEffect(() => {
    const currentState = {
      startTime,
      duration: reactorDuration,
      timeLeft,
      isExploded,
      showExplosion,
      showDebris,
      showPassword,
      staticPassword
    };
    
    TaskStateManager.saveState(TASK_ID_ReactorEasy, currentState);
  }, [startTime, reactorDuration, timeLeft, isExploded, showExplosion, showDebris, showPassword, staticPassword]);

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

  const formatTime = (seconds: number) => {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`;
  };

  const triggerExplosion = () => {
    const finalPassword = generateParameterPassword(TASK_ID_ReactorEasy, reactorDuration);
    setIsExploded(true);
    setShowExplosion(true);
    setShowPassword(true);
    setStaticPassword(finalPassword);
    recordSuccess();
    
    // Show debris after 2 seconds
    debrisTimeoutRef.current = window.setTimeout(() => {
      setShowDebris(true);
    }, 2000);
  };

  // Timer logic based on elapsed time from start
  useEffect(() => {
    if (isExploded) {
      return; // Don't run timer if already exploded
    }

    const updateTimer = () => {
      const elapsedSeconds = Math.floor((Date.now() - startTime) / 1000);
      const remainingTime = Math.max(0, reactorDuration - elapsedSeconds);
      
      setTimeLeft(remainingTime);
      
      if (remainingTime === 0 && !isExploded) {
        triggerExplosion();
      }
    };

    // Update immediately
    updateTimer();
    
    // Then update every second
    countdownRef.current = window.setInterval(updateTimer, 1000);

    return () => {
      if (countdownRef.current) {
        clearInterval(countdownRef.current);
      }
      if (explosionTimeoutRef.current) {
        clearTimeout(explosionTimeoutRef.current);
      }
      if (debrisTimeoutRef.current) {
        clearTimeout(debrisTimeoutRef.current);
      }
    };
  }, [startTime, reactorDuration, isExploded]);

  return (
    <div className="min-h-screen bg-white p-4 overflow-hidden">
      {/* Development Tools */}
      {(isLocalhost || adminConsoleEnabled) && (
        <div className="bg-gradient-to-r from-yellow-50 to-amber-50 border border-yellow-200/50 rounded-xl p-4 mb-6 shadow-sm backdrop-blur-sm">
          <div className="flex items-center justify-between text-sm">
            <div className="text-yellow-800 font-medium">
              <strong>Dev Tools:</strong> Time Left: {timeLeft}s | 
              Exploded: {isExploded ? '✅' : '❌'} |
              Persistent: {TaskStateManager.hasState(TASK_ID_ReactorEasy) ? '✅' : '❌'}
            </div>
            <button 
              onClick={() => {
                if (window.confirm('Are you sure you want to reset this task? This will restart the reactor countdown from the beginning.')) {
                  TaskStateManager.clearState(TASK_ID_ReactorEasy);
                  // Reload with current duration parameter to maintain the same timer
                  window.location.href = `${window.location.pathname}?duration=${taskDuration}`;
                }
              }}
              className="px-3 py-1.5 bg-gradient-to-r from-red-500 to-red-600 text-white text-xs rounded-lg hover:from-red-600 hover:to-red-700 transition-all duration-200 shadow-sm"
            >
              Reset Task
            </button>
          </div>
        </div>
      )}
      <style dangerouslySetInnerHTML={{
        __html: `
          @keyframes steam {
            0% { transform: translateY(0) scale(0.8); opacity: 0.7; }
            50% { transform: translateY(-20px) scale(1); opacity: 0.4; }
            100% { transform: translateY(-40px) scale(1.2); opacity: 0; }
          }
          @keyframes rotate {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
          }
          @keyframes shake {
            0%, 100% { transform: translateX(0); }
            25% { transform: translateX(-2px); }
            75% { transform: translateX(2px); }
          }
          @keyframes explosion {
            0% { transform: scale(1); opacity: 1; }
            50% { transform: scale(1.5); opacity: 0.8; }
            100% { transform: scale(3); opacity: 0; }
          }
          @keyframes debris {
            0% { transform: translateY(-100px) rotate(0deg); opacity: 1; }
            100% { transform: translateY(200px) rotate(360deg); opacity: 0; }
          }
          .steam-particle {
            animation: steam 3s infinite linear;
          }
          .rotate {
            animation: rotate 4s infinite linear;
          }
          .shake {
            animation: shake 0.5s infinite;
          }
          .explosion-flash {
            animation: explosion 2s ease-out;
          }
          .debris-piece {
            animation: debris 3s ease-out forwards;
          }
        `
      }} />
      
      <div className="max-w-6xl mx-auto">

        {/* LED Timer Display */}
        <div className="flex justify-center mb-8">
          <div className="bg-black border-4 border-red-600 rounded-lg p-8 shadow-2xl">
            <div className="text-center mb-2">
              <span className="text-red-300 text-lg font-bold tracking-wider">TIME TO MELTDOWN</span>
            </div>
            <div className="font-mono text-8xl font-bold text-red-500 text-center tracking-wider" 
                 style={{ 
                   textShadow: '0 0 20px #ef4444, 0 0 40px #ef4444', 
                   fontFamily: 'monospace',
                   filter: 'brightness(1.2)'
                 }}>
              {formatTime(timeLeft)}
            </div>
          </div>
        </div>

        {/* Reactor Visual */}
        <div className="relative flex justify-center mb-8">
          <div className={`relative ${showExplosion ? 'explosion-flash' : ''}`}>
            {/* Explosion Effect */}
            {showExplosion && (
              <div className="absolute inset-0 z-50">
                <div className="w-96 h-96 bg-orange-400 rounded-full opacity-80 animate-ping absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2"></div>
                <div className="w-80 h-80 bg-red-500 rounded-full opacity-60 animate-ping absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2" style={{ animationDelay: '0.2s' }}></div>
                <div className="w-64 h-64 bg-yellow-400 rounded-full opacity-40 animate-ping absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2" style={{ animationDelay: '0.4s' }}></div>
              </div>
            )}


            {/* Debris */}
            {showDebris && (
              <div className="absolute inset-0 z-40">
                {[...Array(12)].map((_, i) => (
                  <div
                    key={i}
                    className="debris-piece absolute w-4 h-4 bg-gray-600 rounded"
                    style={{
                      left: `${30 + (i * 8)}%`,
                      top: `${20 + (i % 3) * 20}%`,
                      animationDelay: `${i * 0.1}s`,
                    }}
                  />
                ))}
              </div>
            )}

            {/* Main Reactor Structure */}
            <div className={`relative z-10 ${isExploded ? 'opacity-20' : ''}`}>
              {/* Base Platform */}
              <div className="w-80 h-8 bg-gradient-to-r from-gray-700 via-gray-600 to-gray-700 rounded-lg shadow-lg mb-4"></div>
              
              {/* Main Reactor Core */}
              <div className="relative w-64 h-64 mx-auto">
                {/* Outer Shell */}
                <div className="absolute inset-0 bg-gradient-to-br from-orange-800 via-orange-700 to-orange-900 rounded-full border-8 border-orange-600 shadow-2xl"></div>
                
                {/* Inner Core */}
                <div className="absolute inset-8 bg-gradient-to-br from-yellow-600 via-orange-500 to-red-600 rounded-full animate-pulse shadow-inner"></div>
                
                
                {/* Rotating Elements */}
                <div className="absolute inset-12 border-4 border-orange-400 rounded-full rotate animate-pulse opacity-60"></div>
                <div className="absolute inset-16 border-2 border-yellow-400 rounded-full rotate opacity-40" style={{ animationDirection: 'reverse', animationDuration: '6s' }}></div>
              </div>

              {/* Pipes */}
              <div className="flex justify-center gap-8 mt-4">
                <div className="w-6 h-24 bg-gradient-to-b from-gray-600 to-gray-800 rounded-full relative">
                  <div className="absolute top-2 left-1/2 transform -translate-x-1/2 w-3 h-3 bg-gray-500 rounded-full"></div>
                </div>
                <div className="w-6 h-32 bg-gradient-to-b from-gray-600 to-gray-800 rounded-full relative">
                  <div className="absolute top-2 left-1/2 transform -translate-x-1/2 w-3 h-3 bg-gray-500 rounded-full"></div>
                </div>
                <div className="w-6 h-28 bg-gradient-to-b from-gray-600 to-gray-800 rounded-full relative">
                  <div className="absolute top-2 left-1/2 transform -translate-x-1/2 w-3 h-3 bg-gray-500 rounded-full"></div>
                </div>
              </div>

              {/* Steam Particles */}
              {!isExploded && [...Array(8)].map((_, i) => (
                <div
                  key={i}
                  className="steam-particle absolute w-4 h-4 bg-gray-400 rounded-full opacity-60"
                  style={{
                    left: `${40 + (i * 5)}%`,
                    top: `${10 + (i % 2) * 5}%`,
                    animationDelay: `${i * 0.4}s`,
                  }}
                />
              ))}

              {/* Control Panels */}
              <div className="flex justify-center gap-4 mt-6">
                <div className="w-16 h-12 bg-gray-800 rounded border-2 border-gray-600 p-2">
                  <div className="w-2 h-2 bg-red-500 rounded-full animate-pulse mb-1"></div>
                  <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse mb-1"></div>
                  <div className="w-2 h-1 bg-yellow-500 rounded"></div>
                </div>
                <div className="w-16 h-12 bg-gray-800 rounded border-2 border-gray-600 p-2">
                  <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse mb-1"></div>
                  <div className="w-2 h-2 bg-orange-500 rounded-full animate-pulse mb-1"></div>
                  <div className="w-2 h-1 bg-purple-500 rounded"></div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Status Banner - Only show when exploded */}
        {isExploded && (
          <div className="bg-gray-900 border-4 border-red-500 rounded-lg p-6 mb-6">
            <div 
              id="reactor-status"
              data-state="exploded"
              className="text-center p-6 rounded-lg font-bold text-2xl bg-green-600 text-white"
            >
              <div>
                <div className="text-4xl mb-4">💥 REACTOR EXPLODED 💥</div>
                {showPassword && (
                  <div className="text-lg">
                    Password: 
                    <span id="shutdown-code" className="bg-black px-3 py-2 rounded ml-2 font-mono">
                      {staticPassword}
                    </span>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Technical Details */}
        {showHints && (
          <div className="bg-gray-900 text-green-400 rounded-lg p-6 mt-6 border-2 border-green-500 font-mono">
            <h3 className="font-bold text-green-300 mb-3 text-lg">🛠️ TECHNICAL SPECIFICATIONS</h3>
            <div className="text-sm space-y-2">
              <p><strong className="text-yellow-400">🎯 Status Element:</strong> <code className="bg-gray-700 px-2 py-1 rounded">#reactor-status</code></p>
              <p><strong className="text-yellow-400">✅ Explosion State:</strong> <code className="bg-gray-700 px-2 py-1 rounded">data-state="exploded"</code></p>
              <p><strong className="text-yellow-400">🔓 Code Element:</strong> <code className="bg-gray-700 px-2 py-1 rounded">#shutdown-code</code></p>
              <p><strong className="text-yellow-400">⏱️ Timer:</strong> {Math.floor(reactorDuration / 60)}:{(reactorDuration % 60).toString().padStart(2, '0')} minutes countdown</p>
              <p><strong className="text-yellow-400">📡 Current State:</strong> <code className="bg-gray-700 px-2 py-1 rounded">data-state="{isExploded ? 'exploded' : 'critical'}"</code></p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ReactorEasy; 