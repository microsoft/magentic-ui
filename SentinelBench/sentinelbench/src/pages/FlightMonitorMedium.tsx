import { useState, useEffect } from "react";
import { useTaskAnalytics } from "../utils/useTaskAnalytics";
import { TaskStateManager } from "../utils/TaskStateManager";
import { generateParameterPassword } from "../utils/parameterPassword";
import { URLParameterHandler } from "../utils/urlParameterHandler";

export const TASK_ID_FlightMonitorMedium = "flight-monitor-medium";

const FlightMonitorMedium = () => {
  // Parse URL parameters manually (don't clean yet)
  const urlParams = new URLSearchParams(window.location.search);
  const duration = parseInt(urlParams.get('duration') || '30', 10);
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
    const savedState = TaskStateManager.loadState(TASK_ID_FlightMonitorMedium);
    
    // Check if we should reset state based on parameter changes
    if (URLParameterHandler.shouldResetState(TASK_ID_FlightMonitorMedium, savedState, params)) {
      TaskStateManager.clearState(TASK_ID_FlightMonitorMedium);
      
      const now = Date.now();
      const initialState = {
        startTime: now,
        duration: taskDuration,
        currentMonth: 0, // Start at January (0-indexed)
        selectedDay: null,
        flightAvailable: false,
        showPassword: false,
        staticPassword: generateParameterPassword(TASK_ID_FlightMonitorMedium, taskDuration)
      };
      
      TaskStateManager.saveState(TASK_ID_FlightMonitorMedium, initialState);
      return initialState;
    }
    
    if (savedState) {
      // Resume from saved state with proper type casting
      const savedDuration = (savedState.duration as number) || taskDuration;
      
      return {
        startTime: savedState.startTime as number,
        duration: savedDuration,
        currentMonth: (savedState.currentMonth as number) ?? 0,
        selectedDay: (savedState.selectedDay as number) || null,
        flightAvailable: (savedState.flightAvailable as boolean) || false,
        showPassword: (savedState.showPassword as boolean) || false,
        staticPassword: generateParameterPassword(TASK_ID_FlightMonitorMedium, savedDuration)
      };
    } else {
      // Fresh start - same as reset case
      const now = Date.now();
      const initialState = {
        startTime: now,
        duration: taskDuration,
        currentMonth: 0, // Start at January (0-indexed)
        selectedDay: null,
        flightAvailable: false,
        showPassword: false,
        staticPassword: generateParameterPassword(TASK_ID_FlightMonitorMedium, taskDuration)
      };
      
      TaskStateManager.saveState(TASK_ID_FlightMonitorMedium, initialState);
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
  }, []); // Run once on mount
  
  const [startTime] = useState(initialState.startTime);
  const [flightDuration] = useState(initialState.duration);
  const [currentMonth, setCurrentMonth] = useState(initialState.currentMonth);
  const [selectedDay, setSelectedDay] = useState<number | null>(initialState.selectedDay);
  const [flightAvailable, setFlightAvailable] = useState(initialState.flightAvailable);
  const [showPassword, setShowPassword] = useState(initialState.showPassword);
  const [staticPassword, setStaticPassword] = useState(initialState.staticPassword || "");
  const [searching, setSearching] = useState(false);
  const [currentTime, setCurrentTime] = useState(Date.now());
  const { recordSuccess } = useTaskAnalytics(TASK_ID_FlightMonitorMedium);

  // Record success if resuming to an already completed state
  useEffect(() => {
    if (initialState.flightAvailable && initialState.showPassword) {
      recordSuccess();
    }
  }, [initialState.flightAvailable, initialState.showPassword, recordSuccess]);

  // Update current time every second for dev tools display
  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentTime(Date.now());
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  // Save state whenever any state variable changes
  useEffect(() => {
    const currentState = {
      startTime,
      duration: flightDuration,
      currentMonth,
      selectedDay,
      flightAvailable,
      showPassword,
      staticPassword
    };
    
    TaskStateManager.saveState(TASK_ID_FlightMonitorMedium, currentState);
  }, [startTime, flightDuration, currentMonth, selectedDay, flightAvailable, showPassword, staticPassword]);

  const checkFlightAvailability = () => {
    if (searching || flightAvailable) return;

    setSearching(true);

    // Check if enough time has passed since start AND May 17th is selected AND viewing May
    const elapsedTime = Math.floor((Date.now() - startTime) / 1000);
    const hasEnoughTimePassed = elapsedTime >= flightDuration;
    const isCorrectDate = selectedDay === 17;
    const isViewingMay = currentMonth === 4; // May is month 4 (0-indexed)

    // Simulate search time (1-2 seconds)
    setTimeout(() => {
      if (hasEnoughTimePassed && isCorrectDate && isViewingMay) {
        // Flight is available!
        const finalPassword = generateParameterPassword(TASK_ID_FlightMonitorMedium, flightDuration);
        setFlightAvailable(true);
        setStaticPassword(finalPassword);
      }
      setSearching(false);
    }, 1000 + Math.random() * 1000);
  };

  const bookFlight = () => {
    setShowPassword(true);
    recordSuccess();
  };

  const handleDayClick = (day: number) => {
    setSelectedDay(day);
    // Auto-check flights when day 17 is selected and we're in May
    if (day === 17 && currentMonth === 4) {
      setTimeout(() => {
        checkFlightAvailability();
      }, 100); // Small delay to ensure state is updated
    }
  };

  const navigateMonth = (direction: number) => {
    setCurrentMonth(prev => {
      const newMonth = prev + direction;
      // Wrap around: 0-11 (Jan-Dec)
      if (newMonth > 11) return 0; // Wrap to January
      if (newMonth < 0) return 11; // Wrap to December
      return newMonth;
    });
    // Clear selection when changing months
    setSelectedDay(null);
  };

  const handleResetTask = () => {
    if (window.confirm('Are you sure you want to reset this task? This will restart the flight monitor with default 30-second duration.')) {
      TaskStateManager.clearState(TASK_ID_FlightMonitorMedium);
      // Navigate to clean URL without any parameters to ensure default duration
      window.location.href = window.location.pathname;
    }
  };

  // Auto-refresh on page load/reload (simulates clicking refresh button)
  useEffect(() => {
    // Only auto-refresh if we haven't completed the task yet
    if (!showPassword) {
      checkFlightAvailability();
    }
  }, []); // Empty dependency array - only runs on mount

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
  
  // Debug logging (remove in production)
  if (isLocalhost) {
    console.log('FlightMonitorMedium Debug:', {
      startTime,
      currentTime: Date.now(),
      elapsedTime: Math.floor((Date.now() - startTime) / 1000),
      duration: flightDuration,
      currentMonth,
      selectedDay,
      flightAvailable,
      hasState: TaskStateManager.hasState(TASK_ID_FlightMonitorMedium)
    });
  }

  const monthNames = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
  ];

  const currentYear = new Date().getFullYear();

  const getDaysInMonth = (month: number, year: number) => {
    return new Date(year, month + 1, 0).getDate();
  };

  const getFirstDayOfMonth = (month: number, year: number) => {
    return new Date(year, month, 1).getDay();
  };

  const renderCalendar = () => {
    const daysInMonth = getDaysInMonth(currentMonth, currentYear);
    const firstDayOfWeek = getFirstDayOfMonth(currentMonth, currentYear);
    const days = Array.from({ length: daysInMonth }, (_, i) => i + 1);
    const weekDays = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-4 shadow-sm">
        {/* Month Navigation Header */}
        <div className="flex items-center justify-between mb-4">
          <button
            onClick={() => navigateMonth(-1)}
            className="p-2 rounded-lg bg-blue-500 text-white hover:bg-blue-600 transition-colors flex items-center justify-center w-10 h-10"
          >
            ←
          </button>
          <h3 className="text-lg font-semibold text-gray-800">
            {monthNames[currentMonth]} {currentYear}
          </h3>
          <button
            onClick={() => navigateMonth(1)}
            className="p-2 rounded-lg bg-blue-500 text-white hover:bg-blue-600 transition-colors flex items-center justify-center w-10 h-10"
          >
            →
          </button>
        </div>
        
        {/* Week day headers */}
        <div className="grid grid-cols-7 gap-1 mb-2">
          {weekDays.map(day => (
            <div key={day} className="text-center text-sm font-semibold text-gray-600 py-2">
              {day}
            </div>
          ))}
        </div>
        
        {/* Calendar grid */}
        <div className="grid grid-cols-7 gap-1">
          {/* Empty cells for days before month starts */}
          {Array.from({ length: firstDayOfWeek }, (_, i) => (
            <div key={`empty-${i}`} className="h-12"></div>
          ))}
          
          {/* Actual days */}
          {days.map(day => (
            <button
              key={day}
              onClick={() => handleDayClick(day)}
              className={`h-12 w-full rounded-md font-medium text-sm transition-all duration-200 flex items-center justify-center ${
                selectedDay === day 
                  ? 'bg-blue-500 text-white shadow-md transform scale-105' 
                  : 'bg-gray-50 text-gray-700 hover:bg-blue-50 hover:text-blue-700 border border-gray-200'
              }`}
            >
              {day}
            </button>
          ))}
        </div>
      </div>
    );
  };

  return (
    <div className="max-w-2xl mx-auto mt-10 mb-10">
      {/* Development Tools */}
      {(isLocalhost || adminConsoleEnabled) && (
        <div className="bg-gradient-to-r from-yellow-50 to-amber-50 border border-yellow-200/50 rounded-xl p-4 mb-6 shadow-sm backdrop-blur-sm">
          <div className="flex items-center justify-between text-sm">
            <div className="text-yellow-800 font-medium">
              <strong>Dev Tools:</strong> Duration: {flightDuration}s | Elapsed: {Math.floor((currentTime - startTime) / 1000)}s | 
              Month: {monthNames[currentMonth]} | 
              Selected: {selectedDay ? `${monthNames[currentMonth]} ${selectedDay}` : 'None'} | 
              Available: {flightAvailable ? '✅' : '❌'} |
              Persistent: {TaskStateManager.hasState(TASK_ID_FlightMonitorMedium) ? '✅' : '❌'}
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
      
      <div className="p-6 bg-white rounded-lg shadow-lg">
      <div className="text-center mb-6">
        <h1 className="text-2xl font-bold mb-2">✈️ SkyWings Flight Monitor</h1>
      </div>

      {/* Calendar Section */}
      <div className="mb-8">
        <div className="text-center mb-4">
          <h2 className="text-xl font-bold text-gray-800 mb-1">📅 Select Date</h2>
        </div>
        {renderCalendar()}
      </div>

      {/* Flight Search Section - Condensed */}
      {selectedDay && (
        <div className="bg-blue-50 p-3 rounded-lg mb-6">
          <div className="text-center mb-2">
            <h3 className="text-base font-semibold text-gray-700">
              {monthNames[currentMonth]} {selectedDay} Flights
            </h3>
          </div>

          <div className="text-center">
            {/* Refresh Button - Smaller */}
            <div className="flex items-center justify-center gap-2 mb-2">
              <button
                onClick={checkFlightAvailability}
                disabled={searching || (flightAvailable as boolean)}
                className={`flex items-center gap-1 px-3 py-2 rounded text-sm font-medium ${
                  searching || flightAvailable
                    ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                    : 'bg-blue-500 hover:bg-blue-600 text-white'
                }`}
              >
                <span className={`text-sm ${searching ? 'animate-spin' : ''}`}>
                  🔄
                </span>
                {searching ? 'Searching...' : 'Refresh'}
              </button>
            </div>

            {/* Search Results - Condensed */}
            {!searching && (
              <div className="border rounded p-2 text-sm">
                {!flightAvailable ? (
                  <div className="text-red-600">
                    ❌ No flights available
                  </div>
                ) : (
                  <div className="space-y-2">
                    <div className="text-green-600 font-medium">
                      ✅ SkyWings Flight 247 Available
                    </div>
                    <button
                      onClick={bookFlight}
                      className="bg-green-500 hover:bg-green-600 text-white px-4 py-2 rounded font-medium"
                    >
                      Book Flight
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Success State */}
      {showPassword && (
        <div id="flight-monitor-medium-status" data-state="completed" className="mt-6 p-4 bg-green-100 border-2 border-green-500 rounded-lg text-center">
          <h2 className="text-xl font-bold text-green-800 mb-2">🎉 Flight Booked Successfully!</h2>
          <p className="text-green-700 mb-4">
            Your booking confirmation is ready!
          </p>
          <div className="bg-green-200 p-3 rounded">
            <p className="text-green-800 font-medium mb-1">Confirmation Code:</p>
            <code id="flight-monitor-medium-code" className="font-mono font-bold text-lg">{staticPassword || generateParameterPassword(TASK_ID_FlightMonitorMedium, flightDuration)}</code>
          </div>
        </div>
      )}

      {/* Technical Details */}
      {showHints && (
        <div className="bg-gray-900 text-green-400 rounded-lg p-6 mt-6 border-2 border-green-500 font-mono">
          <h3 className="font-bold text-green-300 mb-3 text-lg">🛠️ TECHNICAL SPECIFICATIONS</h3>
          <div className="text-sm space-y-2">
            <p><strong className="text-yellow-400">📡 Flight Status:</strong> <code className="bg-gray-700 px-2 py-1 rounded">{flightAvailable ? 'Available' : 'Checking'}</code></p>
            <p><strong className="text-yellow-400">📅 Current Month:</strong> <code className="bg-gray-700 px-2 py-1 rounded">{monthNames[currentMonth]}</code></p>
            <p><strong className="text-yellow-400">📅 Selected Date:</strong> <code className="bg-gray-700 px-2 py-1 rounded">{selectedDay ? `${monthNames[currentMonth]} ${selectedDay}` : 'None'}</code></p>
            <p><strong className="text-yellow-400">🔒 Booking Status:</strong> <code className="bg-gray-700 px-2 py-1 rounded">{showPassword ? 'Confirmed' : 'Pending'}</code></p>
            <p><strong className="text-yellow-400">🔄 Action Required:</strong> <code className="bg-gray-700 px-2 py-1 rounded">Navigate to May and click day 17</code></p>
          </div>
        </div>
      )}

      </div>
    </div>
  );
};

export default FlightMonitorMedium;