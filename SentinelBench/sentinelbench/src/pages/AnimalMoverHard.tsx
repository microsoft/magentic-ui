import { useState, useEffect, useCallback, memo, useRef } from "react";
import { useTaskAnalytics } from "../utils/useTaskAnalytics";
import { TaskStateManager } from "../utils/TaskStateManager";
import { TIMEOUT, SIZE, ANIMATION, COMMON } from "../config/constants";
import { generateParameterPassword } from "../utils/parameterPassword";
import { URLParameterHandler } from "../utils/urlParameterHandler";
import { useDrag, useDrop } from 'react-dnd';

export const TASK_ID_AnimalMoverHard = "animal-mover-hard";

const ItemTypes = {
  ANIMAL: 'animal',
};

interface AnimalPosition {
  id: string;
  x: number;
  y: number;
  pen: 'pen1' | 'pen2' | 'pen3'; // Three pens: left, center, right
  type: 'sheep' | 'wolf' | 'pig';
  targetX?: number;
  targetY?: number;
  velocityX: number;
  velocityY: number;
  facingLeft: boolean;
}


// Draggable Animal Component
const DraggableAnimal = ({ animal, onMove, isPenFull }: { 
  animal: AnimalPosition, 
  onMove: (id: string, x: number, y: number, pen: 'pen1' | 'pen2' | 'pen3') => void,
  isPenFull: (targetPen: 'pen1' | 'pen2' | 'pen3', currentPen: 'pen1' | 'pen2' | 'pen3') => boolean
}) => {
  const [{ isDragging }, drag] = useDrag(() => ({
    type: ItemTypes.ANIMAL,
    item: { id: animal.id },
    collect: (monitor) => ({
      isDragging: !!monitor.isDragging(),
    }),
    end: (_item, monitor) => {
      const dropResult = monitor.getDropResult<{ pen: 'pen1' | 'pen2' | 'pen3' }>();
      if (dropResult) {
        // Get actual drop position
        const clientOffset = monitor.getClientOffset();
        const dropZoneElement = document.querySelector(`[data-pen="${dropResult.pen}"]`);
        
        if (clientOffset && dropZoneElement) {
          const dropZoneRect = dropZoneElement.getBoundingClientRect();
          const relativeX = clientOffset.x - dropZoneRect.left;
          const relativeY = clientOffset.y - dropZoneRect.top;
          onMove(animal.id, relativeX, relativeY, dropResult.pen);
        } else {
          // Fallback to center of pen if drop position can't be determined
          onMove(animal.id, 175, 150, dropResult.pen);
        }
      }
    },
  }));

  const handleClick = () => {
    // Click movement: adjacent pens only
    let targetPen: 'pen1' | 'pen2' | 'pen3' | null = null;
    
    if (animal.pen === 'pen1') {
      targetPen = 'pen2'; // Pen 1 → Pen 2
    } else if (animal.pen === 'pen2') {
      // From center, animals can go back to pen1 or forward to pen3
      // Let's default to moving forward to pen3, but could be made smarter
      targetPen = 'pen3';
    } else if (animal.pen === 'pen3') {
      targetPen = 'pen2'; // Pen 3 → Pen 2 (back)
    }
    
    if (targetPen && !isPenFull(targetPen, animal.pen)) {
      // Generate random position in target pen
      const randomX = Math.random() * 270 + 40; // Between 40-310px
      const randomY = Math.random() * 220 + 40; // Between 40-260px
      onMove(animal.id, randomX, randomY, targetPen);
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
        zIndex: isDragging ? SIZE.DRAG_Z_INDEX : 1
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
const DropZone = ({ pen, children, isPenFull }: { 
  pen: 'pen1' | 'pen2' | 'pen3', 
  children: React.ReactNode,
  isPenFull?: boolean 
}) => {
  const [{ isOver }, drop] = useDrop(() => ({
    accept: ItemTypes.ANIMAL,
    drop: () => ({ pen }),
    collect: (monitor) => ({
      isOver: !!monitor.isOver(),
    }),
  }));

  return (
    <div
      ref={drop}
      data-pen={pen}
      className={`relative border-2 border-dashed border-blue-300 rounded-lg transition-all duration-300 ${
        isOver ? 'bg-blue-50 border-blue-500' : 'bg-transparent'
      }`}
    >
      {isPenFull && (pen === 'pen2' || pen === 'pen3') && (
        <div className="absolute top-2 right-2 bg-red-500 text-white text-xs px-2 py-1 rounded z-20">
          PEN FULL
        </div>
      )}
      {children}
    </div>
  );
};

const AnimalMoverHard = () => {
  // Parse URL parameters manually (don't clean yet)
  const urlParams = new URLSearchParams(window.location.search);
  const count = parseInt(urlParams.get('count') || '10', 10);
  // const showHints = urlParams.get('hints') === 'true'; // Unused
  
  // Validate count parameter
  const validCount = (count >= 1 && count <= 256) ? count : 10;
  
  // Check if validation failed and emit error for toast
  useEffect(() => {
    if (urlParams.has('count') && validCount !== count) {
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
      }, TIMEOUT.SHORT / 10); // 100ms
    }
  }, []); // Run once on mount
  
  // Create params object for shouldResetState check
  const params = { count: validCount, hasAnyParams: urlParams.has('count') };

  // Generate initial animal positions
  const generateInitialAnimals = (): AnimalPosition[] => {
    const animals: AnimalPosition[] = [];
    const penWidth = 350;
    const penHeight = 300;
    
    // Calculate number of distractors (50% of sheep count)
    const distractorCount = Math.floor(validCount / 2);
    const wolvesCount = Math.floor(distractorCount / 2);
    
    const totalAnimals = validCount + distractorCount;
    
    for (let i = 0; i < totalAnimals; i++) {
      let x: number = Math.random() * (penWidth - SIZE.ELEMENT_SIZE) + SIZE.POSITION_OFFSET;
      let y: number = Math.random() * (penHeight - SIZE.ELEMENT_SIZE) + SIZE.ELEMENT_SIZE;
      let validPosition = false;
      let attempts = 0;
      
      // Try to find a position that doesn't overlap with other animals
      while (!validPosition && attempts < ANIMATION.MAX_ATTEMPTS) {
        x = Math.random() * (penWidth - SIZE.ELEMENT_SIZE) + SIZE.POSITION_OFFSET;
        y = Math.random() * (penHeight - SIZE.ELEMENT_SIZE) + SIZE.ELEMENT_SIZE;
        
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
      if (i >= validCount) {
        // This is a distractor animal
        const distractorIndex = i - validCount;
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
        pen: 'pen1', // All start in pen 1 (left)
        type: animalType,
        velocityX: (Math.random() - 0.5) * 1,
        velocityY: (Math.random() - 0.5) * 1,
        facingLeft: Math.random() > 0.5
      });
    }
    
    return animals;
  };

  const initializeState = () => {
    const savedState = TaskStateManager.loadState(TASK_ID_AnimalMoverHard);
    
    // Check if we should reset state based on parameter changes
    if (URLParameterHandler.shouldResetState(TASK_ID_AnimalMoverHard, savedState, params)) {
      TaskStateManager.clearState(TASK_ID_AnimalMoverHard);
      
      const now = Date.now();
      const animals = generateInitialAnimals();
      const initialState = {
        startTime: now,
        animals,
        isCompleted: false,
        animalsMoved: 0,
        staticPassword: generateParameterPassword(TASK_ID_AnimalMoverHard, validCount),
        count: validCount,
        lastDriftTime: now
      };
      
      TaskStateManager.saveState(TASK_ID_AnimalMoverHard, initialState);
      return initialState;
    }
    
    if (savedState) {
      // Resume from saved state with proper type casting
      const savedCount = (savedState.count as number) || validCount;
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
          a.pen && (a.pen === 'pen1' || a.pen === 'pen2' || a.pen === 'pen3') &&
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
        animals: restoredAnimals,
        isCompleted: savedState.isCompleted as boolean || false,
        animalsMoved: savedState.animalsMoved as number || 0,
        staticPassword: generateParameterPassword(TASK_ID_AnimalMoverHard, savedCount),
        count: savedCount,
        lastDriftTime: (savedState.lastDriftTime as number) || (savedState.startTime as number)
      };
    } else {
    
      // Fresh start - same as reset case
      const now = Date.now();
      const animals = generateInitialAnimals();
      const initialState = {
        startTime: now,
        animals,
        isCompleted: false,
        animalsMoved: 0,
        staticPassword: generateParameterPassword(TASK_ID_AnimalMoverHard, validCount),
        count: validCount,
        lastDriftTime: now
      };
      
      TaskStateManager.saveState(TASK_ID_AnimalMoverHard, initialState);
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
  const [countState] = useState(initialState.count);
  const [animals, setAnimals] = useState<AnimalPosition[]>(initialState.animals);
  const [isCompleted, setIsCompleted] = useState(initialState.isCompleted);
  const [staticPassword, setStaticPassword] = useState(initialState.staticPassword || "");
  const [lastDriftTime] = useState(initialState.lastDriftTime);
  const isInitialized = useRef(false);
  const { recordSuccess } = useTaskAnalytics(TASK_ID_AnimalMoverHard);
  
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
  
  // Calculate animals in each pen
  const animalsInPen1 = animals.filter(a => a.pen === 'pen1');
  const animalsInPen2 = animals.filter(a => a.pen === 'pen2');
  const animalsInPen3 = animals.filter(a => a.pen === 'pen3');
  
  const sheepInPen3 = animals.filter(a => a.pen === 'pen3' && a.type === 'sheep').length;
  const distractorsInPen3 = animals.filter(a => a.pen === 'pen3' && a.type !== 'sheep').length;
  
  // Check if pens are full (capacity = sheep count)
  const isPenFull = useCallback((targetPen: 'pen1' | 'pen2' | 'pen3', currentPen: 'pen1' | 'pen2' | 'pen3') => {
    if (targetPen === 'pen1') return false; // Pen 1 has unlimited capacity
    if (targetPen === currentPen) return false; // Not moving anywhere
    
    const currentCount = animals.filter(a => a.pen === targetPen).length;
    return currentCount >= countState;
  }, [animals, countState]);

  // Save state whenever any state variable changes
  useEffect(() => {
    // Don't save during initial load to avoid overwriting restored state
    if (!isInitialized.current) return;
    
    const currentState = {
      startTime,
      animals,
      isCompleted,
      animalsMoved: animalsInPen2.length + animalsInPen3.length,
      staticPassword,
      count: countState,
      lastDriftTime
    };
    
    TaskStateManager.saveState(TASK_ID_AnimalMoverHard, currentState);
  }, [startTime, animals, isCompleted, staticPassword, countState, lastDriftTime, animalsInPen2.length, animalsInPen3.length]);

  // Drift mechanism: every 60 seconds, move a random sheep from pen2 or pen3 back to pen1
  // useEffect(() => {
  //   const driftInterval = setInterval(() => {
  //     const now = Date.now();
  //     if (now - lastDriftTime >= 60000) { // 60 seconds
  //       setAnimals(prevAnimals => {
  //         // Find sheep in pen2 or pen3
  //         const sheepInPen2And3 = prevAnimals.filter(a => 
  //           a.type === 'sheep' && (a.pen === 'pen2' || a.pen === 'pen3')
  //         );
  //         
  //         if (sheepInPen2And3.length > 0) {
  //           // Pick a random sheep to drift back
  //           const randomIndex = Math.floor(Math.random() * sheepInPen2And3.length);
  //           const sheepToDrift = sheepInPen2And3[randomIndex];
  //           
  //           // Move it to pen1 at a random position
  //           const randomX = Math.random() * 270 + 40;
  //           const randomY = Math.random() * 220 + 40;
  //           
  //           return prevAnimals.map(animal => 
  //             animal.id === sheepToDrift.id 
  //               ? {
  //                   ...animal,
  //                   pen: 'pen1' as const,
  //                   x: randomX,
  //                   y: randomY,
  //                   facingLeft: true,
  //                   velocityX: (Math.random() - 0.5) * 1,
  //                   velocityY: (Math.random() - 0.5) * 1
  //                 }
  //               : animal
  //           );
  //         }
  //         return prevAnimals;
  //       });
  //       
  //       setLastDriftTime(now);
  //     }
  //   }, 1000); // Check every second
  //   
  //   return () => clearInterval(driftInterval);
  // }, [lastDriftTime]);

  // Handle animal movement
  const handleAnimalMove = useCallback((id: string, x: number, y: number, pen: 'pen1' | 'pen2' | 'pen3') => {
    setAnimals(prevAnimals => {
      const animal = prevAnimals.find(a => a.id === id);
      if (!animal) return prevAnimals;

      // If moving to pen2 or pen3 and pen is full, reject the move
      if ((pen === 'pen2' || pen === 'pen3') && animal.pen !== pen) {
        const currentPenCount = prevAnimals.filter(a => a.pen === pen).length;
        if (currentPenCount >= countState) {
          return prevAnimals; // Reject the move
        }
      }

      // Pen boundaries with fence margin
      const fenceMargin = 40;
      const penWidth = 350;
      const penHeight = 300;
      const animalSize = 40;
      
      const minX = fenceMargin;
      const maxX = penWidth - fenceMargin - animalSize;
      const minY = fenceMargin;
      const maxY = penHeight - fenceMargin - animalSize;
      
      // Clamp position within boundaries
      const finalX = Math.max(minX, Math.min(maxX, x));
      const finalY = Math.max(minY, Math.min(maxY, y));
      
      // Check for collisions with other animals in the same pen and displace them
      const updatedAnimals = prevAnimals.map(a => {
        if (a.id === id) {
          return {
            ...a,
            x: finalX,
            y: finalY,
            pen,
            facingLeft: pen === 'pen1',
            velocityX: (Math.random() - 0.5) * 1,
            velocityY: (Math.random() - 0.5) * 1
          };
        }
        
        // Displace overlapping animals in the same pen
        if (a.pen === pen) {
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
      const newAnimalsInPen2AndPen3 = updatedAnimals.filter(a => a.pen === 'pen2' || a.pen === 'pen3').length;
      const currentState = {
        startTime,
        animals: updatedAnimals,
        isCompleted,
        animalsMoved: newAnimalsInPen2AndPen3,
        staticPassword,
        count: countState,
        lastDriftTime
      };
      TaskStateManager.saveStateImmediate(TASK_ID_AnimalMoverHard, currentState);
      
      return updatedAnimals;
    });
  }, [startTime, countState, isCompleted, staticPassword, lastDriftTime]);

  // Save state whenever any state variable changes (removing duplicate)
  // This is now handled above and in the main useEffect

  // Check for completion - all sheep in pen3 and no distractors in pen3
  useEffect(() => {
    const totalSheep = animals.filter(a => a.type === 'sheep').length;
    if (sheepInPen3 === totalSheep && totalSheep > 0 && distractorsInPen3 === 0 && !isCompleted) {
      const finalPassword = generateParameterPassword(TASK_ID_AnimalMoverHard, countState);
      setIsCompleted(true);
      setStaticPassword(finalPassword);
      recordSuccess();
    }
  }, [sheepInPen3, distractorsInPen3, animals, isCompleted, recordSuccess, countState]);

  // Animal movement animation with collision physics
  useEffect(() => {
    const moveInterval = setInterval(() => {
      setAnimals(prevAnimals => {
        const penWidth = 350;
        const penHeight = 300;
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
          const maxX = penWidth - fenceMargin - animalSize;
          const minY = fenceMargin;
          const maxY = penHeight - fenceMargin - animalSize;
          
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
          
          // Check collision with other animals in the same pen
          for (let i = 0; i < prevAnimals.length; i++) {
            if (i === index) continue;
            const otherAnimal = prevAnimals[i];
            if (otherAnimal.pen !== animalItem.pen) continue;
            
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
    }, COMMON.VALIDATION_DELAY);

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
    const interval = setInterval(syncWithStorage, TIMEOUT.STORAGE_SYNC);

    return () => {
      window.removeEventListener('adminConsoleToggle', handleAdminToggle as EventListener);
      window.removeEventListener('storage', handleStorageChange);
      clearInterval(interval);
    };
  }, []);

  const handleResetTask = () => {
    if (window.confirm('Are you sure you want to reset this task? This will restart the animal moving challenge from the beginning.')) {
      TaskStateManager.clearState(TASK_ID_AnimalMoverHard);
      window.location.href = `${window.location.pathname}?count=${count}`;
    }
  };

  // const nextDriftIn = Math.max(0, 60 - Math.floor((Date.now() - lastDriftTime) / 1000));


  return (
    <div className="min-h-screen bg-gradient-to-b from-sky-400 via-sky-300 to-blue-400 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Development Tools */}
        {(isLocalhost || adminConsoleEnabled) && (
          <div className="bg-gradient-to-r from-yellow-50 to-amber-50 border border-yellow-200/50 rounded-xl p-4 mb-6 shadow-sm backdrop-blur-sm">
            <div className="flex items-center justify-between text-sm">
              <div className="text-yellow-800 font-medium">
                <strong>Dev Tools:</strong> Count: {countState} | Pen1: {animalsInPen1.length} | Pen2: {animalsInPen2.length}/{countState} | Pen3: {animalsInPen3.length}/{countState} | 
                Sheep in Pen3: {sheepInPen3} | Distractors in Pen3: {distractorsInPen3} | {/* Next Drift: {nextDriftIn}s | */}
                Completed: {isCompleted ? '✅' : '❌'} |
                Persistent: {TaskStateManager.hasState(TASK_ID_AnimalMoverHard) ? '✅' : '❌'}
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

        <div className="flex gap-4 justify-center items-start">
          {/* Pen 1 */}
          <div className="text-center">
            <DropZone pen="pen1">
              <div 
                className="w-full h-full bg-gradient-to-br from-green-400 to-green-600 rounded-lg relative overflow-hidden border-8 border-amber-800"
                style={{ 
                  width: '350px', 
                  height: '300px',
                  backgroundImage: 'url("data:image/svg+xml,%3Csvg width="40" height="40" viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"%3E%3Cg fill="none" fill-rule="evenodd"%3E%3Cg fill="%23ffffff" fill-opacity="0.1"%3E%3Ccircle cx="20" cy="20" r="2"/%3E%3C/g%3E%3C/g%3E%3C/svg%3E"),repeating-linear-gradient(0deg, transparent, transparent 35px, rgba(139, 69, 19, 0.3) 35px, rgba(139, 69, 19, 0.3) 40px)',
                  boxShadow: 'inset 0 0 20px rgba(139, 69, 19, 0.3)'
                }}
              >
                {/* Fence posts */}
                <div className="absolute top-0 left-8 w-2 h-full bg-amber-900 opacity-60"></div>
                <div className="absolute top-0 right-8 w-2 h-full bg-amber-900 opacity-60"></div>
                <div className="absolute top-8 left-0 w-full h-2 bg-amber-900 opacity-60"></div>
                <div className="absolute bottom-8 left-0 w-full h-2 bg-amber-900 opacity-60"></div>
                {animalsInPen1.map(animal => (
                  <DraggableAnimal
                    key={animal.id}
                    animal={animal}
                    onMove={handleAnimalMove}
                    isPenFull={isPenFull}
                  />
                ))}
              </div>
            </DropZone>
          </div>


          {/* Pen 2 */}
          <div className="text-center">
            <DropZone pen="pen2" isPenFull={animalsInPen2.length >= countState}>
              <div 
                className="w-full h-full bg-gradient-to-br from-green-400 to-green-600 rounded-lg relative overflow-hidden border-8 border-amber-800"
                style={{ 
                  width: '350px', 
                  height: '300px',
                  backgroundImage: 'url("data:image/svg+xml,%3Csvg width="40" height="40" viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"%3E%3Cg fill="none" fill-rule="evenodd"%3E%3Cg fill="%23ffffff" fill-opacity="0.1"%3E%3Ccircle cx="20" cy="20" r="2"/%3E%3C/g%3E%3C/g%3E%3C/svg%3E"),repeating-linear-gradient(0deg, transparent, transparent 35px, rgba(139, 69, 19, 0.3) 35px, rgba(139, 69, 19, 0.3) 40px)',
                  boxShadow: 'inset 0 0 20px rgba(139, 69, 19, 0.3)'
                }}
              >
                {/* Fence posts */}
                <div className="absolute top-0 left-8 w-2 h-full bg-amber-900 opacity-60"></div>
                <div className="absolute top-0 right-8 w-2 h-full bg-amber-900 opacity-60"></div>
                <div className="absolute top-8 left-0 w-full h-2 bg-amber-900 opacity-60"></div>
                <div className="absolute bottom-8 left-0 w-full h-2 bg-amber-900 opacity-60"></div>
                {animalsInPen2.map(animal => (
                  <DraggableAnimal
                    key={animal.id}
                    animal={animal}
                    onMove={handleAnimalMove}
                    isPenFull={isPenFull}
                  />
                ))}
              </div>
            </DropZone>
          </div>


          {/* Pen 3 */}
          <div className="text-center">
            <DropZone pen="pen3" isPenFull={animalsInPen3.length >= countState}>
              <div 
                className="w-full h-full bg-gradient-to-br from-green-400 to-green-600 rounded-lg relative overflow-hidden border-8 border-amber-800"
                style={{ 
                  width: '350px', 
                  height: '300px',
                  backgroundImage: 'url("data:image/svg+xml,%3Csvg width="40" height="40" viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg"%3E%3Cg fill="none" fill-rule="evenodd"%3E%3Cg fill="%23ffffff" fill-opacity="0.1"%3E%3Ccircle cx="20" cy="20" r="2"/%3E%3C/g%3E%3C/g%3E%3C/svg%3E"),repeating-linear-gradient(0deg, transparent, transparent 35px, rgba(139, 69, 19, 0.3) 35px, rgba(139, 69, 19, 0.3) 40px)',
                  boxShadow: 'inset 0 0 20px rgba(139, 69, 19, 0.3)'
                }}
              >
                {/* Fence posts */}
                <div className="absolute top-0 left-8 w-2 h-full bg-amber-900 opacity-60"></div>
                <div className="absolute top-0 right-8 w-2 h-full bg-amber-900 opacity-60"></div>
                <div className="absolute top-8 left-0 w-full h-2 bg-amber-900 opacity-60"></div>
                <div className="absolute bottom-8 left-0 w-full h-2 bg-amber-900 opacity-60"></div>
                {animalsInPen3.map(animal => (
                  <DraggableAnimal
                    key={animal.id}
                    animal={animal}
                    onMove={handleAnimalMove}
                    isPenFull={isPenFull}
                  />
                ))}
              </div>
            </DropZone>
          </div>
        </div>


        {isCompleted && (
          <div 
            id="animal-mover-hard-status" 
            data-state="completed"
            className="mt-6 p-6 bg-gradient-to-r from-gold-200 to-yellow-200 rounded-lg text-center shadow-lg border-4 border-yellow-400 animate-pulse"
          >
            <div className="text-4xl mb-2">🏆</div>
            <h2 className="text-xl font-bold text-yellow-800 mb-2">All Sheep Successfully Sorted!</h2>
            <p className="text-yellow-700 mb-4">Congratulations! You've moved all sheep to Pen 3 while managing the drift and capacity constraints.</p>
            <span id="animal-mover-hard-code" className="text-2xl font-mono bg-yellow-100 px-4 py-2 rounded border-2 border-yellow-500">
              {staticPassword || generateParameterPassword(TASK_ID_AnimalMoverHard, countState)}
            </span>
          </div>
        )}
      </div>
    </div>
  );
};

export default memo(AnimalMoverHard);