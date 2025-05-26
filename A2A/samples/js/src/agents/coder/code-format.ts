import { GenkitBeta, z } from "genkit/beta";

export const CodeMessageSchema = z.object({
  files: z.array(
    z.object({
      preamble: z.string().optional(),
      filename: z.string().optional(),
      language: z.string().optional(),
      content: z.string(),
      done: z.boolean(),
    })
  ),
  postamble: z.string().optional(),
});
export type CodeMessageData = z.infer<typeof CodeMessageSchema>;

export class CodeMessage implements CodeMessageData {
  data: CodeMessageData;

  constructor(data: CodeMessageData) {
    this.data = data;
  }

  get files() {
    return this.data.files;
  }
  get postamble() {
    return this.data.postamble;
  }

  /** Returns the first file's preamble. */
  get preamble() {
    return this.data.files[0]?.preamble || "";
  }
  /** Returns the first file's filename. */
  get filename() {
    return this.data.files[0]?.filename || "";
  }
  /** Returns the first file's language. */
  get language() {
    return this.data.files[0]?.language || "";
  }
  /** Returns the first file's content. */
  get content() {
    return this.data.files[0]?.content || "";
  }

  toJSON(): CodeMessageData {
    return this.data;
  }
}

function extractCode(source: string): CodeMessageData {
  const files: CodeMessageData["files"] = [];
  let currentPreamble = "";
  let postamble = "";

  const lines = source.split("\n");
  let inCodeBlock = false;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmedLine = line.trim();

    if (trimmedLine.startsWith("```")) {
      if (!inCodeBlock) {
        // Starting a new code block
        inCodeBlock = true;
        // Extract language and filename
        const [language, filename] = trimmedLine.substring(3).split(" ");
        // Start a new file entry
        files.push({
          preamble: currentPreamble.trim(),
          filename,
          language,
          content: "",
          done: false,
        });
        currentPreamble = "";
      } else {
        // Ending a code block
        inCodeBlock = false;
        // Mark the current file as done
        files[files.length - 1].done = true;
        // No need to reset currentPreamble here as it will be handled
        // when we start the next code block or reach the end
      }
      continue;
    }

    if (inCodeBlock) {
      // Add to the current file's content
      files[files.length - 1].content += line + "\n";
    } else {
      // If we're past all code blocks and have content, this is postamble
      if (files.length > 0 && files[files.length - 1].content) {
        postamble += line + "\n";
      } else {
        // Otherwise this is preamble for the next file
        currentPreamble += line + "\n";
      }
    }
  }

  return {
    files,
    postamble: postamble.trim(),
  };
}

export function defineCodeFormat(ai: GenkitBeta) {
  return ai.defineFormat(
    {
      name: "code",
      contentType: "text/plain",
      format: "text",
      schema: CodeMessageSchema,
    },
    () => {
      return {
        instructions: `\n\n=== Output Instructions

Output code in a markdown code block using the following format:

\`\`\`ts file.ts
// code goes here
\`\`\`

- Always include the filename on the same line as the opening code ticks.
- Always include both language and path.
- Do not include additional information other than the code unless explicitly requested.
- Ensure that you always include both the language and the file path.
- If you need to output multiple files, make sure each is in its own code block separated by two newlines.
- If you aren't working with a specific directory structure or existing file, use a descriptive filename like 'fibonacci.ts'

When generating code, always include a brief comment (using whatever comment syntax is appropriate for the languaeg) at the top that provides a short summary of what the file's purpose is, for example:

\`\`\`ts src/components/habit-form.tsx
/** HabitForm is a form for creating and editing habits to track. */
"use client";
// ... rest of code generated below
\`\`\`
`,
        parseMessage: (message) => {
          return new CodeMessage(extractCode(message.text));
        },
        parseChunk: (chunk) => {
          return new CodeMessage(extractCode(chunk.accumulatedText));
        },
      };
    }
  );
}
