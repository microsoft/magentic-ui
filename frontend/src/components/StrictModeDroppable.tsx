import React, { useEffect, useState } from "react";
import { Droppable, DroppableProps } from "@hello-pangea/dnd";

/**
 * StrictModeDroppable component to fix findDOMNode warning in React StrictMode
 * This component delays the rendering of Droppable to avoid double-rendering issues
 */
const StrictModeDroppable: React.FC<DroppableProps> = ({ children, ...props }) => {
  const [enabled, setEnabled] = useState(false);

  useEffect(() => {
    const animation = requestAnimationFrame(() => setEnabled(true));
    return () => {
      cancelAnimationFrame(animation);
      setEnabled(false);
    };
  }, []);

  if (!enabled) {
    return null;
  }

  return <Droppable {...props}>{children}</Droppable>;
};

export default StrictModeDroppable;