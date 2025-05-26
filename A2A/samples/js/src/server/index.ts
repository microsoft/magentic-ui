/**
 * Main entry point for the A2A Server V2 library.
 * Exports the server class, store implementations, and core types.
 */

// Export the main server class and its options
export { A2AServer } from "./server.js";
export type { A2AServerOptions } from "./server.js";

// Export handler-related types
export type { TaskHandler, TaskContext, TaskYieldUpdate } from "./handler.js";

// Export store-related types and implementations
export type { TaskStore } from "./store.js";
export { InMemoryTaskStore, FileStore } from "./store.js";

// Export the custom error class
export { A2AError } from "./error.js";

// Re-export all schema types for convenience
export * as schema from "../schema.js";

// Example basic usage (for documentation or testing)
/*
import { A2AServer, TaskContext, TaskYieldUpdate, schema } from './index.js';
import { v4 as uuidv4 } from 'uuid'; // Assuming uuid is installed

async function* mySimpleHandler(context: TaskContext): AsyncGenerator<TaskYieldUpdate, schema.Task | void, unknown> {
  console.log(`Handling task ${context.task.id}`);
  yield { state: 'working', message: { role: 'agent', parts: [{ text: 'Working on it...' }] } };

  // Simulate work
  await new Promise(resolve => setTimeout(resolve, 1500));

  if (context.isCancelled()) {
     console.log("Task cancelled!");
     return;
  }

  yield {
    name: 'output.txt',
    parts: [{ text: `Result for task ${context.task.id}` }],
  };

  yield { state: 'completed', message: { role: 'agent', parts: [{ text: 'Done!' }] } };
}

// Create and start the server (e.g., using InMemoryTaskStore)
const server = new A2AServer(mySimpleHandler);
server.start();

console.log("Example server started on port 41241");

// To test (using curl or similar):
// 1. Send a task:
// curl -X POST http://localhost:41241 -H "Content-Type: application/json" -d \
// '{
//   "jsonrpc": "2.0",
//   "method": "tasks/send",
//   "id": 1,
//   "params": {
//     "id": "'$(uuidgen)'",
//     "message": {
//       "role": "user",
//       "parts": [{"text": "Please do the thing."}]
//     }
//   }
// }'
//
// 2. Send and subscribe:
// curl -N -X POST http://localhost:41241 -H "Content-Type: application/json" -d \
// '{
//   "jsonrpc": "2.0",
//   "method": "tasks/sendSubscribe",
//   "id": 2,
//   "params": {
//      "id": "'$(uuidgen)'",
//      "message": {
//        "role": "user",
//        "parts": [{"text": "Please do the streaming thing."}]
//      }
//    }
// }'
*/
