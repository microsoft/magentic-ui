import { useEffect } from "react";

interface SessionWebSocket {
  socket: WebSocket;
  runId: string;
}

type SessionWebSockets = {
  [sessionId: number]: SessionWebSocket;
};

/**
 * Development-only hook for debugging WebSocket messages
 * Exposes global debugMagenticUI object in browser console
 */
export const useWebSocketDebug = (sessionSockets: SessionWebSockets) => {
  useEffect(() => {
    if (typeof window !== "undefined" && process.env.NODE_ENV === "development") {
      (window as any).debugMagenticUI = {
        getSockets: () => {
          const sessionIds = Object.keys(sessionSockets).map(Number);
          console.log("Available sessions:", sessionIds);
          console.log("Session details:", sessionSockets);
          return sessionSockets;
        },

        triggerError: (sessionId: number, errorMessage?: string) => {
          const socket = sessionSockets[sessionId]?.socket;
          if (!socket || socket.readyState !== WebSocket.OPEN) {
            console.error(`❌ No active socket for session ${sessionId}`);
            console.log(
              "Available sessions:",
              Object.keys(sessionSockets).map(Number)
            );
            return false;
          }

          const mockEvent = new MessageEvent("message", {
            data: JSON.stringify({
              type: "error",
              error: errorMessage || "Console triggered test error",
              timestamp: new Date().toISOString(),
            }),
          });

          socket.dispatchEvent(mockEvent);
          console.log(`✅ Error triggered for session ${sessionId}`);
          return true;
        },

        help: () => {
          console.log(`
🔧 Magentic-UI Debug Tools
==========================

Available commands:

1. debugMagenticUI.getSockets()
   - List all active WebSocket connections
   - Shows session IDs and socket details

2. debugMagenticUI.triggerError(sessionId, message?)
   - Trigger an error message for a session
   - Example: debugMagenticUI.triggerError(1, "API rate limit exceeded")

3. debugMagenticUI.help()
   - Show this help message

Note: These tools are only available in development mode.
          `);
        },
      };

      console.log("🔧 Debug tools available: window.debugMagenticUI");
      console.log("   Type debugMagenticUI.help() for usage instructions");
    }

    return () => {
      if (typeof window !== "undefined") {
        delete (window as any).debugMagenticUI;
      }
    };
  }, [sessionSockets]);
};
