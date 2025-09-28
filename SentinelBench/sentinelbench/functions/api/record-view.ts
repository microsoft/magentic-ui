import { D1Database } from "@cloudflare/workers-types";

interface Env {
  DB: D1Database;
}

export interface TaskView {
  taskId: string;
  userId: string;
  viewTime: string; // ISO string
  host: string;
  url: string;
}

export const onRequestPost = async (context: {
  request: Request;
  env: Env;
}) => {
  try {
    const data: TaskView = await context.request.json();

    await context.env.DB.prepare(
      `INSERT INTO views (task_id, view_time, user_agent, ip_address, user_id, host, url)
       VALUES (?, ?, ?, ?, ?, ?, ?)`
    )
      .bind(
        data.taskId,
        data.viewTime,
        context.request.headers.get("User-Agent") || "",
        context.request.headers.get("CF-Connecting-IP") || "",
        data.userId || "",
        data.host,
        data.url
      )
      .run();

    return new Response(JSON.stringify({ success: true }), {
      headers: { "Content-Type": "application/json" },
      status: 200,
    });
  } catch (error) {
    console.error("Error saving task view:", error);
    return new Response(
      JSON.stringify({
        success: false,
        error: "Failed to save task view",
      }),
      {
        headers: { "Content-Type": "application/json" },
        status: 500,
      }
    );
  }
};
