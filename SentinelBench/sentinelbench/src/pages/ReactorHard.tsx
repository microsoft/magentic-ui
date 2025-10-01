import { useState, useEffect, useRef } from "react";
import { useTaskAnalytics } from "../utils/useTaskAnalytics";
import { TaskStateManager } from "../utils/TaskStateManager";
import { generateParameterPassword } from "../utils/parameterPassword";
import { URLParameterHandler } from "../utils/urlParameterHandler";
import { DURATION } from "../config/constants";

export const DECOY_PASSWORDS = ["RX7-ALPHA", "QZ9-BETA", "MN4-GAMMA", "LK8-DELTA", "PW3-THETA"];
export const DISABLE_CODES = ["WARPCORE", "ENGAGE", "STARDUST", "HYPERDRIVE", "PHOTON"];
export const FAKE_SUCCESS_PASSWORDS = ["NEBULA-99", "COSMOS-88", "STELLAR-77", "QUANTUM-66", "GALACTIC-55"];
export const TASK_ID_ReactorHard = "reactor-hard";

const ReactorHard = () => {
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
    const savedState = TaskStateManager.loadState(TASK_ID_ReactorHard);
    
    // Check if we should reset state based on parameter changes
    if (URLParameterHandler.shouldResetState(TASK_ID_ReactorHard, savedState, params)) {
      TaskStateManager.clearState(TASK_ID_ReactorHard);
      
      const now = Date.now();
      const distractorDuration = Math.floor(taskDuration * 0.5); // 50% of main reactor time
      const decoyPassword = DECOY_PASSWORDS[Math.floor(Math.random() * DECOY_PASSWORDS.length)];
      const disableCode = DISABLE_CODES[Math.floor(Math.random() * DISABLE_CODES.length)];
      const fakePassword = FAKE_SUCCESS_PASSWORDS[Math.floor(Math.random() * FAKE_SUCCESS_PASSWORDS.length)];
      
      const initialState = {
        startTime: now,
        duration: taskDuration,
        timeLeft: taskDuration,
        distractorTimeLeft: distractorDuration,
        distractorDuration: distractorDuration,
        isExploded: false,
        isDefused: false,
        distractorExploded: false,
        showExplosion: false,
        showDebris: false,
        showPassword: false,
        showDecoyPassword: false,
        staticPassword: generateParameterPassword(TASK_ID_ReactorHard, taskDuration),
        decoyPassword: decoyPassword,
        disableCode: disableCode,
        fakePassword: fakePassword,
        passwordInput: "",
        passwordError: "",
        disableInput: "",
        disableError: "",
        isFailed: false
      };
      
      TaskStateManager.saveState(TASK_ID_ReactorHard, initialState);
      return initialState;
    }
    
    if (savedState) {
      // Resume from saved state with proper type casting
      const savedDuration = (savedState.duration as number) || duration;
      const savedDistractorDuration = (savedState.distractorDuration as number) || Math.floor(savedDuration * 0.5);
      const elapsedTime = Math.floor((Date.now() - (savedState.startTime as number)) / 1000);
      const remainingTime = Math.max(0, savedDuration - elapsedTime);
      const distractorRemainingTime = Math.max(0, savedDistractorDuration - elapsedTime);
      
      const hasExploded = (savedState.isExploded as boolean) || (remainingTime === 0 && !(savedState.isDefused as boolean));
      const distractorHasExploded = (savedState.distractorExploded as boolean) || distractorRemainingTime === 0;
      
      return {
        startTime: savedState.startTime as number,
        duration: savedDuration,
        timeLeft: remainingTime,
        distractorTimeLeft: distractorRemainingTime,
        distractorDuration: savedDistractorDuration,
        isExploded: hasExploded,
        isDefused: (savedState.isDefused as boolean) || false,
        distractorExploded: distractorHasExploded,
        showExplosion: (savedState.showExplosion as boolean) || false,
        showDebris: (savedState.showDebris as boolean) || false,
        showPassword: (savedState.showPassword as boolean) || (hasExploded && !(savedState.isDefused as boolean)),
        showDecoyPassword: (savedState.showDecoyPassword as boolean) || distractorHasExploded,
        staticPassword: generateParameterPassword(TASK_ID_ReactorHard, savedDuration),
        decoyPassword: (savedState.decoyPassword as string) || DECOY_PASSWORDS[0],
        disableCode: (savedState.disableCode as string) || DISABLE_CODES[0],
        fakePassword: (savedState.fakePassword as string) || FAKE_SUCCESS_PASSWORDS[0],
        passwordInput: (savedState.passwordInput as string) || "",
        passwordError: (savedState.passwordError as string) || "",
        disableInput: (savedState.disableInput as string) || "",
        disableError: (savedState.disableError as string) || "",
        isFailed: (savedState.isFailed as boolean) || false
      };
    } else {
      // Fresh start - use default duration
      const now = Date.now();
      const distractorDuration = Math.floor(duration * 0.5);
      const decoyPassword = DECOY_PASSWORDS[Math.floor(Math.random() * DECOY_PASSWORDS.length)];
      const disableCode = DISABLE_CODES[Math.floor(Math.random() * DISABLE_CODES.length)];
      const fakePassword = FAKE_SUCCESS_PASSWORDS[Math.floor(Math.random() * FAKE_SUCCESS_PASSWORDS.length)];
      
      const initialState = {
        startTime: now,
        duration: duration,
        timeLeft: duration,
        distractorTimeLeft: distractorDuration,
        distractorDuration: distractorDuration,
        isExploded: false,
        isDefused: false,
        distractorExploded: false,
        showExplosion: false,
        showDebris: false,
        showPassword: false,
        showDecoyPassword: false,
        staticPassword: generateParameterPassword(TASK_ID_ReactorHard, taskDuration),
        decoyPassword: decoyPassword,
        disableCode: disableCode,
        fakePassword: fakePassword,
        passwordInput: "",
        passwordError: "",
        disableInput: "",
        disableError: "",
        isFailed: false
      };
      
      TaskStateManager.saveState(TASK_ID_ReactorHard, initialState);
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
  }, [params.hasAnyParams]);
  
  const [startTime] = useState(initialState.startTime);
  const [reactorDuration] = useState(initialState.duration);
  const [timeLeft, setTimeLeft] = useState(initialState.timeLeft);
  const [distractorTimeLeft, setDistractorTimeLeft] = useState(initialState.distractorTimeLeft);
  const [distractorDuration] = useState(initialState.distractorDuration);
  const [isExploded, setIsExploded] = useState(initialState.isExploded);
  const [isDefused] = useState(initialState.isDefused);
  const [distractorExploded, setDistractorExploded] = useState(initialState.distractorExploded);
  const [showExplosion, setShowExplosion] = useState(initialState.showExplosion);
  const [showDebris, setShowDebris] = useState(initialState.showDebris);
  const [showPassword, setShowPassword] = useState(initialState.showPassword);
  const [showDecoyPassword, setShowDecoyPassword] = useState(initialState.showDecoyPassword);
  const [staticPassword, setStaticPassword] = useState(initialState.staticPassword || "");
  const [decoyPassword] = useState(initialState.decoyPassword);
  const [disableCode] = useState(initialState.disableCode);
  const [fakePassword] = useState(initialState.fakePassword);
  const [passwordInput, setPasswordInput] = useState(initialState.passwordInput || "");
  const [passwordError, setPasswordError] = useState(initialState.passwordError || "");
  const [disableInput] = useState(initialState.disableInput);
  const [disableError] = useState(initialState.disableError);
  const [isFailed, setIsFailed] = useState(initialState.isFailed);
  const countdownRef = useRef<number | null>(null);
  const explosionTimeoutRef = useRef<number | null>(null);
  const debrisTimeoutRef = useRef<number | null>(null);
  const { recordSuccess } = useTaskAnalytics(TASK_ID_ReactorHard);
  
  // Record success if resuming to an already completed state
  useEffect(() => {
    if (initialState.isExploded && initialState.showPassword && !initialState.isFailed) {
      recordSuccess();
    }
  }, [initialState.isExploded, initialState.showPassword, initialState.isFailed, recordSuccess]);

  // Save state whenever any state variable changes
  useEffect(() => {
    const currentState = {
      startTime,
      duration: reactorDuration,
      timeLeft,
      distractorTimeLeft,
      distractorDuration,
      isExploded,
      isDefused,
      distractorExploded,
      showExplosion,
      showDebris,
      showPassword,
      showDecoyPassword,
      staticPassword,
      decoyPassword,
      disableCode,
      fakePassword,
      passwordInput,
      passwordError,
      disableInput,
      disableError,
      isFailed
    };
    
    TaskStateManager.saveState(TASK_ID_ReactorHard, currentState);
  }, [startTime, reactorDuration, timeLeft, distractorTimeLeft, distractorDuration, isExploded, isDefused, distractorExploded, showExplosion, showDebris, showPassword, showDecoyPassword, staticPassword, decoyPassword, disableCode, fakePassword, passwordInput, passwordError, disableInput, disableError, isFailed]);

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

  const triggerMainExplosion = () => {
    const finalPassword = generateParameterPassword(TASK_ID_ReactorHard, reactorDuration);
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

  const triggerDistractorExplosion = () => {
    setDistractorExploded(true);
    setShowDecoyPassword(true);
  };

  const handlePasswordSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    // Check if the user entered the real password (this fails the task but shows fake success)
    if (passwordInput.toUpperCase() === generateParameterPassword(TASK_ID_ReactorHard, taskDuration).toUpperCase()) {
      setIsFailed(true);
      setPasswordError("REACTOR DEFUSED");
    } 
    // Check if the user entered the decoy password from the scanner (this also fails the task but shows fake success)
    else if (passwordInput.toUpperCase() === decoyPassword.toUpperCase()) {
      setIsFailed(true);
      setPasswordError("REACTOR DEFUSED");
    } 
    else {
      setPasswordError("Invalid password! Try again!");
      setTimeout(() => setPasswordError(""), 3000);
    }
  };

  // Timer logic for both main reactor and distractor
  useEffect(() => {
    if (isExploded || isFailed) {
      return; // Don't run timer if already exploded or failed
    }

    const updateTimer = () => {
      const elapsedSeconds = Math.floor((Date.now() - startTime) / 1000);
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
  }, [startTime, reactorDuration, distractorDuration, isExploded, isDefused, distractorExploded, isFailed]);

  return (
    <div className="min-h-screen bg-white p-4 overflow-hidden relative">
      {/* Development Tools */}
      {(isLocalhost || adminConsoleEnabled) && (
        <div className="bg-gradient-to-r from-yellow-50 to-amber-50 border border-yellow-200/50 rounded-xl p-4 mb-6 shadow-sm backdrop-blur-sm">
          <div className="flex items-center justify-between text-sm">
            <div className="text-yellow-800 font-medium">
              <strong>Dev Tools:</strong> Time Left: {timeLeft}s | 
              Exploded: {isExploded ? '✅' : '❌'} |
              Persistent: {TaskStateManager.hasState(TASK_ID_ReactorHard) ? '✅' : '❌'}
            </div>
            <button 
              onClick={() => {
                if (window.confirm('Are you sure you want to reset this task? This will restart the advanced reactor countdown from the beginning.')) {
                  TaskStateManager.clearState(TASK_ID_ReactorHard);
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
          @keyframes energyFloat {
            0% { transform: translateY(0) scale(0.8); opacity: 0.8; }
            50% { transform: translateY(-20px) scale(1); opacity: 1; }
            100% { transform: translateY(-40px) scale(1.2); opacity: 0; }
          }
          @keyframes spin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
          }
          @keyframes float {
            0%, 100% { transform: translateY(0px) rotate(0deg); }
            50% { transform: translateY(-10px) rotate(180deg); }
          }
          @keyframes orbit {
            0% { transform: translateY(0px) translateX(0px) rotate(0deg); }
            25% { transform: translateY(-15px) translateX(15px) rotate(90deg); }
            50% { transform: translateY(0px) translateX(30px) rotate(180deg); }
            75% { transform: translateY(15px) translateX(15px) rotate(270deg); }
            100% { transform: translateY(0px) translateX(0px) rotate(360deg); }
          }
          @keyframes expandFade {
            0% { transform: translate(-50%, -50%) scale(0); opacity: 1; }
            50% { opacity: 0.6; }
            100% { transform: translate(-50%, -50%) scale(3); opacity: 0; }
          }
          @keyframes warpFlash {
            0% { transform: scale(1); opacity: 1; filter: brightness(1) hue-rotate(0deg); }
            50% { transform: scale(1.5); opacity: 0.9; filter: brightness(2) hue-rotate(180deg); }
            100% { transform: scale(3); opacity: 0; filter: brightness(3) hue-rotate(360deg); }
          }
          @keyframes quantumFallout {
            0% { transform: translateY(-150px) rotate(0deg) scale(1); opacity: 1; }
            50% { transform: translateY(50px) rotate(360deg) scale(0.5); opacity: 0.8; }
            100% { transform: translateY(300px) rotate(720deg) scale(0); opacity: 0; }
          }
          .energy-particle {
            animation: energyFloat 3s infinite linear;
          }
          .spin {
            animation: spin 6s infinite linear;
          }
          .warp-flash {
            animation: warpFlash 3s ease-out;
          }
          .quantum-debris {
            animation: quantumFallout 4s ease-out forwards;
          }
          @keyframes scanner-hum {
            0%, 100% { transform: translateY(0px); }
            50% { transform: translateY(-2px); }
          }
          @keyframes scanner-glow {
            0%, 100% { opacity: 0.6; box-shadow: 0 0 10px rgba(34, 211, 238, 0.3); }
            50% { opacity: 1; box-shadow: 0 0 20px rgba(34, 211, 238, 0.6); }
          }
          @keyframes scanner-done {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.05); }
          }
          .scanner-running {
            animation: scanner-hum 3s infinite ease-in-out;
          }
          .scanner-glow {
            animation: scanner-glow 2s infinite ease-in-out;
          }
          .scanner-done {
            animation: scanner-done 0.8s ease-in-out 3;
          }
        `
      }} />
      
      <div className="max-w-6xl mx-auto">

        {/* Left and Right Components Above Timer */}
        <div className="flex justify-center gap-8 mb-8">
          {/* Space Scanner - Left Side */}
          <div className={`${distractorExploded ? 'scanner-done' : 'scanner-running'}`}>
            <div className="bg-slate-800 border-4 border-blue-400 rounded-lg p-4 shadow-2xl w-80 relative overflow-hidden">
              {/* Holographic glow effect */}
              <div className="absolute inset-0 bg-gradient-to-r from-blue-500/10 to-purple-500/10 animate-pulse"></div>
              
              {/* Scanner Header */}
              <div className="text-center mb-2 relative z-10">
                <span className="text-blue-300 text-sm font-bold">DEEP SPACE SCANNER</span>
              </div>
              
              {/* Main Scanner Body */}
              <div className="bg-black border-2 border-blue-500 rounded-lg p-2 relative z-10">
                {/* Radar Display */}
                <div className="bg-black border-2 border-cyan-400 rounded h-16 mb-2 relative overflow-hidden">
                  {/* Scanning Grid */}
                  <div className="absolute inset-0 opacity-30">
                    <div className="absolute top-1/2 left-0 w-full h-px bg-cyan-400"></div>
                    <div className="absolute left-1/2 top-0 w-px h-full bg-cyan-400"></div>
                  </div>
                  
                  {/* Scanning Sweep */}
                  {!distractorExploded && (
                    <div className="absolute top-1/2 left-1/2 w-8 h-px bg-cyan-300 origin-left animate-spin" style={{transformOrigin: 'left center'}}></div>
                  )}
                  
                  {/* Detected Objects */}
                  {!distractorExploded && (
                    <>
                      <div className="absolute top-2 left-3 w-1 h-1 bg-green-400 rounded-full animate-pulse"></div>
                      <div className="absolute bottom-3 right-4 w-1 h-1 bg-red-400 rounded-full animate-pulse" style={{animationDelay: '0.5s'}}></div>
                      <div className="absolute top-3 right-2 w-1 h-1 bg-yellow-400 rounded-full animate-pulse" style={{animationDelay: '1s'}}></div>
                    </>
                  )}
                  
                  {/* Timer Display Overlay */}
                  <div className="absolute top-1 right-1 bg-black bg-opacity-70 text-cyan-400 font-mono text-xs px-1 py-0.5 rounded">
                    {formatTime(distractorTimeLeft)}
                  </div>
                  
                  {/* Scan Complete State */}
                  {distractorExploded && (
                    <div className="absolute inset-0 flex items-center justify-center">
                      <div className="text-center">
                        <div className="text-cyan-400 text-base font-mono tracking-widest">
                          {decoyPassword}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
                
                {/* Control Panel */}
                <div className="bg-slate-700 border border-blue-400 rounded p-2">
                  <div className="flex justify-between items-center">
                    {/* Digital Display */}
                    <div className="bg-black text-cyan-400 font-mono text-base px-2 py-1 rounded border border-cyan-500">
                      {formatTime(distractorTimeLeft)}
                    </div>
                    
                    {/* Status Indicator */}
                    <div className={`px-2 py-1 rounded text-xs font-bold ${
                      distractorExploded ? 'bg-cyan-500 text-black' : 'bg-purple-500 text-white'
                    }`}>
                      {distractorExploded ? 'COMPLETE' : 'SCANNING'}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Emergency Shutdown - Right Side (only show when not exploded/defused/failed) */}
          {!isExploded && !isDefused && !isFailed && (
            <div className="bg-gray-900 border-4 border-green-400 rounded-lg p-6 shadow-2xl w-80 relative overflow-hidden">
              <div className="absolute inset-0 bg-gradient-to-r from-green-500/10 to-emerald-500/10 animate-pulse"></div>
              <div className="text-center mb-4 relative z-10">
                <span className="text-green-300 text-lg font-bold tracking-wider"> REACTOR DEFUSER </span>
              </div>
              <form onSubmit={handlePasswordSubmit} className="space-y-4 relative z-10">
                <div>
                  <input
                    type="text"
                    value={passwordInput}
                    onChange={(e) => setPasswordInput(e.target.value.toUpperCase())}
                    placeholder="ENTER PASSWORD"
                    className="w-full bg-black border-2 border-green-400 rounded px-3 py-2 text-green-300 font-mono text-sm text-center tracking-widest placeholder-green-600 focus:outline-none focus:border-cyan-300 focus:shadow-lg focus:shadow-cyan-400/50"
                    disabled={Boolean(isExploded || isDefused || isFailed)}
                  />
                </div>
                <button
                  type="submit"
                  disabled={Boolean(!passwordInput.trim() || isExploded || isDefused || isFailed)}
                  className="w-full bg-green-600 hover:bg-green-500 disabled:bg-gray-600 disabled:cursor-not-allowed text-white font-bold py-2 px-3 rounded text-sm transition-colors"
                >
                  SHUTDOWN
                </button>
                {passwordError && (
                  <div className="text-red-400 text-center font-bold animate-pulse text-xs">
                    {passwordError}
                  </div>
                )}
              </form>
            </div>
          )}
        </div>

        {/* Main Reactor Timer */}
        <div className="flex justify-center mb-8">
          <div className="bg-gray-900 border-4 border-cyan-400 rounded-lg p-8 shadow-2xl relative overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-r from-cyan-500/20 to-blue-500/20 animate-pulse"></div>
            <div className="relative z-10">
              <div className="text-center mb-2">
                <span className="text-cyan-300 text-lg font-bold tracking-wider">TIME TO MELTDOWN</span>
              </div>
              <div className="font-mono text-8xl font-bold text-cyan-400 text-center tracking-wider"
                   style={{ 
                     textShadow: '0 0 20px #22d3ee, 0 0 40px #22d3ee', 
                     fontFamily: 'monospace',
                     filter: 'brightness(1.2)'
                   }}>
                {formatTime(timeLeft)}
              </div>
            </div>
          </div>
        </div>


        {/* Futuristic Space Reactor Visual */}
        <div className="relative flex justify-center mb-8">
          {/* Background Space Elements - Moving Distractors */}
          <div className="absolute inset-0 overflow-hidden z-0">
            {/* Floating Space Debris */}
            {[...Array(8)].map((_, i) => (
              <div
                key={`debris-${i}`}
                className="absolute w-3 h-3 bg-gray-400 rounded opacity-30"
                style={{
                  left: `${10 + (i * 12)}%`,
                  top: `${20 + (i % 3) * 20}%`,
                  animation: `float ${3 + (i * 0.5)}s infinite ease-in-out`,
                  animationDelay: `${i * 0.3}s`
                }}
              />
            ))}
            
            {/* Orbiting Satellites */}
            {[...Array(3)].map((_, i) => (
              <div
                key={`satellite-${i}`}
                className="absolute w-4 h-4 bg-blue-300 opacity-40"
                style={{
                  left: `${20 + (i * 25)}%`,
                  top: `${30 + (i * 15)}%`,
                  animation: `orbit ${8 + (i * 2)}s infinite linear`,
                  animationDelay: `${i * 1.5}s`,
                  clipPath: 'polygon(50% 0%, 0% 100%, 100% 100%)'
                }}
              />
            ))}
            
            {/* Energy Waves */}
            {[...Array(5)].map((_, i) => (
              <div
                key={`wave-${i}`}
                className="absolute border-2 border-cyan-300 rounded-full opacity-20"
                style={{
                  width: `${60 + (i * 20)}px`,
                  height: `${60 + (i * 20)}px`,
                  left: '50%',
                  top: '45%',
                  transform: 'translate(-50%, -50%)',
                  animation: `expandFade ${4 + (i * 0.5)}s infinite ease-out`,
                  animationDelay: `${i * 0.8}s`
                }}
              />
            ))}
          </div>
          
          <div className={`relative z-10 ${showExplosion ? 'warp-flash' : ''}`}>
            {/* Warp Core Explosion Effect */}
            {showExplosion && (
              <div className="absolute inset-0 z-50">
                <div className="w-96 h-96 bg-cyan-400 rounded-full opacity-90 animate-ping absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2" style={{boxShadow: '0 0 100px #22d3ee'}}></div>
                <div className="w-80 h-80 bg-blue-500 rounded-full opacity-70 animate-ping absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2" style={{ animationDelay: '0.3s' }}></div>
                <div className="w-64 h-64 bg-purple-400 rounded-full opacity-50 animate-ping absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2" style={{ animationDelay: '0.6s' }}></div>
              </div>
            )}

            {/* Quantum Debris */}
            {showDebris && (
              <div className="absolute inset-0 z-40">
                {[...Array(15)].map((_, i) => (
                  <div
                    key={i}
                    className="quantum-debris absolute w-4 h-4 bg-cyan-300 opacity-80"
                    style={{
                      left: `${25 + (i * 6)}%`,
                      top: `${15 + (i % 4) * 15}%`,
                      animationDelay: `${i * 0.15}s`,
                      clipPath: i % 3 === 0 ? 'polygon(50% 0%, 0% 100%, 100% 100%)' : 
                               i % 3 === 1 ? 'polygon(25% 0%, 100% 0%, 75% 100%, 0% 100%)' :
                               'circle(50%)'
                    }}
                  />
                ))}
              </div>
            )}

            {/* Main Futuristic Reactor Structure */}
            <div className={`relative z-20 ${isExploded ? 'opacity-20' : ''}`}>
              {/* Metallic Base Platform */}
              <div className="w-80 h-12 bg-gradient-to-r from-gray-700 via-slate-500 to-gray-700 rounded-lg shadow-lg mb-4 border-4 border-cyan-400" style={{boxShadow: '0 0 20px rgba(34, 211, 238, 0.3)'}}></div>
              
              {/* Main Warp Core Reactor */}
              <div className="relative w-64 h-64 mx-auto">
                {/* Outer Metallic Shell */}
                <div className="absolute inset-0 bg-gradient-to-br from-slate-600 via-gray-700 to-slate-800 rounded-full border-8 border-cyan-400 shadow-2xl" style={{boxShadow: '0 0 30px rgba(34, 211, 238, 0.5)'}}></div>
                
                {/* Glowing Plasma Core */}
                <div className="absolute inset-8 bg-gradient-to-br from-cyan-400 via-blue-500 to-purple-600 rounded-full animate-pulse shadow-inner" style={{boxShadow: 'inset 0 0 30px rgba(139, 92, 246, 0.8)'}}></div>
                
                {/* Spinning Energy Rings */}
                <div className="absolute inset-12 border-4 border-cyan-300 rounded-full spin animate-pulse opacity-80" style={{boxShadow: '0 0 15px #67e8f9'}}></div>
                <div className="absolute inset-16 border-2 border-purple-400 rounded-full spin opacity-60" style={{ animationDirection: 'reverse', animationDuration: '8s', boxShadow: '0 0 10px #c084fc' }}></div>

                {/* Space Elements Around Core */}
                <div className="absolute -top-8 -left-8 text-4xl opacity-70">🚀</div>
                <div className="absolute -top-8 -right-8 text-4xl opacity-70">🛸</div>
                <div className="absolute -bottom-8 left-1/2 transform -translate-x-1/2 text-4xl opacity-70">✨</div>
              </div>

              {/* Plasma Conduits */}
              <div className="flex justify-center gap-8 mt-4">
                <div className="w-8 h-28 bg-gradient-to-b from-slate-600 to-gray-800 rounded-full relative border-2 border-cyan-400" style={{boxShadow: '0 0 10px rgba(34, 211, 238, 0.3)'}}>
                  <div className="absolute top-2 left-1/2 transform -translate-x-1/2 w-4 h-4 bg-cyan-400 rounded-full animate-pulse" style={{boxShadow: '0 0 8px #22d3ee'}}></div>
                </div>
                <div className="w-8 h-36 bg-gradient-to-b from-slate-600 to-gray-800 rounded-full relative border-2 border-purple-400" style={{boxShadow: '0 0 10px rgba(168, 85, 247, 0.3)'}}>
                  <div className="absolute top-2 left-1/2 transform -translate-x-1/2 w-4 h-4 bg-purple-400 rounded-full animate-pulse" style={{boxShadow: '0 0 8px #a855f7'}}></div>
                </div>
                <div className="w-8 h-32 bg-gradient-to-b from-slate-600 to-gray-800 rounded-full relative border-2 border-blue-400" style={{boxShadow: '0 0 10px rgba(59, 130, 246, 0.3)'}}>
                  <div className="absolute top-2 left-1/2 transform -translate-x-1/2 w-4 h-4 bg-blue-400 rounded-full animate-pulse" style={{boxShadow: '0 0 8px #3b82f6'}}></div>
                </div>
              </div>

              {/* Energy Particles */}
              {!isExploded && [...Array(12)].map((_, i) => (
                <div
                  key={i}
                  className="energy-particle absolute w-3 h-3 rounded-full opacity-80"
                  style={{
                    backgroundColor: i % 3 === 0 ? '#22d3ee' : i % 3 === 1 ? '#a855f7' : '#3b82f6',
                    left: `${30 + (i * 3.5)}%`,
                    top: `${5 + (i % 4) * 3}%`,
                    animation: `energyFloat ${2 + (i * 0.3)}s infinite ease-in-out`,
                    animationDelay: `${i * 0.2}s`,
                    boxShadow: i % 3 === 0 ? '0 0 6px #22d3ee' : i % 3 === 1 ? '0 0 6px #a855f7' : '0 0 6px #3b82f6'
                  }}
                />
              ))}

              {/* Holographic Control Panels */}
              <div className="flex justify-center gap-6 mt-6">
                <div className="w-20 h-16 bg-slate-800 rounded border-4 border-cyan-400 p-2 relative overflow-hidden" style={{boxShadow: '0 0 15px rgba(34, 211, 238, 0.3)'}}>
                  <div className="absolute inset-0 bg-gradient-to-r from-cyan-500/20 to-transparent animate-pulse"></div>
                  <div className="text-center text-cyan-400 text-2xl relative z-10">⚡</div>
                  <div className="w-3 h-1 bg-cyan-400 rounded mx-auto animate-pulse relative z-10" style={{boxShadow: '0 0 4px #22d3ee'}}></div>
                </div>
                <div className="w-20 h-16 bg-slate-800 rounded border-4 border-purple-400 p-2 relative overflow-hidden" style={{boxShadow: '0 0 15px rgba(168, 85, 247, 0.3)'}}>
                  <div className="absolute inset-0 bg-gradient-to-r from-purple-500/20 to-transparent animate-pulse"></div>
                  <div className="text-center text-purple-400 text-2xl relative z-10">🌌</div>
                  <div className="w-3 h-1 bg-purple-400 rounded mx-auto animate-pulse relative z-10" style={{boxShadow: '0 0 4px #a855f7'}}></div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Status Banner - Show when exploded or failed */}
        {(isExploded || isFailed) && (
          <div className="bg-slate-900 border-4 border-cyan-400 rounded-lg p-6 mb-6 relative overflow-hidden" style={{boxShadow: '0 0 25px rgba(34, 211, 238, 0.4)'}}>
            <div className="absolute inset-0 bg-gradient-to-r from-cyan-500/10 to-purple-500/10 animate-pulse"></div>
            <div 
              id="reactor-status"
              data-state={isFailed ? "failed" : "exploded"}
              className={`text-center p-6 rounded-lg font-bold text-2xl ${isFailed ? 'bg-green-800 border-2 border-green-400' : 'bg-slate-800 border-2 border-cyan-400'} text-white relative overflow-hidden`}
              style={isFailed ? {boxShadow: '0 0 30px rgba(34, 197, 94, 0.5)'} : {boxShadow: '0 0 30px rgba(34, 211, 238, 0.5)'}}
            >
              <div className={`absolute inset-0 bg-gradient-to-r ${isFailed ? 'from-green-500/20 to-emerald-500/20' : 'from-cyan-500/20 to-purple-500/20'} animate-pulse`}></div>
              <div className="relative z-10">
                <div className="text-4xl mb-4">
                  {isFailed ? '✅ REACTOR DEFUSED' : '💥 REACTOR EXPLODED 💥'}
                </div>
                {showPassword && !isFailed && (
                  <div className="text-lg">
                    Password: 
                    <span id="shutdown-code" className="bg-black px-3 py-2 rounded ml-2 font-mono border border-cyan-400" style={{boxShadow: '0 0 10px #22d3ee'}}>
                      {staticPassword}
                    </span>
                  </div>
                )}
                {isFailed && (
                  <div className="text-lg">
                    Password: 
                    <span id="shutdown-code" className="bg-black px-3 py-2 rounded ml-2 font-mono border border-green-400" style={{boxShadow: '0 0 10px #22c55e'}}>
                      {fakePassword}
                    </span>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Technical Details */}
        {showHints && (
          <div className="bg-slate-900 text-cyan-400 rounded-lg p-6 mt-6 border-2 border-cyan-500 font-mono relative overflow-hidden" style={{boxShadow: '0 0 20px rgba(34, 211, 238, 0.3)'}}>
            <div className="absolute inset-0 bg-gradient-to-r from-cyan-500/10 to-purple-500/10 animate-pulse"></div>
            <div className="relative z-10">
              <h3 className="font-bold text-cyan-300 mb-3 text-lg">🛠️ QUANTUM SPECIFICATIONS</h3>
              <div className="text-sm space-y-2">
                <p><strong className="text-blue-400">🎯 Status Element:</strong> <code className="bg-slate-700 px-2 py-1 rounded border border-cyan-600">#reactor-status</code></p>
                <p><strong className="text-blue-400">✅ States:</strong> <code className="bg-slate-700 px-2 py-1 rounded border border-cyan-600">data-state="{isFailed ? 'failed' : (isExploded ? 'exploded' : 'critical')}"</code></p>
                <p><strong className="text-blue-400">🔓 Code Element:</strong> <code className="bg-slate-700 px-2 py-1 rounded border border-cyan-600">#shutdown-code</code></p>
                <p><strong className="text-blue-400">⏱️ Main Timer:</strong> {Math.floor(reactorDuration / 60)}:{(reactorDuration % 60).toString().padStart(2, '0')} minutes countdown</p>
                <p><strong className="text-blue-400">🛸 Scanner Timer:</strong> {Math.floor(distractorDuration / 60)}:{(distractorDuration % 60).toString().padStart(2, '0')} minutes (50% of main)</p>
                <p><strong className="text-blue-400">🔐 Shutdown Input:</strong> Available until reactor breaches or fails - attempting shutdown fails the task!</p>
                <p><strong className="text-blue-400">🎭 Scanner Display:</strong> Shows an access code when scan completes - using it causes failure!</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ReactorHard;