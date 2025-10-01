import { useState, useEffect, useCallback, memo, useRef } from "react";
import { useTaskAnalytics } from "../utils/useTaskAnalytics";
import { TaskStateManager } from "../utils/TaskStateManager";
import { SIZE, ANIMATION, COMMON } from "../config/constants";
import { generateParameterPassword } from "../utils/parameterPassword";
import { URLParameterHandler } from "../utils/urlParameterHandler";
import { useDrag, useDrop } from 'react-dnd';

export const TASK_ID_AnimalMoverEasy = "animal-mover-easy";

const ItemTypes = {
  SHEEP: 'sheep',
};

interface SheepPosition {
  id: string;
  x: number;
  y: number;
  side: 'left' | 'right';
  targetX?: number;
  targetY?: number;
  velocityX: number;
  velocityY: number;
  facingLeft: boolean;
}

// Draggable Sheep Component
const DraggableSheep = ({ sheep, onMove }: { sheep: SheepPosition, onMove: (id: string, x: number, y: number, side: 'left' | 'right', _dropX?: number, _dropY?: number) => void }) => {
  const [{ isDragging }, drag] = useDrag(() => ({
    type: ItemTypes.SHEEP,
    item: { id: sheep.id },
    collect: (monitor) => ({
      isDragging: !!monitor.isDragging(),
    }),
    end: (_item, monitor) => {
      const dropResult = monitor.getDropResult<{ side: 'left' | 'right' }>();
      if (dropResult) {
        // Get actual drop position
        const clientOffset = monitor.getClientOffset();
        const dropZoneElement = document.querySelector(`[data-side="${dropResult.side}"]`);
        
        if (clientOffset && dropZoneElement) {
          const dropZoneRect = dropZoneElement.getBoundingClientRect();
          const relativeX = clientOffset.x - dropZoneRect.left;
          const relativeY = clientOffset.y - dropZoneRect.top;
          onMove(sheep.id, relativeX, relativeY, dropResult.side, relativeX, relativeY);
        } else {
          // Fallback to center of pen if drop position can't be determined
          onMove(sheep.id, 300, 200, dropResult.side);
        }
      }
    },
  }));

  const handleClick = () => {
    // Only move if on left side
    if (sheep.side === 'left') {
      // Generate random position on right side
      const randomX = Math.random() * 520 + 40; // Between 40-560px
      const randomY = Math.random() * 320 + 40; // Between 40-360px
      onMove(sheep.id, randomX, randomY, 'right');
    }
  };

  return (
    <div
      ref={drag}
      onClick={handleClick}
      className="absolute text-4xl cursor-grab transition-all duration-300 hover:scale-110"
      style={{ 
        left: sheep.x, 
        top: sheep.y,
        opacity: isDragging ? 0.5 : 1,
        transform: isDragging ? 'scale(1.1)' : 'scale(1)',
        zIndex: isDragging ? SIZE.DRAG_Z_INDEX : 1
      }}
      data-sheep-id={sheep.id}
    >
      <span style={{ transform: sheep.facingLeft ? 'scaleX(-1)' : 'scaleX(1)' }}>🐑</span>
    </div>
  );
};

// Drop Zone Component
const DropZone = ({ side, children }: { side: 'left' | 'right', children: React.ReactNode }) => {
  const [{ isOver }, drop] = useDrop(() => ({
    accept: ItemTypes.SHEEP,
    drop: () => ({ side }),
    collect: (monitor) => ({
      isOver: !!monitor.isOver(),
    }),
  }));

  return (
    <div
      ref={drop}
      data-side={side}
      className={`relative border-2 border-dashed border-blue-300 rounded-lg transition-all duration-300 ${
        isOver ? 'bg-blue-50 border-blue-500' : 'bg-transparent'
      }`}
    >
      {children}
    </div>
  );
};

