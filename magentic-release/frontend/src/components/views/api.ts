import { Session, SessionRuns } from "../types/datamodel";
import { getServerUrl } from "../utils";
import { Team, AgentConfig } from "../types/datamodel";
export class SessionAPI {
  private getBaseUrl(): string {
    return getServerUrl();
  }

  private getHeaders(): HeadersInit {
    return {
      "Content-Type": "application/json",
    };
  }

  async listSessions(userId: string): Promise<Session[]> {
    const response = await fetch(
      `${this.getBaseUrl()}/sessions/?user_id=${userId}`,
      {
        headers: this.getHeaders(),
      }
    );
    const data = await response.json();
    if (!data.status)
      throw new Error(data.message || "Failed to fetch sessions");
    return data.data;
  }

  async getSession(sessionId: number, userId: string): Promise<Session> {
    const response = await fetch(
      `${this.getBaseUrl()}/sessions/${sessionId}?user_id=${userId}`,
      {
        headers: this.getHeaders(),
      }
    );
    const data = await response.json();
    if (!data.status)
      throw new Error(data.message || "Failed to fetch session");
    return data.data;
  }

  async createSession(
    sessionData: Partial<Session>,
    userId: string
  ): Promise<Session> {
    const session = {
      ...sessionData,
      user_id: userId, // Ensure user_id is included
    };

    const response = await fetch(`${this.getBaseUrl()}/sessions/`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify(session),
    });
    const data = await response.json();
    if (!data.status)
      throw new Error(data.message || "Failed to create session");
    return data.data;
  }

  async updateSession(
    sessionId: number,
    sessionData: Partial<Session>,
    userId: string
  ): Promise<Session> {
    const session = {
      ...sessionData,
      id: sessionId,
      user_id: userId, // Ensure user_id is included
    };

    const response = await fetch(
      `${this.getBaseUrl()}/sessions/${sessionId}?user_id=${userId}`,
      {
        method: "PUT",
        headers: this.getHeaders(),
        body: JSON.stringify(session),
      }
    );
    const data = await response.json();
    if (!data.status)
      throw new Error(data.message || "Failed to update session");
    return data.data;
  }

  // session runs with messages
  async getSessionRuns(
    sessionId: number,
    userId: string
  ): Promise<SessionRuns> {
    const response = await fetch(
      `${this.getBaseUrl()}/sessions/${sessionId}/runs?user_id=${userId}`,
      {
        headers: this.getHeaders(),
      }
    );
    const data = await response.json();
    if (!data.status)
      throw new Error(data.message || "Failed to fetch session runs");
    return data.data; // Returns { runs: RunMessage[] }
  }

  async deleteSession(sessionId: number, userId: string): Promise<void> {
    const response = await fetch(
      `${this.getBaseUrl()}/sessions/${sessionId}?user_id=${userId}`,
      {
        method: "DELETE",
        headers: this.getHeaders(),
      }
    );
    const data = await response.json();
    if (!data.status)
      throw new Error(data.message || "Failed to delete session");
  }

  // Adding messages endpoint
  async listSessionMessages(sessionId: number, userId: string): Promise<any[]> {
    // Replace 'any' with proper message type
    const response = await fetch(
      `${this.getBaseUrl()}/sessions/${sessionId}/messages?user_id=${userId}`,
      {
        headers: this.getHeaders(),
      }
    );
    const data = await response.json();
    if (!data.status)
      throw new Error(data.message || "Failed to fetch messages");
    return data.data;
  }
}

export class TeamAPI {
  private getBaseUrl(): string {
    return getServerUrl();
  }

  private getHeaders(): HeadersInit {
    return {
      "Content-Type": "application/json",
    };
  }

  async listTeams(userId: string): Promise<Team[]> {
    const response = await fetch(
      `${this.getBaseUrl()}/teams/?user_id=${userId}`,
      {
        headers: this.getHeaders(),
      }
    );
    const data = await response.json();
    if (!data.status) throw new Error(data.message || "Failed to fetch teams");
    return data.data;
  }

  async getTeam(teamId: number, userId: string): Promise<Team> {
    const response = await fetch(
      `${this.getBaseUrl()}/teams/${teamId}?user_id=${userId}`,
      {
        headers: this.getHeaders(),
      }
    );
    const data = await response.json();
    if (!data.status) throw new Error(data.message || "Failed to fetch team");
    return data.data;
  }

  async createTeam(teamData: Partial<Team>, userId: string): Promise<Team> {
    const team = {
      ...teamData,
      user_id: userId,
    };

    const response = await fetch(`${this.getBaseUrl()}/teams/`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify(team),
    });
    const data = await response.json();
    if (!data.status) throw new Error(data.message || "Failed to create team");
    return data.data;
  }

  async deleteTeam(teamId: number, userId: string): Promise<void> {
    const response = await fetch(
      `${this.getBaseUrl()}/teams/${teamId}?user_id=${userId}`,
      {
        method: "DELETE",
        headers: this.getHeaders(),
      }
    );
    const data = await response.json();
    if (!data.status) throw new Error(data.message || "Failed to delete team");
  }

  // Team-Agent Link Management
  async linkAgent(teamId: number, agentId: number): Promise<void> {
    const response = await fetch(
      `${this.getBaseUrl()}/teams/${teamId}/agents/${agentId}`,
      {
        method: "POST",
        headers: this.getHeaders(),
      }
    );
    const data = await response.json();
    if (!data.status)
      throw new Error(data.message || "Failed to link agent to team");
  }

  async linkAgentWithSequence(
    teamId: number,
    agentId: number,
    sequenceId: number
  ): Promise<void> {
    const response = await fetch(
      `${this.getBaseUrl()}/teams/${teamId}/agents/${agentId}/${sequenceId}`,
      {
        method: "POST",
        headers: this.getHeaders(),
      }
    );
    const data = await response.json();
    if (!data.status)
      throw new Error(
        data.message || "Failed to link agent to team with sequence"
      );
  }

  async unlinkAgent(teamId: number, agentId: number): Promise<void> {
    const response = await fetch(
      `${this.getBaseUrl()}/teams/${teamId}/agents/${agentId}`,
      {
        method: "DELETE",
        headers: this.getHeaders(),
      }
    );
    const data = await response.json();
    if (!data.status)
      throw new Error(data.message || "Failed to unlink agent from team");
  }

  async getTeamAgents(teamId: number): Promise<AgentConfig[]> {
    const response = await fetch(
      `${this.getBaseUrl()}/teams/${teamId}/agents`,
      {
        headers: this.getHeaders(),
      }
    );
    const data = await response.json();
    if (!data.status)
      throw new Error(data.message || "Failed to fetch team agents");
    return data.data;
  }
}

