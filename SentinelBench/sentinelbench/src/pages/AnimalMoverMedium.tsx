import { useState, useEffect, useCallback, memo, useRef } from "react";
import { useTaskAnalytics } from "../utils/useTaskAnalytics";
import { TaskStateManager } from "../utils/TaskStateManager";
import { generateParameterPassword } from "../utils/parameterPassword";
import { URLParameterHandler } from "../utils/urlParameterHandler";
import { useDrag, useDrop } from 'react-dnd';

export const TASK_ID_AnimalMoverMedium = "animal-mover-medium";

const ItemTypes = {
  ANIMAL: 'animal',
};

interface AnimalPosition {
  id: string;
  x: number;
  y: number;
  side: 'left' | 'right';
  type: 'sheep' | 'wolf' | 'pig';
  targetX?: number;
  targetY?: number;
  velocityX: number;
  velocityY: number;
  facingLeft: boolean;
}

// Draggable Animal Component
const DraggableAnimal = ({ animal, onMove }: { 
  animal: AnimalPosition, 
  onMove: (id: string, x: number, y: number, side: 'left' | 'right', _dropX?: number, _dropY?: number) => void
}) => {
  const [{ isDragging }, drag] = useDrag(() => ({
    type: ItemTypes.ANIMAL,
    item: { id: animal.id },
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
          onMove(animal.id, relativeX, relativeY, dropResult.side, relativeX, relativeY);
        } else {
          // Fallback to center of pen if drop position can't be determined
          onMove(animal.id, 300, 200, dropResult.side);
        }
      }
    },
  }));

  const handleClick = () => {
    // Animals on left side can always move right (if pen has space)
    // Animals on right side can always move back left (to make room)
    if (animal.side === 'left' || animal.side === 'right') {
      const targetSide = animal.side === 'left' ? 'right' : 'left';
      // Generate random position on target side
      const randomX = Math.random() * 520 + 40; // Between 40-560px
      const randomY = Math.random() * 320 + 40; // Between 40-360px
      onMove(animal.id, randomX, randomY, targetSide);
    }
  };

  const getAnimalEmoji = (type: string) => {
    switch (type) {
      case 'sheep': return '🐑';
      case 'wolf': return '🐺';
      case 'pig': return '🐷';
      default: return '🐑';
    }
  };

  return (
    <div
      ref={drag}
      onClick={handleClick}
      className="absolute text-4xl cursor-grab transition-all duration-300 hover:scale-110"
      style={{ 
        left: animal.x, 
        top: animal.y,
        opacity: isDragging ? 0.5 : 1,
        transform: isDragging ? 'scale(1.1)' : 'scale(1)',
        zIndex: isDragging ? 1000 : 1
      }}
      data-animal-id={animal.id}
    >
      <span style={{ transform: animal.facingLeft ? 'scaleX(-1)' : 'scaleX(1)' }}>
        {getAnimalEmoji(animal.type)}
      </span>
    </div>
  );
};

