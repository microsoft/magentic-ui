# Limitations

MagenticLite is a research prototype. Some things it doesn't handle well today:

- **Summarization is limited.** Tasks that ask MagenticLite to read a long source and produce a faithful summary often miss important content or oversimplify.
- **Long multi-turn conversations degrade.** Quality drops as the conversation history grows, especially for tasks that require keeping many earlier details in mind.
- **Steering may not always stick.** Even when you successfully redirect the browser-use agent ([Fara](https://aka.ms/fara-foundry)) mid-task, [MagenticBrain](https://aka.ms/MagenticBrain-foundry) may ignore your correction once Fara returns and dispatch Fara back to the original sub-task. The agent's overall plan can be stubborn that way.
- **Very large files or contexts don't fit.** Tasks that require reading or producing very large documents (well beyond a typical chat-sized prompt) will fail or truncate.
- **Uploading files inside the browser isn't supported.** The browser-use agent cannot complete flows that require attaching a file from your local disk through a webpage's upload control.
- **Images aren't supported as task inputs.** Any task that hinges on the agent opening an image file you provide (e.g. "describe this picture", "extract text from this screenshot") will not succeed.

If you hit something not on this list and aren't sure whether it's expected, please file an issue.