export class PlanAPI {
  private getBaseUrl(): string {
    return getServerUrl();
  }

  private getHeaders(): HeadersInit {
    return {
      "Content-Type": "application/json",
    };
  }

  async listPlans(userId: string): Promise<any[]> {
    const response = await fetch(
      `${this.getBaseUrl()}/plans/?user_id=${userId}`,
      {
        headers: this.getHeaders(),
      }
    );
    const data = await response.json();
    if (!data.status) throw new Error(data.message || "Failed to fetch plans");
    return data.data;
  }

  async getPlan(planId: number, userId: string): Promise<any> {
    const response = await fetch(
      `${this.getBaseUrl()}/plans/${planId}?user_id=${userId}`,
      {
        headers: this.getHeaders(),
      }
    );
    const data = await response.json();
    if (!data.status) throw new Error(data.message || "Failed to fetch plan");
    return data.data;
  }

  async createPlan(planData: Partial<any>, userId: string): Promise<any> {
    const plan = {
      ...planData,
      user_id: userId,
    };

    const response = await fetch(`${this.getBaseUrl()}/plans/`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify(plan),
    });
    const data = await response.json();
    if (!data.status) throw new Error(data.message || "Failed to create plan");
    return data.data;
  }

  async updatePlan(
    planId: number,
    planData: Partial<any>,
    userId: string
  ): Promise<any> {
    if (!planData.task) {
      console.error("Missing task in planData:", planData);
    }
    if (!planData.steps || !Array.isArray(planData.steps)) {
      console.error("Missing or invalid steps in planData:", planData);
    }

    const { created_at, ...dataWithoutCreatedAt } = planData;

    const plan = {
      ...dataWithoutCreatedAt,
      id: planId,
      user_id: userId,
      updated_at: null, // This will be replaced by the server with current time
    };

    try {
      const response = await fetch(
        `${this.getBaseUrl()}/plans/${planId}?user_id=${userId}`,
        {
          method: "PUT",
          headers: this.getHeaders(),
          body: JSON.stringify(plan),
        }
      );

      const data = await response.json();
      if (!data.status)
        throw new Error(data.message || "Failed to update plan");
      return data.data;
    } catch (error) {
      console.error("Error in updatePlan:", error);
      throw error;
    }
  }

  async deletePlan(planId: number, userId: string): Promise<void> {
    try {
      const response = await fetch(
        `${this.getBaseUrl()}/plans/${planId}?user_id=${userId}`,
        {
          method: "DELETE",
          headers: this.getHeaders(),
        }
      );

      if (!response.ok) {
        throw new Error(
          `Failed to delete plan. Server responded with status: ${response.status}`
        );
      }

      const data = await response.json();

      if (!data.status) {
        throw new Error(data.message || "Failed to delete plan");
      }
    } catch (error) {
      throw error;
    }
  }

  async learnPlan(sessionId: number, userId: string): Promise<any> {
    try {
      const response = await fetch(`${this.getBaseUrl()}/plans/learn_plan`, {
        method: "POST",
        headers: this.getHeaders(),
        body: JSON.stringify({
          session_id: sessionId,
          user_id: userId,
        }),
      });

      if (!response.ok) {
        // Log the complete error response
        const errorText = await response.text();
        console.error("Full error response:", errorText);
        try {
          const errorData = JSON.parse(errorText);
          throw new Error(errorData.detail || response.statusText);
        } catch (e) {
          throw new Error(
            `${response.status} ${response.statusText}: ${errorText}`
          );
        }
      }

      return await response.json();
    } catch (error) {
      console.error("Error learning plan:", error);
      throw error;
    }
  }
}

export class SettingsAPI {
  private getBaseUrl(): string {
    return getServerUrl();
  }

  private getHeaders(): HeadersInit {
    return {
      "Content-Type": "application/json",
    };
  }

  async getSettings(userId: string): Promise<Record<string, any>> {
    const response = await fetch(
      `${this.getBaseUrl()}/settings/?user_id=${userId}`,
      {
        headers: this.getHeaders(),
      }
    );
    const data = await response.json();
    if (!data.status)
      throw new Error(data.message || "Failed to fetch settings");
    return data.data.config || {}; // Return just the config object
  }

  async updateSettings(
    userId: string,
    config: Record<string, any>
  ): Promise<void> {
    const response = await fetch(`${this.getBaseUrl()}/settings/`, {
      method: "PUT",
      headers: this.getHeaders(),
      body: JSON.stringify({
        user_id: userId,
        config: config,
      }),
    });
    const data = await response.json();
    if (!data.status)
      throw new Error(data.message || "Failed to update settings");
  }
}

export const teamAPI = new TeamAPI();
export const sessionAPI = new SessionAPI();
export const planAPI = new PlanAPI();
export const settingsAPI = new SettingsAPI();