// Drop Zone Component
const DropZone = ({ side, children, isPenFull }: { 
  side: 'left' | 'right', 
  children: React.ReactNode,
  isPenFull?: boolean 
}) => {
  const [{ isOver }, drop] = useDrop(() => ({
    accept: ItemTypes.ANIMAL,
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
      {isPenFull && side === 'right' && (
        <div className="absolute top-2 right-2 bg-red-500 text-white text-xs px-2 py-1 rounded z-20">
          PEN FULL
        </div>
      )}
      {children}
    </div>
  );
};

const AnimalMoverMedium = () => {
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
      }, 100);
    }
  }, []); // Run once on mount
  
  // Create params object for shouldResetState check
  const params = { count: sheepCount, hasAnyParams: urlParams.has('count') };

  // Generate initial animal positions
  const generateInitialAnimals = (): AnimalPosition[] => {
    const animals: AnimalPosition[] = [];
    const sideWidth = 600;
    const sideHeight = 400;
    
    // Calculate number of distractors (50% of sheep count)
    const distractorCount = Math.floor(sheepCount / 2);
    const wolvesCount = Math.floor(distractorCount / 2);
    
    const totalAnimals = sheepCount + distractorCount;
    
    for (let i = 0; i < totalAnimals; i++) {
      let x: number = Math.random() * (sideWidth - 60) + 30;
      let y: number = Math.random() * (sideHeight - 60) + 60;
      let validPosition = false;
      let attempts = 0;
      
      // Try to find a position that doesn't overlap with other animals
      while (!validPosition && attempts < 100) {
        x = Math.random() * (sideWidth - 60) + 30;
        y = Math.random() * (sideHeight - 60) + 60;
        
        // Check collision with existing animals
        validPosition = !animals.some(existingAnimal => {
          const distance = Math.sqrt(
            Math.pow(existingAnimal.x - x, 2) + Math.pow(existingAnimal.y - y, 2)
          );
          return distance < 50; // Minimum distance between animals
        });
        
        attempts++;
      }
      
      // Determine animal type
      let animalType: 'sheep' | 'wolf' | 'pig' = 'sheep';
      if (i >= sheepCount) {
        // This is a distractor animal
        const distractorIndex = i - sheepCount;
        if (distractorIndex < wolvesCount) {
          animalType = 'wolf';
        } else {
          animalType = 'pig';
        }
      }
      
      animals.push({
        id: `${animalType}-${i}`,
        x: x,
        y: y,
        side: 'left',
        type: animalType,
        velocityX: (Math.random() - 0.5) * 1,
        velocityY: (Math.random() - 0.5) * 1,
        facingLeft: Math.random() > 0.5
      });
    }
    
    return animals;
  };

  const initializeState = () => {
    const savedState = TaskStateManager.loadState(TASK_ID_AnimalMoverMedium);
    
    // Check if we should reset state based on parameter changes
    if (URLParameterHandler.shouldResetState(TASK_ID_AnimalMoverMedium, savedState, params)) {
      TaskStateManager.clearState(TASK_ID_AnimalMoverMedium);
      
      const now = Date.now();
      const initialState = {
        startTime: now,
        count: sheepCount,
        animals: generateInitialAnimals(),
        isCompleted: false,
        animalsMoved: 0,
        staticPassword: generateParameterPassword(TASK_ID_AnimalMoverMedium, sheepCount)
      };
      
      TaskStateManager.saveState(TASK_ID_AnimalMoverMedium, initialState);
      return initialState;
    }
    
    if (savedState) {
      // Resume from saved state with proper type casting
      const savedCount = (savedState.count as number) || sheepCount;
      const savedAnimals = savedState.animals as AnimalPosition[];
      
      // Validate that we have valid animal data
      const hasValidAnimals = savedAnimals && 
        Array.isArray(savedAnimals) && 
        savedAnimals.length > 0 &&
        savedAnimals.every(a => 
          a && 
          typeof a.x === 'number' && 
          typeof a.y === 'number' && 
          typeof a.velocityX === 'number' &&
          typeof a.velocityY === 'number' &&
          typeof a.facingLeft === 'boolean' &&
          a.side && (a.side === 'left' || a.side === 'right') &&
          a.id && typeof a.id === 'string' &&
          a.type && (a.type === 'sheep' || a.type === 'wolf' || a.type === 'pig')
        );
      
      // If we have valid animal data, use it; otherwise generate fresh animals
      const restoredAnimals = hasValidAnimals ? 
        savedAnimals.map(a => ({
          ...a,
          // Ensure all required properties are present with fallbacks
          velocityX: typeof a.velocityX === 'number' ? a.velocityX : (Math.random() - 0.5) * 1,
          velocityY: typeof a.velocityY === 'number' ? a.velocityY : (Math.random() - 0.5) * 1,
          facingLeft: typeof a.facingLeft === 'boolean' ? a.facingLeft : Math.random() > 0.5
        })) : 
        generateInitialAnimals();
      
      return {
        startTime: savedState.startTime as number,
        count: savedCount,
        animals: restoredAnimals,
        isCompleted: savedState.isCompleted as boolean || false,
        animalsMoved: savedState.animalsMoved as number || 0,
        staticPassword: generateParameterPassword(TASK_ID_AnimalMoverMedium, savedCount)
      };
    } else {
      // Fresh start - same as reset case
      const now = Date.now();
      const initialState = {
        startTime: now,
        count: sheepCount,
        animals: generateInitialAnimals(),
        isCompleted: false,
        animalsMoved: 0,
        staticPassword: generateParameterPassword(TASK_ID_AnimalMoverMedium, sheepCount)
      };
      
      TaskStateManager.saveState(TASK_ID_AnimalMoverMedium, initialState);
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
  const [animals, setAnimals] = useState<AnimalPosition[]>(initialState.animals);
  const [isCompleted, setIsCompleted] = useState(initialState.isCompleted);
  const [staticPassword, setStaticPassword] = useState(initialState.staticPassword || "");
  const isInitialized = useRef(false);
  const { recordSuccess } = useTaskAnalytics(TASK_ID_AnimalMoverMedium);
  
  // Record success if resuming to an already completed state
  useEffect(() => {
    if (initialState.isCompleted) {
      recordSuccess();
    }
  }, [initialState.isCompleted, recordSuccess]);

  // Mark as initialized after first render
  useEffect(() => {
    isInitialized.current = true;
  }, []);

  // Calculate animals on each side
  const sheepOnRight = animals.filter(a => a.side === 'right' && a.type === 'sheep').length;
  const animalsOnRight = animals.filter(a => a.side === 'right').length;
  const distractorsOnRight = animals.filter(a => a.side === 'right' && a.type !== 'sheep').length;
  const sheepOnLeft = animals.filter(a => a.side === 'left' && a.type === 'sheep').length;
  
  // Check if right pen is full
  const isPenFull = animalsOnRight >= taskCount;

  // Handle animal movement
  const handleAnimalMove = useCallback((id: string, x: number, y: number, side: 'left' | 'right') => {
    setAnimals(prevAnimals => {
      const animal = prevAnimals.find(a => a.id === id);
      if (!animal) return prevAnimals;

      // If moving to right side and pen is full, reject the move
      if (side === 'right' && animal.side === 'left') {
        const currentRightCount = prevAnimals.filter(a => a.side === 'right').length;
        if (currentRightCount >= taskCount) {
          return prevAnimals; // Reject the move
        }
      }

      // Pen boundaries with fence margin
      const fenceMargin = 40;
      const penWidth = 600;
      const penHeight = 400;
      const animalSize = 40;
      
      const minX = fenceMargin;
      const maxX = penWidth - fenceMargin - animalSize;
      const minY = fenceMargin;
      const maxY = penHeight - fenceMargin - animalSize;
      
      // Clamp position within boundaries
      const finalX = Math.max(minX, Math.min(maxX, x));
      const finalY = Math.max(minY, Math.min(maxY, y));
      
      // Check for collisions with other animals in the same side and displace them
      const updatedAnimals = prevAnimals.map(a => {
        if (a.id === id) {
          return {
            ...a,
            x: finalX,
            y: finalY,
            side,
            facingLeft: side === 'left',
            velocityX: (Math.random() - 0.5) * 1,
            velocityY: (Math.random() - 0.5) * 1
          };
        }
        
        // Displace overlapping animals in the same side
        if (a.side === side) {
          const dx = a.x - finalX;
          const dy = a.y - finalY;
          const distance = Math.sqrt(dx * dx + dy * dy);
          
          if (distance < animalSize && distance > 0) {
            // Calculate displacement direction
            const normalX = dx / distance;
            const normalY = dy / distance;
            const displacementDistance = animalSize - distance + 10; // Extra spacing
            
            let newX = a.x + normalX * displacementDistance;
            let newY = a.y + normalY * displacementDistance;
            
            // Keep displaced animals within boundaries
            newX = Math.max(minX, Math.min(maxX, newX));
            newY = Math.max(minY, Math.min(maxY, newY));
            
            return {
              ...a,
              x: newX,
              y: newY,
              velocityX: normalX * 2,
              velocityY: normalY * 2
            };
          }
        }
        
        return a;
      });
      
      // Save state immediately for animal moves to prevent data loss
      const newAnimalsOnRight = updatedAnimals.filter(a => a.side === 'right').length;
      const currentState = {
        startTime,
        count: taskCount,
        animals: updatedAnimals,
        isCompleted,
        animalsMoved: newAnimalsOnRight,
        staticPassword
      };
      TaskStateManager.saveStateImmediate(TASK_ID_AnimalMoverMedium, currentState);
      
      return updatedAnimals;
    });
  }, [startTime, taskCount, isCompleted, staticPassword]);

  // Save state whenever any state variable changes
  useEffect(() => {
    // Don't save during initial load to avoid overwriting restored state
    if (!isInitialized.current) return;
    
    const currentState = {
      startTime,
      count: taskCount,
      animals,
      isCompleted,
      animalsMoved: animalsOnRight,
      staticPassword
    };
    
    TaskStateManager.saveState(TASK_ID_AnimalMoverMedium, currentState);
  }, [startTime, taskCount, animals, isCompleted, animalsOnRight, staticPassword]);

  // Check for completion - all sheep moved to right side and no distractors on right
  useEffect(() => {
    const totalSheep = animals.filter(a => a.type === 'sheep').length;
    if (sheepOnRight === totalSheep && totalSheep > 0 && distractorsOnRight === 0 && !isCompleted) {
      const finalPassword = generateParameterPassword(TASK_ID_AnimalMoverMedium, taskCount);
      setIsCompleted(true);
      setStaticPassword(finalPassword);
      recordSuccess();
    }
  }, [sheepOnRight, distractorsOnRight, animals, isCompleted, recordSuccess, startTime, taskCount]);

  // Animal movement animation with collision physics
  useEffect(() => {
    const moveInterval = setInterval(() => {
      setAnimals(prevAnimals => {
        const sideWidth = 600;
        const sideHeight = 400;
        const animalSize = 40;
        
        return prevAnimals.map((animalItem, index) => {
          let newX = animalItem.x + animalItem.velocityX;
          let newY = animalItem.y + animalItem.velocityY;
          let newVelX = animalItem.velocityX;
          let newVelY = animalItem.velocityY;
          let newFacingLeft = animalItem.facingLeft;
          let hitBoundary = false;
          
          const fenceMargin = 40;
          const minX = fenceMargin;
          const maxX = sideWidth - fenceMargin - animalSize;
          const minY = fenceMargin;
          const maxY = sideHeight - fenceMargin - animalSize;
          
          // Horizontal boundary collision
          if (newX <= minX) {
            newX = minX + 10;
            newVelX = Math.abs(newVelX) * 0.5;
            newFacingLeft = false;
            hitBoundary = true;
          } else if (newX >= maxX) {
            newX = maxX - 10;
            newVelX = -Math.abs(newVelX) * 0.5;
            newFacingLeft = true;
            hitBoundary = true;
          }
          
          // Vertical boundary collision
          if (newY <= minY) {
            newY = minY + 10;
            newVelY = Math.abs(newVelY) * 0.5;
          } else if (newY >= maxY) {
            newY = maxY - 10;
            newVelY = -Math.abs(newVelY) * 0.5;
          }
          
          // Check collision with other animals
          for (let i = 0; i < prevAnimals.length; i++) {
            if (i === index) continue;
            const otherAnimal = prevAnimals[i];
            if (otherAnimal.side !== animalItem.side) continue;
            
            const dx = newX - otherAnimal.x;
            const dy = newY - otherAnimal.y;
            const distance = Math.sqrt(dx * dx + dy * dy);
            
            if (distance < animalSize && distance > 0) {
              const normalX = dx / distance;
              const normalY = dy / distance;
              
              const overlap = animalSize - distance;
              newX += normalX * overlap * 0.5;
              newY += normalY * overlap * 0.5;
              
              const relativeVelX = newVelX - otherAnimal.velocityX;
              const relativeVelY = newVelY - otherAnimal.velocityY;
              const velAlongNormal = relativeVelX * normalX + relativeVelY * normalY;
              
              if (velAlongNormal > 0) continue;
              
              const bounceStrength = 0.6;
              newVelX -= velAlongNormal * normalX * bounceStrength;
              newVelY -= velAlongNormal * normalY * bounceStrength;
              newFacingLeft = newVelX < 0;
            }
          }
          
          // Add random movement and damping
          newVelX += (Math.random() - 0.5) * 0.1;
          newVelY += (Math.random() - 0.5) * 0.1;
          newVelX *= 0.98;
          newVelY *= 0.98;
          
          if (!hitBoundary && Math.abs(newVelX) > 0.1) {
            newFacingLeft = newVelX < 0;
          }
          
          // Limit maximum speed
          const maxSpeed = 1.0;
          const speed = Math.sqrt(newVelX * newVelX + newVelY * newVelY);
          if (speed > maxSpeed) {
            newVelX = (newVelX / speed) * maxSpeed;
            newVelY = (newVelY / speed) * maxSpeed;
          }
          
          // Final safety check
          newX = Math.max(minX + 5, Math.min(maxX - 5, newX));
          newY = Math.max(minY + 5, Math.min(maxY - 5, newY));
          
          return {
            ...animalItem,
            x: newX,
            y: newY,
            velocityX: newVelX,
            velocityY: newVelY,
            facingLeft: newFacingLeft
          };
        });
      });
    }, 100);

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
    if (window.confirm('Are you sure you want to reset this task? This will restart the animal moving challenge from the beginning.')) {
      TaskStateManager.clearState(TASK_ID_AnimalMoverMedium);
      // Reload with current count parameter to maintain the same count
      window.location.href = `${window.location.pathname}?count=${sheepCount}`;
    }
  };

  const leftSideAnimals = animals.filter(a => a.side === 'left');
  const rightSideAnimals = animals.filter(a => a.side === 'right');

  return (
    <div className="min-h-screen bg-gradient-to-b from-sky-400 via-sky-300 to-blue-400 p-6">
      <div className="max-w-6xl mx-auto">
        {/* Development Tools */}
        {(isLocalhost || adminConsoleEnabled) && (
          <div className="bg-gradient-to-r from-yellow-50 to-amber-50 border border-yellow-200/50 rounded-xl p-4 mb-6 shadow-sm backdrop-blur-sm">
            <div className="flex items-center justify-between text-sm">
              <div className="text-yellow-800 font-medium">
                <strong>Dev Tools:</strong> Count: {taskCount} | Sheep Left: {sheepOnLeft} | Sheep Right: {sheepOnRight} | 
                Distractors Right: {distractorsOnRight} | Pen Full: {isPenFull ? '✅' : '❌'} | 
                Completed: {isCompleted ? '✅' : '❌'} |
                Persistent: {TaskStateManager.hasState(TASK_ID_AnimalMoverMedium) ? '✅' : '❌'}
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
                {leftSideAnimals.map(animal => (
                  <DraggableAnimal
                    key={animal.id}
                    animal={animal}
                    onMove={handleAnimalMove}
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
            <DropZone side="right" isPenFull={isPenFull}>
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
                {rightSideAnimals.map(animal => (
                  <DraggableAnimal
                    key={animal.id}
                    animal={animal}
                    onMove={handleAnimalMove}
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
            <p className="text-yellow-700 mb-4">Congratulations! You've successfully moved all sheep across the lake while avoiding the distractors.</p>
            <code className="text-2xl font-mono bg-yellow-100 px-4 py-2 rounded border-2 border-yellow-500">
              {staticPassword || generateParameterPassword(TASK_ID_AnimalMoverMedium, taskCount)}
            </code>
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

export default memo(AnimalMoverMedium);