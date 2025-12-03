# MagenticLite (aka Magentic 2.0) Transparency Notes

## Overview

MagenticLite (aka Magentic 2.0) is a powerful open-source agentic application that works with you to help you complete tasks across the web browser and your local file system. Built as the successor to [Magentic-UI](https://www.microsoft.com/en-us/research/publication/magentic-ui-report/), MagenticLite was optimized to work with small language models (SLMs) — making it leaner, faster, and more accessible without sacrificing capability.

Unlike its predecessor, which required SOTA frontier models to achieve desired performance, MagenticLite delivers strong agentic capabilities at a fraction of the cost and compute, while keeping you in control at critical steps.

> Looking for the previous version of Magentic-UI optimized to run with frontier models? It lives on the `magentic-ui-0.1.x` branch.

---

## What Can MagenticLite Do?

MagenticLite operates its own browser and can access folders that the user grants it access to, working fluidly across both to complete useful, real-world tasks. It can handle a wide range of tasks — from web research and form filling, to file management, data analysis, and code writing and execution.

Every reasoning trace and action is fully visible to the user. Users can steer the agent at any point, either in natural language or by directly taking control of the browser, ensuring they remain in the driver's seat throughout.

---

## Intended Uses

MagenticLite is a research prototype best suited to explore, experience, and deploy agentic assistance for tasks that require web navigation and local file system interaction.

> **MagenticLite should always be used with human supervision.**

Examples of tasks it can accomplish:

- Fill online forms and make bookings on your behalf
- Research and analyze information across the browser and your local file system
- Manage and analyze your local file system
- Complete simple coding tasks locally

MagenticLite is being shared with the research community to foster further research on agentic systems that keep people in control. It is intended to be used by domain experts who are independently capable of evaluating the quality of outputs, safety issues, and potential harms before acting on them.

---

## Out-of-Scope Uses

We do not recommend using MagenticLite in commercial or real-world applications without further testing and development. It is being released for research purposes.

MagenticLite may not work as expected if used with models other than the recommended setup: **Fara1.5** for browser use and **MagenticBrain** for orchestration and coding.

MagenticLite is **not** well suited for tasks that:

- Rely on audio or video data
- Involve long-duration tasks (e.g., summarizing 100+ papers)
- Require real-time fast actions such as playing online games

MagenticLite should always be used with a human in the loop. It was not designed or evaluated for all possible downstream purposes. Developers should consider its inherent limitations as they select use cases, and evaluate and mitigate for accuracy, safety, and fairness concerns specific to each intended downstream use.

MagenticLite should **not** be used in:

- Highly regulated domains or high-stakes situations where inaccurate outputs could suggest actions that lead to injury or negatively impact an individual's health, legal, financial, or life opportunities
- High-risk decision making (e.g., in law enforcement, legal, finance, or healthcare)

---

## How to Get Started

To begin using MagenticLite, follow instructions in the README page or check our installation guide under `/docs`.

---

## Evaluation

MagenticLite was evaluated on its ability to solve complex agentic tasks, both in standard benchmark settings and on a custom evaluation dataset designed around priority use cases.

### Evaluation Methods

Evaluations were driven by hero use cases reflecting real everyday tasks — including form filling, browser research, and file system management. A custom evaluation dataset was built around these scenarios to measure performance on tasks that reflect actual user value, complementing standard benchmarks rather than simply optimizing for them.

**Recommended models for evaluation:** MagenticLite was developed and tested using **Fara1.5** and **MagenticBrain** as the recommended model configuration. These are the models on which all evaluations and safety testing were conducted. Users may substitute other models, but performance, safety behavior, and benchmark results are not guaranteed outside of the tested configuration.

In addition to quality performance testing, MagenticLite was assessed from a Responsible AI perspective. Based on these results, mitigations were implemented to minimize susceptibility to misuse. See the [Risks and Mitigations](#risks-and-mitigations) section below.

---

## Limitations

- MagenticLite was developed for research and experimental purposes. Further testing and validation are needed before considering its application in commercial or real-world scenarios.
- MagenticLite was designed and tested primarily using the **English language**. Performance in other languages may vary and should be assessed by someone who is both an expert in the expected outputs and a native speaker of that language.
- Outputs generated by AI may include factual errors, fabrication, or speculation. Users are responsible for assessing the accuracy of generated content. All decisions leveraging outputs of the system should be made with human oversight and not be based solely on system outputs.
- All evaluations and safety testing — including critical point handling, XPIA, and code-harm tests — were conducted on the **Fara1.5 + MagenticBrain** configuration. Performance and safety behavior have not been tested on other model combinations.
- Users with limited GPU capacity may run only one of the two models, but not all use cases will be unlocked. Users who run MagenticLite without Fara should be aware that critical point detection for browser actions relies on Fara's trained behavior.
- MagenticLite inherits any biases, errors, or omissions produced by the underlying model used.
- There has not been a systematic effort to ensure that all deployment configurations are protected from all security vulnerabilities such as indirect prompt injection attacks.
- MagenticLite plans one step at a time rather than committing to a full upfront plan, making it more adaptive and easier to course-correct — a deliberate design choice for SLM-based orchestration.

A list of tasks and usage patterns that are not well supported is documented in `docs/limitations.md`.

---

## Best Practices

MagenticLite is a highly capable agent, proficient at interacting with websites, operating over local files, and writing or executing Python code. Like all LLM-based systems, it can and will make mistakes. To safely operate MagenticLite:

- **Always run it within Quicksand**, a Python wrapper for QEMU VM that provides strong isolation boundaries and is available as part of this open-source release. Strictly limit its access to only essential resources — avoid exposing unnecessary files, folders, or credentials to the agent.
- **Avoid logging into websites** through the agent unnecessarily.
- **Never share sensitive data** you would not confidently send to external providers. MagenticLite shares browser screenshots with model providers, including all data entered on websites within its browser session.
- **Ensure careful human oversight:** meticulously review proposed actions and monitor progress before giving approval.
- **Approach outputs with appropriate skepticism** — MagenticLite can hallucinate, misattribute sources, or be misled by deceptive or low-quality online content.

We strongly encourage users to pair MagenticLite with models that support robust Responsible AI mitigations. For reference on responsible AI best practices:

- [Announcing new AI safety & Responsible AI features in Azure](https://techcommunity.microsoft.com/t5/ai-azure-ai-services-blog/announcing-new-ai-safety-amp-responsible-ai-features-in-azure/ba-p/3983686)
- [Azure OpenAI Overview](https://learn.microsoft.com/en-us/legal/cognitive-services/openai/overview)
- [Azure OpenAI Transparency Note](https://learn.microsoft.com/en-us/legal/cognitive-services/openai/transparency-note)
- [OpenAI Usage Policies](https://openai.com/policies/usage-policies)
- [Azure OpenAI Code of Conduct](https://learn.microsoft.com/en-us/legal/cognitive-services/openai/code-of-conduct)

Users are reminded to be mindful of data privacy concerns and are encouraged to review the privacy policies associated with any models and data storage solutions interfacing with MagenticLite. It is the user's responsibility to ensure that the use of MagenticLite complies with relevant data protection regulations and organizational guidelines.

---

## Risks and Mitigations

The risk surface spans the files and websites the agents have access to. The two primary risk categories are:

- **Data leakage from prompt injection.** Untrusted content encountered in the browser or in user-supplied files may attempt to manipulate the agent into exfiltrating data or taking unintended actions. MagenticLite shares browser screenshots with model providers, including any data entered on websites within its session.
- **Undesired or destructive actions** across the user's local file system, the operated browser, or executed code — including irreversible operations the user did not intend to authorize.

### Mitigations

MagenticLite mitigates these risks through a layered approach:

- **Sandboxed execution environment.** All browser sessions and code execution happen inside Quicksand, a Python wrapper around a QEMU VM that provides strong isolation boundaries from the host system. This limits the blast radius of both prompt injection and undesired actions.
- **Human intervention at critical points in the browser.** Fara's training surfaces actions that warrant user approval (e.g., transactions, irreversible submissions, login flows), pausing for explicit user confirmation before proceeding.
- **Code action classification at the MagenticLite harness level.** The allow / require_approval / deny tables categorize every tool call and bash command from the Orchestrator model, blocking destructive operations and routing risky ones through user approval.
- **User guidance on limiting data exposure.** We recommend that users:
  - Grant the agent access to only the folders strictly necessary for the task
  - Avoid logging into websites through the agent unless required
  - Never share sensitive data they would not confidently send to external model providers
  - Use the recommended model configuration (Fara1.5 + MagenticBrain), where critical point detection has been tested

Users who choose to disable Fara, substitute alternative models, or run MagenticLite outside the sandboxed VM forfeit one or more of these mitigations and should evaluate the residual risk for their use case.

### How Critical Point Detection Works

In Magentic-UI 0.1, critical point detection was handled by prompting the configured frontier model (e.g., GPT-4o) to flag actions that warranted user review. This prompting-based safety layer no longer exists in this release. Instead, critical point detection has been moved closer to where each kind of action originates:

**Browser actions → handled by Fara's trained behavior.**
The need for human intervention in browser use is rarely black-and-white and contains many gray areas. Rather than rely on post-hoc prompting, we trained Fara on traces that include correctly calibrated critical points, so the model itself learns when to surface an action for user approval. This generalizes better than prompting and avoids the latency overhead of routing each step through a separate large model. Users who do not run Fara should be aware that this safeguard depends on Fara's training and is not provided by MagenticLite itself.

**Code and tool actions → handled by the MagenticLite harness.**
MagenticBrain works with a discrete set of tools and bash commands, which makes a deterministic, list-based approach well-suited. The harness applies an **allow / require_approval / deny** classification to every tool call and bash command before execution:

| Classification | Description |
|---|---|
| **Allow** | Low-risk, reversible actions execute automatically (e.g., reading a file, listing a directory) |
| **Require approval** | Actions with potential side effects pause and prompt the user for explicit approval before running |
| **Deny** | Destructive or irreversible actions (e.g., recursive deletes outside the working folder, certain network operations) are blocked outright |

This split — model-level for browser, harness-level for code — reflects the different shapes of the two action spaces: continuous and ambiguous in the browser, discrete and enumerable in code.

> **Important note for users familiar with Magentic-UI 0.1:** Because critical point detection is no longer provided by MagenticLite itself, running this release with a browser-use model other than Fara, or with a coding model that bypasses the harness, will not give you the same safety behavior that was tested and approved in 0.1. We strongly recommend the recommended model configuration described above.

---

## License

**MIT License**

Nothing disclosed here, including the Out of Scope Uses section, should be interpreted as or deemed a restriction or modification to the license the code is released under.

---

## Contact

We welcome feedback and collaboration from our audience. If you have suggestions, questions, or observe unexpected/offensive behavior in our technology, please contact us at [magui@service.microsoft.com](mailto:magui@service.microsoft.com).

If the team receives reports of undesired behavior or identifies issues independently, we will update this repository with appropriate mitigations.
