/**
 * Represents a single step in a plan
 */
export interface IPlanStep {
  title: string;
  details: string;
  enabled?: boolean;
  open?: boolean;
  agent_name?: string;
}

/**
 * Represents a complete plan with metadata
 */
export interface IPlan {
  id?: number;           // Plan ID (optional for new plans)
  task: string;          // The task this plan addresses
  steps: IPlanStep[];    // Array of plan steps
  created_at?: string;   // Creation timestamp
  updated_at?: string;   // Last update timestamp
  user_id?: string;      // Owner of the plan

  // Session tracking fields
  sessionId?: number;    // Associated session ID for processing
  messageId?: string;    // Message ID for deduplication

  // For backend plan representation
  plan_summary?: string; // Summary description of the plan
  session_id?: number | null;
}

/**
 * Default empty plan
 */
export const emptyPlan: IPlan = {
  task: "",
  steps: [
    {
      title: "Loading Plan...",
      details: "",
      enabled: false,
      agent_name: "",
    }
  ]
};

/**
 * Default plan template with example steps
 */
export const defaultPlan: IPlan = {
  task: "Example task",
  steps: [
    {
      title: "Initiate Web Search",
      details: "Ask WebSurfer to perform a web search for relevant information.",
      enabled: true,
      agent_name: "WebSurfer",
    },
    {
      title: "Summarize Key Findings",
      details: "Request WebSurfer to summarize the top results or key information found.",
      enabled: true,
      agent_name: "WebSurfer",
    },
    {
      title: "Validate Information",
      details: "Ensure that the information gathered is from credible sources.",
      enabled: true,
      agent_name: "WebSurfer",
    }
  ]
};

/**
 * Convert a JSON string to an array of IPlanStep objects
 */
export function convertToIPlanSteps(jsonString: string): IPlanStep[] {
  try {
    const parsedArray = JSON.parse(jsonString);
    const stepsArray = Array.isArray(parsedArray) ? parsedArray : [parsedArray];

    const planSteps: IPlanStep[] = stepsArray.map((item: any) => ({
      title: item.title || "Untitled Step",
      details: item.details || "",
      enabled: item.enabled !== undefined ? item.enabled : true,
      agent_name: item.agent_name || "",
    }));

    return planSteps;
  } catch (e) {
    console.error("Failed to parse plan JSON:", e);
    return [];
  }
}

/**
 * Convert plan steps to a JSON string
 */
export function convertPlanStepsToJsonString(steps: IPlanStep[]): string {
  if (!steps || !Array.isArray(steps)) {
    console.error("Invalid steps array passed to convertPlanStepsToJsonString:", steps);
    return JSON.stringify([]);
  }

  const filteredSteps = steps.filter(step => step.enabled !== false);

  const cleanedSteps = filteredSteps.map(({ title, details, agent_name }) => ({
    title,
    details,
    agent_name,
  }));

  return JSON.stringify(cleanedSteps);
}
