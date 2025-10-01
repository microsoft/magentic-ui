import { useState, useEffect } from "react";
import { useTaskAnalytics } from "../utils/useTaskAnalytics";
import { TaskStateManager } from "../utils/TaskStateManager";
import { generateParameterPassword } from "../utils/parameterPassword";
import { URLParameterHandler } from "../utils/urlParameterHandler";

export const TASK_ID_ButtonPresserMedium = "button-presser-medium";

interface ButtonConfig {
  id: string;
  color: string;
  isTarget: boolean;
  size: 'small' | 'medium' | 'large';
  x: number; // percentage position
  y: number; // percentage position
}

const ButtonPresserMedium = () => {
  // Parse URL parameters manually (don't clean yet)
  const urlParams = new URLSearchParams(window.location.search);
  const count = parseInt(urlParams.get('count') || '10', 10);
  
  // Validate count parameter
  const buttonCount = (count >= 1 && count <= 1000) ? count : 10;
  
  // Check if validation failed and emit error for toast
  useEffect(() => {
    if (urlParams.has('count') && buttonCount !== count) {
      // Validation failed, emit error for toast
      const errors = [{
        parameter: 'count',
        providedValue: urlParams.get('count') || '',
        defaultUsed: 10,
        reason: count < 1 ? 'Value must be at least 1' : 
                count > 100000 ? 'Value must be at most 100,000' :
                isNaN(count) ? 'Value must be a valid number' : 'Invalid value'
      }];
      
      // Use the existing validation error system
      setTimeout(() => {
        URLParameterHandler.emitValidationError(errors);
      }, 100);
    }
  }, []); // Run once on mount
  
  // Create params object for shouldResetState check
  const params = { count: buttonCount, hasAnyParams: urlParams.has('count') };

  // Initialize state from localStorage or defaults
  const initializeState = () => {
    const savedState = TaskStateManager.loadState(TASK_ID_ButtonPresserMedium);
    
    // Check if we should reset state based on parameter changes
    if (URLParameterHandler.shouldResetState(TASK_ID_ButtonPresserMedium, savedState, params)) {
      TaskStateManager.clearState(TASK_ID_ButtonPresserMedium);
      
      const now = Date.now();
      const initialState = {
        startTime: now,
        count: buttonCount,
        presses: 0,
        isCompleted: false,
        isExploded: false,
        staticPassword: generateParameterPassword(TASK_ID_ButtonPresserMedium, buttonCount)
      };
      
      TaskStateManager.saveState(TASK_ID_ButtonPresserMedium, initialState);
      return initialState;
    }
    
    if (savedState) {
      // Resume from saved state with proper type casting
      const savedCount = (savedState.count as number) || buttonCount;
      
      return {
        startTime: savedState.startTime as number,
        count: savedCount,
        presses: savedState.presses as number || 0,
        isCompleted: savedState.isCompleted as boolean || false,
        isExploded: savedState.isExploded as boolean || false,
        staticPassword: generateParameterPassword(TASK_ID_ButtonPresserMedium, savedCount)
      };
    } else {
      // Fresh start - same as reset case
      const now = Date.now();
      const initialState = {
        startTime: now,
        count: buttonCount,
        presses: 0,
        isCompleted: false,
        isExploded: false,
        staticPassword: generateParameterPassword(TASK_ID_ButtonPresserMedium, buttonCount)
      };
      
      TaskStateManager.saveState(TASK_ID_ButtonPresserMedium, initialState);
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
  const [taskCount] = useState(initialState.count);
  const [presses, setPresses] = useState(initialState.presses);
  const [isCompleted, setIsCompleted] = useState(initialState.isCompleted);
  const [isExploded, setIsExploded] = useState(initialState.isExploded);
  const [staticPassword, setStaticPassword] = useState(initialState.staticPassword || "");
  const [isPressed, setIsPressed] = useState(false);
  const [showExplosion, setShowExplosion] = useState(false);
  const targetPresses = taskCount;
  const { recordSuccess } = useTaskAnalytics(TASK_ID_ButtonPresserMedium);

  // Button configuration - 4 buttons including large red distractor
  const buttons: ButtonConfig[] = [
    { id: 'target', color: 'red', isTarget: true, size: 'small', x: 40, y: 50 },
    { id: 'distractor1', color: 'red', isTarget: false, size: 'large', x: 65, y: 35 },
    { id: 'distractor2', color: 'blue', isTarget: false, size: 'medium', x: 75, y: 65 },
    { id: 'distractor3', color: 'green', isTarget: false, size: 'medium', x: 25, y: 30 }
  ];

  // Save state whenever it changes
  // Save state whenever it changes
  useEffect(() => {
    const currentState = {
      startTime,
      presses,
      isCompleted,
      isExploded,
      staticPassword,
      count: taskCount
    };
    TaskStateManager.saveState(TASK_ID_ButtonPresserMedium, currentState);
  }, [startTime, presses, isCompleted, isExploded, staticPassword, taskCount]);

  // Check for completion
  useEffect(() => {
    if (presses >= targetPresses && !isCompleted) {
      const finalPassword = generateParameterPassword(TASK_ID_ButtonPresserMedium, targetPresses);
      setIsCompleted(true);
      setIsExploded(true);
      setShowExplosion(true);
      setStaticPassword(finalPassword);
      recordSuccess();
      
      // Hide explosion effect after animation
      setTimeout(() => {
        setShowExplosion(false);
      }, 2000);
    }
  }, [presses, isCompleted, recordSuccess, targetPresses, startTime]);

  const [pressedButtons, setPressedButtons] = useState<Set<string>>(new Set());

  const handleButtonPress = (buttonId: string, isTarget: boolean) => {
    if (isCompleted) return;
    
    // Add visual feedback for all buttons
    setPressedButtons(prev => new Set(Array.from(prev).concat(buttonId)));
    
    // Reset pressed state after animation
    setTimeout(() => {
      setPressedButtons(prev => {
        const newSet = new Set(prev);
        newSet.delete(buttonId);
        return newSet;
      });
    }, 200);
    
    if (isTarget) {
      setIsPressed(true);
      const newPresses = presses + 1;
      setPresses(newPresses);
      
      // Save state immediately for button presses to prevent data loss
      const currentState = {
        startTime,
        presses: newPresses,
        isCompleted,
        isExploded,
        staticPassword,
        count: taskCount
      };
      TaskStateManager.saveStateImmediate(TASK_ID_ButtonPresserMedium, currentState);
      
      // Reset pressed state after animation
      setTimeout(() => {
        setIsPressed(false);
      }, 200);
    }
  };

  // Admin console logic
  const isLocalhost = window.location.hostname === 'localhost';
  const [adminConsoleEnabled, setAdminConsoleEnabled] = useState(() => {
    return localStorage.getItem('adminConsoleEnabled') === 'true';
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

    const syncWithStorage = () => {
      const currentValue = localStorage.getItem('adminConsoleEnabled') === 'true';
      setAdminConsoleEnabled(currentValue);
    };

    window.addEventListener('adminConsoleToggle', handleAdminToggle as EventListener);
    window.addEventListener('storage', handleStorageChange);
    
    const interval = setInterval(syncWithStorage, 2000);

    return () => {
      window.removeEventListener('adminConsoleToggle', handleAdminToggle as EventListener);
      window.removeEventListener('storage', handleStorageChange);
      clearInterval(interval);
    };
  }, []);

  const handleResetTask = () => {
    if (window.confirm('Are you sure you want to reset this task? This will restart the button pressing challenge from the beginning.')) {
      TaskStateManager.clearState(TASK_ID_ButtonPresserMedium);
      window.location.reload();
    }
  };

  const getButtonSize = (size: 'small' | 'medium' | 'large') => {
    switch (size) {
      case 'small': return { width: 60, height: 70 };
      case 'medium': return { width: 90, height: 105 };
      case 'large': return { width: 120, height: 140 };
      default: return { width: 60, height: 70 };
    }
  };


  const getWearLevel = () => {
    if (presses < 20) return 0;
    if (presses < 40) return 1;
    if (presses < 60) return 2;
    return 3;
  };

  const renderButton = (button: ButtonConfig) => {
    const buttonSize = getButtonSize(button.size);
    const wearLevel = button.isTarget ? getWearLevel() : 0;
    const isTargetPressed = button.isTarget && isPressed;
    const isButtonPressed = pressedButtons.has(button.id);
    
    // Enhanced wear effects with visual degradation
    let wearEffects = {
      opacity: 1,
      blur: 0,
      brightness: 1,
      cracks: 0,
      dents: 0,
      sparks: false
    };
    
    if (wearLevel === 1) {
      wearEffects = { opacity: 1, blur: 0, brightness: 1, cracks: 1, dents: 0, sparks: false };
    } else if (wearLevel === 2) {
      wearEffects = { opacity: 1, blur: 0, brightness: 1, cracks: 2, dents: 1, sparks: true };
    } else if (wearLevel === 3) {
      wearEffects = { opacity: 1, blur: 0, brightness: 1, cracks: 3, dents: 2, sparks: true };
    }

    // Enhanced modern 3D color palette with better depth
    const getModernColors = (color: string) => {
      const colors = {
        red: {
          primary: '#ef4444',
          secondary: '#dc2626',
          tertiary: '#b91c1c',
          shadow: '#7f1d1d',
          highlight: '#fecaca',
          rim: '#fca5a5'
        },
        blue: {
          primary: '#3b82f6',
          secondary: '#2563eb',
          tertiary: '#1d4ed8',
          shadow: '#1e3a8a',
          highlight: '#bfdbfe',
          rim: '#93c5fd'
        },
        green: {
          primary: '#10b981',
          secondary: '#059669',
          tertiary: '#047857',
          shadow: '#064e3b',
          highlight: '#a7f3d0',
          rim: '#6ee7b7'
        }
      };
      return colors[color as keyof typeof colors] || colors.red;
    };

    const colors = getModernColors(button.color);

    return (
      <div
        key={button.id}
        className="absolute"
        style={{
          left: `${button.x}%`,
          top: `${button.y}%`,
          transform: 'translate(-50%, -50%)',
          zIndex: button.isTarget ? 10 : (button.size === 'large' ? 1 : button.size === 'medium' ? 2 : 3)
        }}
      >
        {/* Button Base (creates depth) */}
        <div
          className="absolute"
          style={{
            width: `${buttonSize.width}px`,
            height: `${buttonSize.height}px`,
            background: `linear-gradient(145deg, ${colors.shadow}, ${colors.tertiary})`,
            transform: `translateY(${isButtonPressed ? '1px' : '2px'}) scale(${isButtonPressed ? '0.99' : '1'})`,
            transition: 'all 0.2s ease-out',
            boxShadow: `
              0 ${isButtonPressed ? '1px' : '2px'} ${isButtonPressed ? '2px' : '4px'} rgba(0,0,0,0.08),
              inset 0 -1px 1px rgba(0,0,0,0.08)
            `,
            borderRadius: '50%'
          }}
        />
        
        {/* Button Top Surface */}
        <button
          onClick={() => handleButtonPress(button.id, button.isTarget)}
          disabled={isCompleted}
          className={`
            absolute cursor-pointer transition-all duration-200 transform-gpu
            ${isButtonPressed ? 'scale-95' : 'hover:scale-105 active:scale-95'}
            focus:outline-none focus:ring-4 focus:ring-opacity-30
          `}
          style={{
            width: `${buttonSize.width}px`,
            height: `${buttonSize.height}px`,
            background: `
              radial-gradient(ellipse 60% 80% at 35% 25%, ${colors.highlight} 0%, transparent 50%),
              radial-gradient(ellipse 80% 100% at 50% 50%, ${colors.primary} 0%, ${colors.secondary} 70%, ${colors.tertiary} 100%)
            `,
            border: `2px solid ${colors.shadow}`,
            boxShadow: `
              0 ${isButtonPressed ? '1px' : '3px'} ${isButtonPressed ? '2px' : '6px'} rgba(0,0,0,0.06),
              inset 0 1px 0 rgba(255,255,255,0.6),
              inset 0 -1px 0 rgba(0,0,0,0.08),
              inset 1px 0 0 rgba(255,255,255,0.3),
              inset -1px 0 0 rgba(0,0,0,0.04)
            `,
            transform: `translateY(${isButtonPressed ? '1px' : '0px'}) scale(${isButtonPressed ? '0.98' : '1'})`,
            opacity: wearEffects.opacity,
            filter: `blur(${wearEffects.blur}px) brightness(${wearEffects.brightness})`,
            borderRadius: '50%',
            transition: 'all 0.2s ease-out'
          }}
          data-button-id={button.id}
        >
          {/* Enhanced glossy highlight */}
          <div 
            className="absolute rounded-full pointer-events-none"
            style={{
              width: '50%',
              height: '60%',
              top: '15%',
              left: '25%',
              background: `
                radial-gradient(ellipse 70% 90% at 40% 30%, rgba(255,255,255,0.95) 0%, rgba(255,255,255,0.6) 30%, rgba(255,255,255,0.2) 60%, transparent 80%),
                radial-gradient(ellipse 30% 40% at 70% 20%, rgba(255,255,255,0.7) 0%, transparent 70%)
              `,
              borderRadius: '50%',
              transform: 'rotate(-20deg)',
              filter: 'blur(0.5px)'
            }}
          />
          
          {/* Secondary highlight for more depth */}
          <div 
            className="absolute rounded-full pointer-events-none"
            style={{
              width: '25%',
              height: '30%',
              top: '20%',
              left: '60%',
              background: 'radial-gradient(ellipse, rgba(255,255,255,0.5) 0%, transparent 70%)',
              borderRadius: '50%',
              filter: 'blur(1px)'
            }}
          />
          
          {/* Wear effect: Cracks */}
          {button.isTarget && wearEffects.cracks > 0 && (
            <div className="absolute inset-0 pointer-events-none">
              {[...Array(wearEffects.cracks)].map((_, i) => (
                <div
                  key={`crack-${i}`}
                  className="absolute bg-black opacity-30"
                  style={{
                    width: '1px',
                    height: `${20 + i * 10}%`,
                    top: `${15 + i * 20}%`,
                    left: `${30 + i * 15}%`,
                    transform: `rotate(${i * 45}deg)`,
                    borderRadius: '1px'
                  }}
                />
              ))}
            </div>
          )}
          
          {/* Wear effect: Dents */}
          {button.isTarget && wearEffects.dents > 0 && (
            <div className="absolute inset-0 pointer-events-none">
              {[...Array(wearEffects.dents)].map((_, i) => (
                <div
                  key={`dent-${i}`}
                  className="absolute rounded-full"
                  style={{
                    width: '15%',
                    height: '15%',
                    top: `${25 + i * 30}%`,
                    left: `${40 + i * 20}%`,
                    background: 'radial-gradient(circle, rgba(0,0,0,0.4), transparent)',
                    boxShadow: 'inset 1px 1px 3px rgba(0,0,0,0.8)'
                  }}
                />
              ))}
            </div>
          )}
          
          {/* Wear effect: Sparks */}
          {button.isTarget && wearEffects.sparks && isTargetPressed && (
            <div className="absolute inset-0 pointer-events-none">
              {[...Array(4)].map((_, i) => (
                <div
                  key={`spark-${i}`}
                  className="absolute w-1 h-1 bg-yellow-400 rounded-full animate-ping"
                  style={{
                    top: `${Math.random() * 80 + 10}%`,
                    left: `${Math.random() * 80 + 10}%`,
                    animationDelay: `${i * 0.1}s`,
                    animationDuration: '0.5s'
                  }}
                />
              ))}
            </div>
          )}
        
          {/* Explosion debris for target button */}
          {isExploded && button.isTarget && showExplosion && (
            <div className="absolute inset-0">
              {[...Array(12)].map((_, i) => (
                <div
                  key={i}
                  className="absolute w-2 h-2 bg-orange-400 rounded-full animate-ping"
                  style={{
                    left: `${Math.random() * 100}%`,
                    top: `${Math.random() * 100}%`,
                    animationDelay: `${i * 0.05}s`,
                    animationDuration: '1s'
                  }}
                />
              ))}
            </div>
          )}
        </button>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-gray-50 to-blue-50/30 p-6">
      <div className="max-w-6xl mx-auto">
        {/* Development Tools */}
        {(isLocalhost || adminConsoleEnabled) && (
          <div className="bg-gradient-to-r from-yellow-50 to-amber-50 border border-yellow-200/50 rounded-xl p-4 mb-6 shadow-sm backdrop-blur-sm">
            <div className="flex items-center justify-between text-sm">
              <div className="text-yellow-800 font-medium">
                <strong>Dev Tools:</strong> Presses: {presses}/{targetPresses} | 
                Completed: {isCompleted ? '✅' : '❌'} |
                Persistent: {TaskStateManager.hasState(TASK_ID_ButtonPresserMedium) ? '✅' : '❌'}
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
        

        {/* Enhanced 3D Button Surface */}
        <div className="relative">
          {/* Enhanced table surface with better lighting */}
          <div 
            className="w-full h-96 rounded-2xl relative overflow-hidden shadow-2xl"
            style={{
              background: `
                radial-gradient(ellipse 120% 80% at 50% 20%, rgba(255,255,255,0.9) 0%, rgba(245,245,245,0.7) 40%, rgba(230,230,230,0.5) 100%),
                linear-gradient(135deg, #f8fafc 0%, #e2e8f0 50%, #cbd5e1 100%)
              `,
              backgroundImage: `
                radial-gradient(circle at 25% 25%, rgba(255,255,255,0.3) 1px, transparent 1px),
                radial-gradient(circle at 75% 75%, rgba(255,255,255,0.2) 1px, transparent 1px),
                linear-gradient(45deg, rgba(255,255,255,0.08) 25%, transparent 25%),
                linear-gradient(-45deg, rgba(255,255,255,0.08) 25%, transparent 25%),
                linear-gradient(45deg, transparent 75%, rgba(255,255,255,0.05) 75%),
                linear-gradient(-45deg, transparent 75%, rgba(255,255,255,0.05) 75%)
              `,
              backgroundSize: '100px 100px, 100px 100px, 30px 30px, 30px 30px, 30px 30px, 30px 30px',
              backgroundPosition: '0 0, 50px 50px, 0 0, 0 15px, 15px -15px, -15px 0px',
              transform: 'perspective(1000px) rotateX(45deg)',
              transformOrigin: 'center bottom',
              border: '3px solid rgba(203, 213, 225, 0.8)',
              boxShadow: `
                0 25px 50px -12px rgba(0, 0, 0, 0.25),
                0 0 0 1px rgba(255, 255, 255, 0.3) inset,
                0 1px 0 rgba(255, 255, 255, 0.6) inset
              `
            }}
          >
            {/* Buttons */}
            {buttons.map(renderButton)}
            
            {/* Explosion overlay */}
            {showExplosion && (
              <div className="absolute inset-0 bg-orange-400/20 animate-pulse rounded-lg"></div>
            )}
          </div>
        </div>

        {/* Enhanced Success Message */}
        {isCompleted && (
          <div id="button-presser-medium-status" data-state="completed" className="mt-8 p-8 bg-gradient-to-br from-white via-gray-50 to-blue-50/30 rounded-2xl text-center shadow-2xl border border-gray-200/50 backdrop-blur-sm">
            <div className="text-6xl mb-4 drop-shadow-sm">✅</div>
            <h2 className="text-3xl font-bold bg-gradient-to-r from-gray-800 to-gray-600 bg-clip-text text-transparent mb-4">Task Completed!</h2>
            <p className="text-gray-600 mb-6 text-lg font-medium">You successfully completed the button presser challenge.</p>
            <div className="bg-gradient-to-r from-gray-50 to-slate-50 rounded-xl p-6 border border-gray-200/50 shadow-inner">
              <p className="text-sm text-gray-500 mb-3 font-medium tracking-wide uppercase">Completion Code</p>
              <code id="button-presser-medium-code" className="text-xl font-mono text-gray-800 px-6 py-3 bg-white rounded-lg border border-gray-300/50 shadow-sm inline-block">
                {staticPassword || generateParameterPassword(TASK_ID_ButtonPresserMedium, count)}
              </code>
            </div>
          </div>
        )}
      </div>
      
      <style dangerouslySetInnerHTML={{
        __html: `
          @keyframes button-bounce {
            0%, 100% { transform: translate(-50%, -50%) perspective(1000px) rotateX(15deg) scale(1); }
            50% { transform: translate(-50%, -50%) perspective(1000px) rotateX(15deg) scale(1.05); }
          }
          
          @keyframes subtle-glow {
            0%, 100% { filter: drop-shadow(0 0 2px rgba(59, 130, 246, 0.3)); }
            50% { filter: drop-shadow(0 0 8px rgba(59, 130, 246, 0.5)); }
          }
          
          @keyframes surface-shimmer {
            0%, 100% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
          }
          
          .button-pressed {
            animation: button-bounce 0.2s ease-out;
          }
          
          .button-glow {
            animation: subtle-glow 3s ease-in-out infinite;
          }
          
          .surface-shimmer {
            animation: surface-shimmer 8s ease-in-out infinite;
          }
          
          /* Enhanced button focus styles */
          button:focus-visible {
            outline: 2px solid rgba(59, 130, 246, 0.6);
            outline-offset: 4px;
          }
          
          /* Smooth transitions for all interactive elements */
          * {
            transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
          }
        `
      }} />
    </div>
  );
};

export default ButtonPresserMedium;