import { z } from "zod";

export const StdioServerParamsSchema = z.object({
    type: z.literal("StdioServerParams"),
    command: z.string(),
    args: z.array(z.string()).optional(),
    read_timeout_seconds: z.number().gt(0).optional(),
})

export type StdioServerParams = z.infer<typeof StdioServerParamsSchema>

export const SseServerParamsSchema = z.object({
    type: z.literal("SseServerParams"),
    url: z.string(),
    headers: z.record(z.string()).optional(),
    timeout: z.number().gt(0).optional(),
    sse_read_timeout: z.number().gt(0).optional(),
})

export type SseServerParams = z.infer<typeof SseServerParamsSchema>

export const MCPServerConfigSchema = z.discriminatedUnion("type", [
    StdioServerParamsSchema, SseServerParamsSchema
]);

export type MCPServerConfig = z.infer<typeof MCPServerConfigSchema>;

export const NamedMCPServerConfigSchema = z.object({
    server_name: z.string().regex(/^[A-Za-z]+[A-Za-z0-9]*$/, "Only letters and numbers are allowed and the name must be a valid python identifier."),
    server_params: MCPServerConfigSchema,
});

export type NamedMCPServerConfig = z.infer<typeof NamedMCPServerConfigSchema>;