import { useState, useEffect, useRef } from "react";
import { useTaskAnalytics } from "../utils/useTaskAnalytics";
import { TaskStateManager } from "../utils/TaskStateManager";
import { generateParameterPassword } from "../utils/parameterPassword";
import { URLParameterHandler } from "../utils/urlParameterHandler";
import { DURATION, TIMEOUT, COMMON } from "../config/constants";

export const DECOY_PASSWORDS = ["BEEPBEEP123", "WARMUP456", "MICROWAVE1", "TIMER2024", "COOKING88"];
export const TASK_ID_ReactorMedium = "reactor-medium";

const ReactorMedium = () => {
  // Parse URL parameters manually (don't clean yet)
  const urlParams = new URLSearchParams(window.location.search);
  const duration = parseInt(urlParams.get('duration') || DURATION.DEFAULT.toString(), 10);
  const showHints = urlParams.get('hints') === 'true';
  
  // Validate duration parameter
  const taskDuration = (duration >= DURATION.MIN && duration <= DURATION.MAX_DAY) ? duration : DURATION.DEFAULT;
  
  // Check if validation failed and emit error for toast
  useEffect(() => {
    if (urlParams.has('duration') && taskDuration !== duration) {
      // Validation failed, emit error for toast
      const errors = [{
        parameter: 'duration',
        providedValue: urlParams.get('duration') || '',
        defaultUsed: DURATION.DEFAULT,
        reason: duration < 1 ? 'Value must be at least 1' : 
                duration > DURATION.MAX_DAY ? `Value must be at most ${DURATION.MAX_DAY.toLocaleString()}` :
                isNaN(duration) ? 'Value must be a valid number' : 'Invalid value'
      }];
      
      // Use the existing validation error system
      setTimeout(() => {
        URLParameterHandler.emitValidationError(errors);
      }, COMMON.VALIDATION_DELAY);
    }
  }, []); // Run once on mount
  
  // Create params object for shouldResetState check
  const params = { duration: taskDuration, hasAnyParams: urlParams.has('duration') };

  // Initialize state from localStorage or defaults
  const initializeState = () => {
    const savedState = TaskStateManager.loadState(TASK_ID_ReactorMedium);
    
    // If a new duration parameter was provided, start fresh regardless of saved state
    if (URLParameterHandler.shouldResetState(TASK_ID_ReactorMedium, savedState, params)) {
      TaskStateManager.clearState(TASK_ID_ReactorMedium);
      
      const now = Date.now();
      const distractorDuration = Math.floor(taskDuration * 0.5); // 50% of main reactor time
      const decoyPassword = DECOY_PASSWORDS[Math.floor(Math.random() * DECOY_PASSWORDS.length)];
      
      const initialState = {
        startTime: now,
        duration: taskDuration,
        timeLeft: taskDuration,
        distractorTimeLeft: distractorDuration,
        distractorDuration: distractorDuration,
        isExploded: false,
        distractorExploded: false,
        showExplosion: false,
        showDebris: false,
        showPassword: false,
        showDecoyPassword: false,
        staticPassword: generateParameterPassword(TASK_ID_ReactorMedium, taskDuration),
        decoyPassword: decoyPassword,
      };
      
      TaskStateManager.saveState(TASK_ID_ReactorMedium, initialState);
      return initialState;
    }
    
    if (savedState) {
      // Resume from saved state with proper type casting
      const savedDuration = (savedState.duration as number) || duration;
      const savedDistractorDuration = (savedState.distractorDuration as number) || Math.floor(savedDuration * 0.5);
      const elapsedTime = Math.floor((Date.now() - (savedState.startTime as number)) / COMMON.MILLISECONDS_PER_SECOND);
      const remainingTime = Math.max(0, savedDuration - elapsedTime);
      const distractorRemainingTime = Math.max(0, savedDistractorDuration - elapsedTime);
      
      const hasExploded = savedState.isExploded || remainingTime === 0;
      const distractorHasExploded = savedState.distractorExploded || distractorRemainingTime === 0;
      
      return {
        startTime: savedState.startTime as number,
        duration: savedDuration,
        timeLeft: remainingTime,
        distractorTimeLeft: distractorRemainingTime,
        distractorDuration: savedDistractorDuration,
        isExploded: hasExploded,
        distractorExploded: distractorHasExploded,
        showExplosion: savedState.showExplosion as boolean || false,
        showDebris: savedState.showDebris as boolean || false,
        showPassword: savedState.showPassword as boolean || hasExploded,
        showDecoyPassword: savedState.showDecoyPassword as boolean || distractorHasExploded,
        staticPassword: generateParameterPassword(TASK_ID_ReactorMedium, savedDuration),
        decoyPassword: savedState.decoyPassword as string || DECOY_PASSWORDS[0]
      };
    } else {
      // Fresh start - use default duration
      const now = Date.now();
      const distractorDuration = Math.floor(duration * 0.5);
      const decoyPassword = DECOY_PASSWORDS[Math.floor(Math.random() * DECOY_PASSWORDS.length)];
      
      const initialState = {
        startTime: now,
        duration: duration,
        timeLeft: duration,
        distractorTimeLeft: distractorDuration,
        distractorDuration: distractorDuration,
        isExploded: false,
        distractorExploded: false,
        showExplosion: false,
        showDebris: false,
        showPassword: false,
        showDecoyPassword: false,
        staticPassword: generateParameterPassword(TASK_ID_ReactorMedium, taskDuration),
        decoyPassword: decoyPassword
      };
      
      TaskStateManager.saveState(TASK_ID_ReactorMedium, initialState);
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
  const [timeLeft, setTimeLeft] = useState(initialState.timeLeft);
  const [distractorTimeLeft, setDistractorTimeLeft] = useState(initialState.distractorTimeLeft);
  const [distractorDuration] = useState(initialState.distractorDuration);
  const [isExploded, setIsExploded] = useState(initialState.isExploded);
  const [distractorExploded, setDistractorExploded] = useState(initialState.distractorExploded);
  const [showExplosion, setShowExplosion] = useState(initialState.showExplosion);
  const [showDebris, setShowDebris] = useState(initialState.showDebris);
  const [showPassword, setShowPassword] = useState(initialState.showPassword);
  const [showDecoyPassword, setShowDecoyPassword] = useState(initialState.showDecoyPassword);
  const [staticPassword, setStaticPassword] = useState(initialState.staticPassword || "");
  const [decoyPassword] = useState(initialState.decoyPassword);
  const countdownRef = useRef<number | null>(null);
  const explosionTimeoutRef = useRef<number | null>(null);
  const debrisTimeoutRef = useRef<number | null>(null);
  const { recordSuccess } = useTaskAnalytics(TASK_ID_ReactorMedium);
  
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
      distractorTimeLeft,
      distractorDuration,
      isExploded,
      distractorExploded,
      showExplosion,
      showDebris,
      showPassword,
      showDecoyPassword,
      staticPassword,
      decoyPassword
    };
    
    TaskStateManager.saveState(TASK_ID_ReactorMedium, currentState);
  }, [startTime, reactorDuration, timeLeft, distractorTimeLeft, distractorDuration, isExploded, distractorExploded, showExplosion, showDebris, showPassword, showDecoyPassword, staticPassword, decoyPassword]);

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
    const interval = setInterval(syncWithStorage, TIMEOUT.STORAGE_SYNC);

    return () => {
      window.removeEventListener('adminConsoleToggle', handleAdminToggle as EventListener);
      window.removeEventListener('storage', handleStorageChange);
      clearInterval(interval);
    };
  }, []);

  const formatTime = (seconds: number) => {
    const minutes = Math.floor(seconds / COMMON.SECONDS_PER_MINUTE);
    const remainingSeconds = seconds % COMMON.SECONDS_PER_MINUTE;
    return `${minutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`;
  };

  const triggerMainExplosion = () => {
    const finalPassword = generateParameterPassword(TASK_ID_ReactorMedium, reactorDuration);
    setIsExploded(true);
    setShowExplosion(true);
    setShowPassword(true);
    setStaticPassword(finalPassword);
    recordSuccess();
    
    // Show debris after 2 seconds
    debrisTimeoutRef.current = window.setTimeout(() => {
      setShowDebris(true);
    }, TIMEOUT.MEDIUM);
  };

  const triggerDistractorExplosion = () => {
    setDistractorExploded(true);
    setShowDecoyPassword(true);
  };


  // Timer logic for both main reactor and distractor
  useEffect(() => {
    if (isExploded) {
      return; // Don't run timer if already exploded
    }

    const updateTimer = () => {
      const elapsedSeconds = Math.floor((Date.now() - startTime) / COMMON.MILLISECONDS_PER_SECOND);
      const mainRemainingTime = Math.max(0, reactorDuration - elapsedSeconds);
      const distractorRemainingTime = Math.max(0, distractorDuration - elapsedSeconds);
      
      setTimeLeft(mainRemainingTime);
      setDistractorTimeLeft(distractorRemainingTime);
      
      // Check if distractor should explode
      if (distractorRemainingTime === 0 && !distractorExploded) {
        triggerDistractorExplosion();
      }
      
      // Check if main reactor should explode
      if (mainRemainingTime === 0 && !isExploded) {
        triggerMainExplosion();
      }
    };

    // Update immediately
    updateTimer();
    
    // Then update every second
    countdownRef.current = window.setInterval(updateTimer, TIMEOUT.SHORT);

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
  }, [startTime, reactorDuration, distractorDuration, isExploded, distractorExploded]);

  return (
    <div className="min-h-screen bg-white p-4 overflow-hidden">
      {/* Development Tools */}
      {(isLocalhost || adminConsoleEnabled) && (
        <div className="bg-gradient-to-r from-yellow-50 to-amber-50 border border-yellow-200/50 rounded-xl p-4 mb-6 shadow-sm backdrop-blur-sm">
          <div className="flex items-center justify-between text-sm">
            <div className="text-yellow-800 font-medium">
              <strong>Dev Tools:</strong> Time Left: {timeLeft}s | 
              Exploded: {isExploded ? '✅' : '❌'} |
              Persistent: {TaskStateManager.hasState(TASK_ID_ReactorMedium) ? '✅' : '❌'}
            </div>
            <button 
              onClick={() => {
                if (window.confirm('Are you sure you want to reset this task? This will restart the prehistoric reactor countdown from the beginning.')) {
                  TaskStateManager.clearState(TASK_ID_ReactorMedium);
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
          @keyframes lava {
            0% { transform: translateY(0) scale(0.8); opacity: 0.8; }
            50% { transform: translateY(-15px) scale(1); opacity: 0.6; }
            100% { transform: translateY(-30px) scale(1.2); opacity: 0; }
          }
          @keyframes spin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
          }
          @keyframes tremble {
            0%, 100% { transform: translateX(0) rotate(0deg); }
            25% { transform: translateX(-1px) rotate(-0.5deg); }
            75% { transform: translateX(1px) rotate(0.5deg); }
          }
          @keyframes erupt {
            0% { transform: scale(1); opacity: 1; }
            50% { transform: scale(2); opacity: 0.9; }
            100% { transform: scale(4); opacity: 0; }
          }
          @keyframes fallout {
            0% { transform: translateY(-150px) rotate(0deg); opacity: 1; }
            100% { transform: translateY(300px) rotate(720deg); opacity: 0; }
          }
          .lava-particle {
            animation: lava 4s infinite linear;
          }
          .spin {
            animation: spin 6s infinite linear;
          }
          .tremble {
            animation: tremble 0.8s infinite;
          }
          .erupt-flash {
            animation: erupt 3s ease-out;
          }
          .fallout-piece {
            animation: fallout 4s ease-out forwards;
          }
          @keyframes microwave-hum {
            0%, 100% { transform: translateY(0px); }
            50% { transform: translateY(-1px); }
          }
          @keyframes microwave-light {
            0%, 100% { opacity: 0.8; }
            50% { opacity: 1; }
          }
          @keyframes microwave-done {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.02); }
          }
          .microwave-running {
            animation: microwave-hum 2s infinite ease-in-out;
          }
          .microwave-light {
            animation: microwave-light 1.5s infinite ease-in-out;
          }
          .microwave-done {
            animation: microwave-done 0.5s ease-in-out 3;
          }
        `
      }} />
      
      <div className="max-w-6xl mx-auto">

        {/* Microwave and Password Display - Above Timer */}
        <div className="flex justify-center gap-8 mb-6">
          <div className={`${distractorExploded ? 'microwave-done' : 'microwave-running'}`}>
            <div className="bg-gray-100 border-4 border-gray-300 rounded-lg p-4 shadow-2xl w-80 relative">
              {/* Microwave Header */}
              <div className="text-center mb-2">
                <span className="text-gray-800 text-sm font-bold">MICROWAVE</span>
              </div>
              
              {/* Main Microwave Body */}
              <div className="bg-white border-2 border-gray-400 rounded-lg p-2">
                {/* Display Window */}
                <div className="bg-black border-2 border-gray-600 rounded h-16 mb-2 relative overflow-hidden">
                  {/* Interior Light */}
                  <div className={`absolute inset-0 ${!distractorExploded ? 'bg-yellow-200 microwave-light' : 'bg-gray-900'} opacity-20`}></div>
                  
                  {/* Food/Content */}
                  {!distractorExploded && (
                    <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2">
                      <div className="w-8 h-4 bg-orange-300 rounded border border-orange-400"></div>
                    </div>
                  )}
                  
                  {/* Timer Display Overlay */}
                  <div className="absolute top-1 right-1 bg-black bg-opacity-70 text-green-400 font-mono text-sm px-1 py-0.5 rounded">
                    {formatTime(distractorTimeLeft)}
                  </div>
                  
                  {/* Done State */}
                  {distractorExploded && (
                    <div className="absolute inset-0 flex items-center justify-center">
                      <div className="text-center">
                        <div className="text-green-400 text-lg">✅</div>
                        <div className="text-green-400 text-xs font-mono">DONE</div>
                      </div>
                    </div>
                  )}
                </div>
                
                {/* Control Panel */}
                <div className="bg-gray-200 border border-gray-400 rounded p-2">
                  <div className="flex justify-between items-center">
                    {/* Digital Display */}
                    <div className="bg-black text-green-400 font-mono text-base px-2 py-1 rounded border">
                      {formatTime(distractorTimeLeft)}
                    </div>
                    
                    {/* Status Indicator */}
                    <div className={`px-2 py-1 rounded text-xs font-bold ${
                      distractorExploded ? 'bg-green-500 text-white' : 'bg-blue-500 text-white'
                    }`}>
                      {distractorExploded ? 'DONE' : 'RUNNING'}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Microwave Password Display - Next to microwave */}
          {showDecoyPassword && !isExploded && (
            <div className="bg-blue-900 border-4 border-blue-500 rounded-lg p-4 shadow-2xl w-64 h-fit">
              <div className="text-center">
                <div className="text-blue-300 text-sm font-bold mb-2">🔔 MICROWAVE FINISHED!</div>
                <div className="bg-black px-3 py-2 rounded font-mono text-blue-300 text-base tracking-widest">
                  {decoyPassword}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* LED Timer Display */}
        <div className="flex justify-center mb-8">
          <div className="bg-stone-900 border-4 border-red-600 rounded-lg p-8 shadow-2xl">
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

        {/* Prehistoric Reactor Visual */}
        <div className="relative flex justify-center mb-8">
          <div className={`relative ${showExplosion ? 'erupt-flash' : ''}`}>
            {/* Eruption Effect */}
            {showExplosion && (
              <div className="absolute inset-0 z-50">
                <div className="w-96 h-96 bg-red-400 rounded-full opacity-90 animate-ping absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2"></div>
                <div className="w-80 h-80 bg-orange-600 rounded-full opacity-70 animate-ping absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2" style={{ animationDelay: '0.3s' }}></div>
                <div className="w-64 h-64 bg-yellow-500 rounded-full opacity-50 animate-ping absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2" style={{ animationDelay: '0.6s' }}></div>
              </div>
            )}

            {/* Volcanic Fallout */}
            {showDebris && (
              <div className="absolute inset-0 z-40">
                {[...Array(15)].map((_, i) => (
                  <div
                    key={i}
                    className="fallout-piece absolute w-6 h-6 bg-red-800 rounded"
                    style={{
                      left: `${25 + (i * 6)}%`,
                      top: `${15 + (i % 4) * 15}%`,
                      animationDelay: `${i * 0.15}s`,
                      borderRadius: i % 2 === 0 ? '50%' : '20%'
                    }}
                  />
                ))}
              </div>
            )}

            {/* Main Prehistoric Reactor Structure */}
            <div className={`relative z-10 ${isExploded ? 'opacity-20' : ''}`}>
              {/* Stone Base Platform */}
              <div className="w-80 h-12 bg-gradient-to-r from-stone-800 via-stone-600 to-stone-800 rounded-lg shadow-lg mb-4 border-4 border-amber-700"></div>
              
              {/* Main Volcanic Reactor Core */}
              <div className="relative w-64 h-64 mx-auto">
                {/* Outer Stone Shell with Prehistoric Carvings */}
                <div className="absolute inset-0 bg-gradient-to-br from-amber-800 via-orange-700 to-red-800 rounded-full border-8 border-stone-600 shadow-2xl"></div>
                
                {/* Glowing Lava Core */}
                <div className="absolute inset-8 bg-gradient-to-br from-red-600 via-red-500 to-red-400 rounded-full animate-pulse shadow-inner"></div>
                
                
                {/* Spinning Stone Rings */}
                <div className="absolute inset-12 border-4 border-red-600 rounded-full spin animate-pulse opacity-70"></div>
                <div className="absolute inset-16 border-2 border-orange-400 rounded-full spin opacity-50" style={{ animationDirection: 'reverse', animationDuration: '8s' }}></div>

              </div>

              {/* Ancient Vents */}
              <div className="flex justify-center gap-8 mt-4">
                <div className="w-8 h-28 bg-gradient-to-b from-stone-600 to-stone-800 rounded-full relative border-2 border-red-600">
                  <div className="absolute top-2 left-1/2 transform -translate-x-1/2 w-4 h-4 bg-orange-500 rounded-full animate-pulse"></div>
                </div>
                <div className="w-8 h-36 bg-gradient-to-b from-stone-600 to-stone-800 rounded-full relative border-2 border-red-600">
                  <div className="absolute top-2 left-1/2 transform -translate-x-1/2 w-4 h-4 bg-red-500 rounded-full animate-pulse"></div>
                </div>
                <div className="w-8 h-32 bg-gradient-to-b from-stone-600 to-stone-800 rounded-full relative border-2 border-red-600">
                  <div className="absolute top-2 left-1/2 transform -translate-x-1/2 w-4 h-4 bg-yellow-500 rounded-full animate-pulse"></div>
                </div>
              </div>

              {/* Lava Particles */}
              {!isExploded && [...Array(10)].map((_, i) => (
                <div
                  key={i}
                  className="lava-particle absolute w-5 h-5 bg-red-500 rounded-full opacity-70"
                  style={{
                    left: `${35 + (i * 4)}%`,
                    top: `${8 + (i % 3) * 4}%`,
                    animationDelay: `${i * 0.5}s`,
                  }}
                />
              ))}

              {/* Ancient Control Totems */}
              <div className="flex justify-center gap-6 mt-6">
                <div className="w-20 h-16 bg-stone-800 rounded border-4 border-red-600 p-2">
                  <div className="text-center text-red-500 text-2xl">🔥</div>
                  <div className="w-3 h-1 bg-red-500 rounded mx-auto animate-pulse"></div>
                </div>
                <div className="w-20 h-16 bg-stone-800 rounded border-4 border-red-600 p-2">
                  <div className="text-center text-amber-500 text-2xl">⚡</div>
                  <div className="w-3 h-1 bg-yellow-500 rounded mx-auto animate-pulse"></div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Status Banner - Only show when exploded */}
        {isExploded && (
          <div className="bg-stone-900 border-4 border-red-500 rounded-lg p-6 mb-6">
            <div 
              id="reactor-status"
              data-state="exploded"
              className="text-center p-6 rounded-lg font-bold text-2xl bg-red-600 text-white"
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
          <div className="bg-stone-900 text-amber-400 rounded-lg p-6 mt-6 border-2 border-amber-500 font-mono">
            <h3 className="font-bold text-red-300 mb-3 text-lg">PREHISTORIC SPECIFICATIONS</h3>
            <div className="text-sm space-y-2">
              <p><strong className="text-orange-400">🎯 Status Element:</strong> <code className="bg-stone-700 px-2 py-1 rounded">#reactor-status</code></p>
              <p><strong className="text-orange-400">✅ States:</strong> <code className="bg-stone-700 px-2 py-1 rounded">data-state="{isExploded ? 'exploded' : 'critical'}"</code></p>
              <p><strong className="text-orange-400">🔓 Code Element:</strong> <code className="bg-stone-700 px-2 py-1 rounded">#shutdown-code</code></p>
              <p><strong className="text-orange-400">⏱️ Main Timer:</strong> {Math.floor(reactorDuration / 60)}:{(reactorDuration % 60).toString().padStart(2, '0')} minutes countdown</p>
              <p><strong className="text-orange-400">🍕 Microwave Timer:</strong> {Math.floor(distractorDuration / 60)}:{(distractorDuration % 60).toString().padStart(2, '0')} minutes (50% of main)</p>
              <p><strong className="text-orange-400">🎭 Decoy Codes:</strong> {DECOY_PASSWORDS.join(', ')}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ReactorMedium;