const SheepMoverEasy = () => {
  // Parse URL parameters manually (don't clean yet)
  const urlParams = new URLSearchParams(window.location.search);
  const count = parseInt(urlParams.get('count') || '10', 10);
  // const showHints = urlParams.get('hints') === 'true'; // Unused
  
  // Validate count parameter
  const sheepCount = (count >= 1 && count <= 256) ? count : 10;
  
  // Check if validation failed and emit error for toast
  useEffect(() => {
    if (urlParams.has('count') && sheepCount !== count) {
      // Validation failed, emit error for toast
      const errors = [{
        parameter: 'count',
        providedValue: urlParams.get('count') || '',
        defaultUsed: 10,
        reason: count < 1 ? 'Value must be at least 1' : 
                count > 256 ? 'Value must be at most 256' :
                isNaN(count) ? 'Value must be a valid number' : 'Invalid value'
      }];
      
      // Use the existing validation error system
      setTimeout(() => {
        URLParameterHandler.emitValidationError(errors);
      }, COMMON.VALIDATION_DELAY);
    }
  }, []); // Run once on mount
  
  // Create params object for shouldResetState check
  const params = { count: sheepCount, hasAnyParams: urlParams.has('count') };

  // Generate initial sheep positions
  const generateInitialSheep = (): SheepPosition[] => {
    const sheep: SheepPosition[] = [];
    const sideWidth = 600;
    const sideHeight = 400;
    
    for (let i = 0; i < sheepCount; i++) {
      let x: number = Math.random() * (sideWidth - SIZE.ELEMENT_SIZE) + SIZE.POSITION_OFFSET;
      let y: number = Math.random() * (sideHeight - SIZE.ELEMENT_SIZE) + SIZE.ELEMENT_SIZE;
      let validPosition = false;
      let attempts = 0;
      
      // Try to find a position that doesn't overlap with other sheep
      while (!validPosition && attempts < ANIMATION.MAX_ATTEMPTS) {
        x = Math.random() * (sideWidth - SIZE.ELEMENT_SIZE) + SIZE.POSITION_OFFSET;
        y = Math.random() * (sideHeight - SIZE.ELEMENT_SIZE) + SIZE.ELEMENT_SIZE;
        
        // Check collision with existing sheep
        validPosition = !sheep.some(existingSheep => {
          const distance = Math.sqrt(
            Math.pow(existingSheep.x - x, 2) + Math.pow(existingSheep.y - y, 2)
          );
          return distance < 50; // Minimum distance between sheep
        });
        
        attempts++;
      }
      
      sheep.push({
        id: `sheep-${i}`,
        x: x,
        y: y,
        side: 'left',
        velocityX: (Math.random() - 0.5) * 1, // Slower initial velocity between -0.5 and 0.5
        velocityY: (Math.random() - 0.5) * 1,
        facingLeft: Math.random() > 0.5
      });
    }
    
    return sheep;
  };

  const initializeState = () => {
    const savedState = TaskStateManager.loadState(TASK_ID_AnimalMoverEasy);
    
    
    // Check if we should reset state based on parameter changes
    if (URLParameterHandler.shouldResetState(TASK_ID_AnimalMoverEasy, savedState, params)) {
      TaskStateManager.clearState(TASK_ID_AnimalMoverEasy);
      
      const now = Date.now();
      const initialState = {
        startTime: now,
        count: sheepCount,
        sheep: generateInitialSheep(),
        isCompleted: false,
        sheepMoved: 0,
        staticPassword: generateParameterPassword(TASK_ID_AnimalMoverEasy, sheepCount)
      };
      
      TaskStateManager.saveState(TASK_ID_AnimalMoverEasy, initialState);
      return initialState;
    }
    
    if (savedState) {
      // Resume from saved state with proper type casting
      const savedCount = (savedState.count as number) || sheepCount;
      const savedSheep = savedState.sheep as SheepPosition[];
      
      
      // Validate that we have valid sheep data
      const hasValidSheep = savedSheep && 
        Array.isArray(savedSheep) && 
        savedSheep.length > 0 &&
        savedSheep.every(s => 
          s && 
          typeof s.x === 'number' && 
          typeof s.y === 'number' && 
          typeof s.velocityX === 'number' &&
          typeof s.velocityY === 'number' &&
          typeof s.facingLeft === 'boolean' &&
          s.side && (s.side === 'left' || s.side === 'right') &&
          s.id && typeof s.id === 'string'
        );
      
      
      // If we have valid sheep data, use it; otherwise generate fresh sheep
      const restoredSheep = hasValidSheep ? 
        savedSheep.map(s => ({
          ...s,
          // Ensure all required properties are present with fallbacks
          velocityX: typeof s.velocityX === 'number' ? s.velocityX : (Math.random() - 0.5) * 1,
          velocityY: typeof s.velocityY === 'number' ? s.velocityY : (Math.random() - 0.5) * 1,
          facingLeft: typeof s.facingLeft === 'boolean' ? s.facingLeft : Math.random() > 0.5
        })) : 
        generateInitialSheep();
      
      return {
        startTime: savedState.startTime as number,
        count: savedCount,
        sheep: restoredSheep,
        isCompleted: savedState.isCompleted as boolean || false,
        sheepMoved: savedState.sheepMoved as number || 0,
        staticPassword: generateParameterPassword(TASK_ID_AnimalMoverEasy, savedCount)
      };
    } else {
      // Fresh start - same as reset case
      const now = Date.now();
      const initialState = {
        startTime: now,
        count: sheepCount,
        sheep: generateInitialSheep(),
        isCompleted: false,
        sheepMoved: 0,
        staticPassword: generateParameterPassword(TASK_ID_AnimalMoverEasy, sheepCount)
      };
      
      TaskStateManager.saveState(TASK_ID_AnimalMoverEasy, initialState);
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
  const [sheep, setSheep] = useState<SheepPosition[]>(initialState.sheep);
  const [isCompleted, setIsCompleted] = useState(initialState.isCompleted);
  const [staticPassword, setStaticPassword] = useState(initialState.staticPassword || "");
  const isInitialized = useRef(false);
  const { recordSuccess } = useTaskAnalytics(TASK_ID_AnimalMoverEasy);
  
  // Record success if resuming to an already completed state
  useEffect(() => {
    if (initialState.isCompleted) {
      recordSuccess();
    }
  }, [initialState.isCompleted, recordSuccess]);

  // Calculate sheep moved to right side
  const sheepOnRight = sheep.filter(s => s.side === 'right').length;
  const sheepOnLeft = sheep.filter(s => s.side === 'left').length;

  // Handle sheep movement
  const handleSheepMove = useCallback((id: string, x: number, y: number, side: 'left' | 'right') => {
    
    setSheep(prevSheep => {
      // Pen boundaries with fence margin
      const fenceMargin = 40;
      const penWidth = 600;
      const penHeight = 400;
      const sheepSize = 40;
      
      const minX = fenceMargin;
      const maxX = penWidth - fenceMargin - sheepSize;
      const minY = fenceMargin;
      const maxY = penHeight - fenceMargin - sheepSize;
      
      // Clamp position within boundaries
      const finalX = Math.max(minX, Math.min(maxX, x));
      const finalY = Math.max(minY, Math.min(maxY, y));
      
      // Check for collisions with other sheep in the same side and displace them
      const updatedSheep = prevSheep.map(s => {
        if (s.id === id) {
          return {
            ...s,
            x: finalX,
            y: finalY,
            side,
            facingLeft: side === 'left', // Face left when on left side, right when on right side
            velocityX: (Math.random() - 0.5) * 1,
            velocityY: (Math.random() - 0.5) * 1
          };
        }
        
        // Displace overlapping sheep in the same side
        if (s.side === side) {
          const dx = s.x - finalX;
          const dy = s.y - finalY;
          const distance = Math.sqrt(dx * dx + dy * dy);
          
          if (distance < sheepSize && distance > 0) {
            // Calculate displacement direction
            const normalX = dx / distance;
            const normalY = dy / distance;
            const displacementDistance = sheepSize - distance + 10; // Extra spacing
            
            let newX = s.x + normalX * displacementDistance;
            let newY = s.y + normalY * displacementDistance;
            
            // Keep displaced sheep within boundaries
            newX = Math.max(minX, Math.min(maxX, newX));
            newY = Math.max(minY, Math.min(maxY, newY));
            
            return {
              ...s,
              x: newX,
              y: newY,
              velocityX: normalX * 2, // Give it some momentum away from the dropped sheep
              velocityY: normalY * 2
            };
          }
        }
        
        return s;
      });
      
      
      // Save state immediately for sheep moves to prevent data loss
      const newSheepOnRight = updatedSheep.filter(s => s.side === 'right').length;
      const currentState = {
        startTime,
        count: taskCount,
        sheep: updatedSheep,
        isCompleted,
        sheepMoved: newSheepOnRight,
        staticPassword
      };
      TaskStateManager.saveStateImmediate(TASK_ID_AnimalMoverEasy, currentState);
      
      return updatedSheep;
    });
  }, [startTime, taskCount, isCompleted, staticPassword]);

  // Mark as initialized after first render
  useEffect(() => {
    isInitialized.current = true;
  }, []);

  // Save state whenever any state variable changes
  useEffect(() => {
    // Don't save during initial load to avoid overwriting restored state
    if (!isInitialized.current) return;
    
    const currentState = {
      startTime,
      count: taskCount,
      sheep,
      isCompleted,
      sheepMoved: sheepOnRight,
      staticPassword
    };
    
    TaskStateManager.saveState(TASK_ID_AnimalMoverEasy, currentState);
  }, [startTime, taskCount, sheep, isCompleted, sheepOnRight, staticPassword]);

  // Check for completion - all sheep moved to right side
  useEffect(() => {
    const totalSheep = sheep.length;
    if (sheepOnRight === totalSheep && totalSheep > 0 && !isCompleted) {
      const finalPassword = generateParameterPassword(TASK_ID_AnimalMoverEasy, taskCount);
      setIsCompleted(true);
      setStaticPassword(finalPassword);
      recordSuccess();
    }
  }, [sheepOnRight, sheep.length, isCompleted, recordSuccess, startTime, taskCount]);

  // Sheep movement animation with collision physics
  useEffect(() => {
    const moveInterval = setInterval(() => {
      setSheep(prevSheep => {
        const sideWidth = 600;
        const sideHeight = 400;
        const sheepSize = 40; // Approximate sheep size for collision
        // const margin = 30;
        
        // Boundary enforcement - keep sheep well within visible area
        
        return prevSheep.map((sheepItem, index) => {
          let newX = sheepItem.x + sheepItem.velocityX;
          let newY = sheepItem.y + sheepItem.velocityY;
          let newVelX = sheepItem.velocityX;
          let newVelY = sheepItem.velocityY;
          let newFacingLeft = sheepItem.facingLeft;
          let hitBoundary = false; // Track if we hit a boundary
          
          // More robust boundary collision - check before and after movement
          const fenceMargin = 40; // Match fence visual
          const minX = fenceMargin;
          const maxX = sideWidth - fenceMargin - sheepSize;
          const minY = fenceMargin; // Top margin
          const maxY = sideHeight - fenceMargin - sheepSize; // Bottom margin
          
          // Horizontal boundary collision with stronger enforcement
          if (newX <= minX) {
            newX = minX + 10; // Push significantly inside boundary
            newVelX = Math.abs(newVelX) * 0.5; // Bounce right with more energy loss
            newFacingLeft = false; // Face right
            hitBoundary = true;
          } else if (newX >= maxX) {
            newX = maxX - 10; // Push significantly inside boundary
            newVelX = -Math.abs(newVelX) * 0.5; // Bounce left with more energy loss
            newFacingLeft = true; // Face left
            hitBoundary = true;
          }
          
          // Vertical boundary collision with stronger enforcement
          if (newY <= minY) {
            newY = minY + 10; // Push significantly inside boundary
            newVelY = Math.abs(newVelY) * 0.5; // Bounce down with more energy loss
          } else if (newY >= maxY) {
            newY = maxY - 10; // Push significantly inside boundary
            newVelY = -Math.abs(newVelY) * 0.5; // Bounce up with more energy loss
          }
          
          // Check collision with other sheep
          for (let i = 0; i < prevSheep.length; i++) {
            if (i === index) continue;
            const otherSheep = prevSheep[i];
            if (otherSheep.side !== sheepItem.side) continue;
            
            const dx = newX - otherSheep.x;
            const dy = newY - otherSheep.y;
            const distance = Math.sqrt(dx * dx + dy * dy);
            
            if (distance < sheepSize && distance > 0) {
              // Collision detected - bounce sheep apart
              const normalX = dx / distance;
              const normalY = dy / distance;
              
              // Separate sheep
              const overlap = sheepSize - distance;
              newX += normalX * overlap * 0.5;
              newY += normalY * overlap * 0.5;
              
              // Bounce velocities
              const relativeVelX = newVelX - otherSheep.velocityX;
              const relativeVelY = newVelY - otherSheep.velocityY;
              const velAlongNormal = relativeVelX * normalX + relativeVelY * normalY;
              
              if (velAlongNormal > 0) continue; // Objects separating
              
              const bounceStrength = 0.6;
              newVelX -= velAlongNormal * normalX * bounceStrength;
              newVelY -= velAlongNormal * normalY * bounceStrength;
              newFacingLeft = newVelX < 0;
            }
          }
          
          // Add some random movement and damping (reduced random movement)
          newVelX += (Math.random() - 0.5) * 0.1; // Reduced random movement
          newVelY += (Math.random() - 0.5) * 0.1;
          newVelX *= 0.98; // Stronger damping
          newVelY *= 0.98;
          
          // Update facing direction based on velocity ONLY if we didn't hit a boundary
          if (!hitBoundary && Math.abs(newVelX) > 0.1) { // Only change direction if moving significantly and didn't hit boundary
            newFacingLeft = newVelX < 0;
          }
          
          // Limit maximum speed to prevent escaping
          const maxSpeed = 1.0; // Further reduced to prevent boundary escape
          const speed = Math.sqrt(newVelX * newVelX + newVelY * newVelY);
          if (speed > maxSpeed) {
            newVelX = (newVelX / speed) * maxSpeed;
            newVelY = (newVelY / speed) * maxSpeed;
          }
          
          // Final safety check - force sheep to stay well within bounds
          newX = Math.max(minX + 5, Math.min(maxX - 5, newX));
          newY = Math.max(minY + 5, Math.min(maxY - 5, newY));
          
          return {
            ...sheepItem,
            x: newX,
            y: newY,
            velocityX: newVelX,
            velocityY: newVelY,
            facingLeft: newFacingLeft
          };
        });
      });
    }, COMMON.VALIDATION_DELAY); // Much more frequent updates for smooth movement

    return () => clearInterval(moveInterval);
  }, []);

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

  const handleResetTask = () => {
    if (window.confirm('Are you sure you want to reset this task? This will restart the sheep moving challenge from the beginning.')) {
      TaskStateManager.clearState(TASK_ID_AnimalMoverEasy);
      // Reload with current count parameter to maintain the same count
      window.location.href = `${window.location.pathname}?count=${sheepCount}`;
    }
  };

  const leftSideSheep = sheep.filter(s => s.side === 'left');
  const rightSideSheep = sheep.filter(s => s.side === 'right');

  return (
    <div className="min-h-screen bg-gradient-to-b from-sky-400 via-sky-300 to-blue-400 p-6">
      <div className="max-w-6xl mx-auto">
        {/* Development Tools */}
        {(isLocalhost || adminConsoleEnabled) && (
          <div className="bg-gradient-to-r from-yellow-50 to-amber-50 border border-yellow-200/50 rounded-xl p-4 mb-6 shadow-sm backdrop-blur-sm">
            <div className="flex items-center justify-between text-sm">
              <div className="text-yellow-800 font-medium">
                <strong>Dev Tools:</strong> Count: {taskCount} | Left: {sheepOnLeft} | Right: {sheepOnRight} | 
                Completed: {isCompleted ? '✅' : '❌'} |
                Persistent: {TaskStateManager.hasState(TASK_ID_AnimalMoverEasy) ? '✅' : '❌'}
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
        


        <div className="flex gap-6 justify-center items-start">
          {/* Left Side */}
          <div className="text-center">
            <DropZone side="left">
              <div 
                className="w-full h-full bg-gradient-to-br from-green-400 to-green-600 rounded-lg relative overflow-hidden border-8 border-amber-800"
                style={{ 
                  width: '600px', 
                  height: '400px',
                  backgroundImage: 'url("data:image/svg+xml,%3Csvg width="40" height="40" viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"%3E%3Cg fill="none" fill-rule="evenodd"%3E%3Cg fill="%23ffffff" fill-opacity="0.1"%3E%3Ccircle cx="20" cy="20" r="2"/%3E%3C/g%3E%3C/g%3E%3C/svg%3E"),repeating-linear-gradient(0deg, transparent, transparent 35px, rgba(139, 69, 19, 0.3) 35px, rgba(139, 69, 19, 0.3) 40px)',
                  boxShadow: 'inset 0 0 20px rgba(139, 69, 19, 0.3)'
                }}
              >
                {/* Fence posts */}
                <div className="absolute top-0 left-8 w-2 h-full bg-amber-900 opacity-60"></div>
                <div className="absolute top-0 right-8 w-2 h-full bg-amber-900 opacity-60"></div>
                <div className="absolute top-8 left-0 w-full h-2 bg-amber-900 opacity-60"></div>
                <div className="absolute bottom-8 left-0 w-full h-2 bg-amber-900 opacity-60"></div>
                {leftSideSheep.map(sheep => (
                  <DraggableSheep
                    key={sheep.id}
                    sheep={sheep}
                    onMove={handleSheepMove}
                  />
                ))}
              </div>
            </DropZone>
          </div>

          {/* River */}
          <div className="flex flex-col items-center">
            <div className="w-32 bg-gradient-to-b from-blue-600 via-blue-500 to-blue-700 rounded-lg relative overflow-hidden" style={{ height: '400px' }}>
              {/* Flowing water animation */}
              <div className="absolute inset-0 opacity-30">
                <div className="absolute w-full h-full bg-gradient-to-r from-transparent via-white to-transparent animate-pulse"></div>
                <div 
                  className="absolute w-full h-4 bg-gradient-to-r from-transparent via-cyan-200 to-transparent animate-bounce"
                  style={{ animationDelay: '0.5s', top: '20%' }}
                ></div>
                <div 
                  className="absolute w-full h-4 bg-gradient-to-r from-transparent via-cyan-200 to-transparent animate-bounce"
                  style={{ animationDelay: '1s', top: '50%' }}
                ></div>
                <div 
                  className="absolute w-full h-4 bg-gradient-to-r from-transparent via-cyan-200 to-transparent animate-bounce"
                  style={{ animationDelay: '1.5s', top: '80%' }}
                ></div>
              </div>
            </div>
          </div>

          {/* Right Side */}
          <div className="text-center">
            <DropZone side="right">
              <div 
                className="w-full h-full bg-gradient-to-br from-green-400 to-green-600 rounded-lg relative overflow-hidden border-8 border-amber-800"
                style={{ 
                  width: '600px', 
                  height: '400px',
                  backgroundImage: 'url("data:image/svg+xml,%3Csvg width="40" height="40" viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"%3E%3Cg fill="none" fill-rule="evenodd"%3E%3Cg fill="%23ffffff" fill-opacity="0.1"%3E%3Ccircle cx="20" cy="20" r="2"/%3E%3C/g%3E%3C/g%3E%3C/svg%3E"),repeating-linear-gradient(0deg, transparent, transparent 35px, rgba(139, 69, 19, 0.3) 35px, rgba(139, 69, 19, 0.3) 40px)',
                  boxShadow: 'inset 0 0 20px rgba(139, 69, 19, 0.3)'
                }}
              >
                {/* Fence posts */}
                <div className="absolute top-0 left-8 w-2 h-full bg-amber-900 opacity-60"></div>
                <div className="absolute top-0 right-8 w-2 h-full bg-amber-900 opacity-60"></div>
                <div className="absolute top-8 left-0 w-full h-2 bg-amber-900 opacity-60"></div>
                <div className="absolute bottom-8 left-0 w-full h-2 bg-amber-900 opacity-60"></div>
                {rightSideSheep.map(sheep => (
                  <DraggableSheep
                    key={sheep.id}
                    sheep={sheep}
                    onMove={handleSheepMove}
                  />
                ))}
              </div>
            </DropZone>
          </div>
        </div>

        {isCompleted && (
          <div className="mt-6 p-6 bg-gradient-to-r from-gold-200 to-yellow-200 rounded-lg text-center shadow-lg border-4 border-yellow-400 animate-pulse">
            <div className="text-4xl mb-2">🏆</div>
            <h2 className="text-xl font-bold text-yellow-800 mb-2">All Sheep Safely Across!</h2>
            <p className="text-yellow-700 mb-4">Congratulations! You've successfully moved all sheep across the lake.</p>
            <code className="text-2xl font-mono bg-yellow-100 px-4 py-2 rounded border-2 border-yellow-500">{staticPassword || generateParameterPassword(TASK_ID_AnimalMoverEasy, taskCount)}</code>
          </div>
        )}
      </div>
      
      <style dangerouslySetInnerHTML={{
        __html: `
          @keyframes water-flow {
            0% { transform: translateY(0px); }
            50% { transform: translateY(-10px); }
            100% { transform: translateY(0px); }
          }
          .water-animation {
            animation: water-flow 2s ease-in-out infinite;
          }
        `
      }} />
    </div>
  );
};

export default memo(SheepMoverEasy);