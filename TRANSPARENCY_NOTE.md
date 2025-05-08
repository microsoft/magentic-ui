# Magentic-UI

## OVERVIEW

Magentic-UI is a human-centered computer use agent (CUA) **designed for collaboration with people** on web-based tasks. Magentic-UI operates a web browser and other tools, like code execution and file navigation, in real-time while optimizing for human-in-the-loop (HIL) orchestration.

### What Can Magentic-UI Do?

Magentic-UI was developed to investigate human-in-the-loop approaches for agentic design with the goals to improve agentic performance and increase user productivity for web tasks. Magentic-UI strongly involves the user throughout the planning and execution phase. Magentic-UI prompts the user to accept a plan before starting execution. Plans can be modified, saved and re-used.

### Intended Uses

Magentic-UI is a research prototype best suited to explore, experience and investigate agentic assistance in performing tasks that require web navigation. Magentic-UI should always be used with human supervision.

Below are examples of tasks that Magentic-UI can accomplish:

- Check the price of a coffee from the closest coffee shops to a certain destination
- Create a formatted spreadsheet containing the box score statistics of all NBA games that occurred on a certain date
- Summarize in a report a set of papers each downloaded from a given URL, such as the latest papers from arxiv on a certain topic

Magentic-UI is being shared with the research community to foster further research on human-in-the-loop in agentic systems.

Magentic-UI is intended to be used by domain experts who are independently capable of evaluating the quality of outputs, safety issues and potential harm before acting on them. OUT-of-scope uses

We do not recommend using Magentic-UI in commercial or real-world applications without further testing and development. It is being released for research purposes.

Magentic-UI is not well suited for tasks that: rely on audio or video data to process, long-duration tasks (e.g., summarize 100 papers) or tasks that require real-time fast actions like playing online games.

Magentic-UI should always be used with a human-in-the-loop. While we support an autonomous version of Magentic-UI in our code for the purposes of evaluation, this version is not included in the interface and should only be used for evaluation purposes and nothing else. We discourage the use of the autonomous version as it does not possess the same safety safeguards as the human-in-the-loop version through the interface and has not undergone the same safety testing.

Magentic-UI was not designed or evaluated for all possible downstream purposes. Developers should consider its inherent limitations as they select use cases, and evaluate and mitigate for accuracy, safety, and fairness concerns specific to each intended downstream use.

Magentic-UI should not be used in highly regulated domains or high stakes situations where inaccurate outputs could suggest actions that lead to injury or negatively impact an individual's health, legal, and financial, life opportunities or legal status.

We do not recommend using Magentic-UI in the context of high-risk decision making (e.g. in law enforcement, legal, finance, or healthcare).

## HOW TO GET STARTED

To begin using Magentic-UI, follow instructions at [microsoft/magentic-ui: Magentic-UI](https://github.com/microsoft/magentic-ui)

## EVALUATION

Magentic-UI was evaluated on its ability to autonomously solve complex tasks from benchmarks such as GAIA. Magentic-UI autonomously tries to complete these tasks and its final answer is judged with respect to the ground truth answer. To evaluate a human-in-the-loop set-up we also evaluated Magentic-UI with a simulated user with an interactive version of the GAIA benchmark.

### Evaluation Methods

We compared the performance of Magentic-UI against [Magentic-One](https://github.com/microsoft/autogen/tree/gaia_multiagent_v01_march_1st/samples/tools/autogenbench/scenarios/GAIA/Templates/Orchestrator) on the, [GAIA](https://arxiv.org/abs/2311.12983) benchmark. When running autonomously Magentic-UI shows comparable performance to Magentic-One (which previously achieved sota results on GAIA) and higher accuracy with simulated human-in-the-loop.

The model used for evaluation was GPT-4o from Azure OpenAI. Results may vary if Magentic-UI is used with a different model, or when using other models for evaluation, based on their unique design, configuration and training.

In addition to robust quality performance testing, Magentic-UI was assessed from a Responsible AI perspective. Based on these results, we implemented mitigations to minimize Magentic-UI s susceptibility to misuse. See details in risks and mitigation section below.

### Evaluation Results

At a high level, we found that Magentic-UI performed similarly to [Magentic-One](https://github.com/microsoft/autogen/tree/gaia_multiagent_v01_march_1st/samples/tools/autogenbench/scenarios/GAIA/Templates/Orchestrator) on autonomous task completion and better with simulated human-in-the-loop.

## LIMITATIONS

Magentic-UI was developed for research and experimental purposes. Further testing and validation are needed before considering its application in commercial or real-world scenarios.

Magentic-UI was designed and tested using the English language. Performance in other languages may vary and should be assessed by someone who is both an expert in the expected outputs and a native speaker of that language.

Outputs generated by AI may include factual errors, fabrication, or speculation. Users are responsible for assessing the accuracy of generated content. All decisions leveraging outputs of the system should be made with human oversight and not be based solely on system outputs.

Magentic-UI inherits any biases, errors, or omissions produced by the model used. Developers are advised to choose an appropriate base LLM/MLLM carefully, depending on the intended use case.

There has not been a systematic effort to ensure that systems using Magentic-UI are protected from security vulnerabilities such as indirect prompt injection attacks. Any systems using it should take proactive measures to harden their systems as appropriate.

## BEST PRACTICES

Magentic-UI is a highly capable agent, proficient at interacting with websites, operating over local files, and writing or executing Python code, but like all LLM-based systems, it can and will make mistakes. To safely operate Magentic-UI, always run it within the provided Docker containers, and strictly limit its access to only essential resources avoid sharing unnecessary files, folders, or logging into websites through the agent. Never share sensitive data you wouldn't confidently send to external providers like Azure or OpenAI. Magentic-UI shares browser screenshots with model providers including all data users choose to enter on websites in Magentic-UI s browser. Ensure careful human oversight by meticulously reviewing proposed actions and monitoring progress before giving approval. Finally, approach its output with appropriate skepticism; Magentic-UI can hallucinate, misattribute sources, or be misled by deceptive or low-quality online content.

We strongly encourage users to use LLMs/MLLMs that support robust Responsible AI mitigations, such as Azure Open AI (AOAI) services. Such services continually update their safety and RAI mitigations with the latest industry standards for responsible use. For more on AOAI s best practices when employing foundations models for scripts and applications:

- [Blog post on responsible AI features in AOAI that were presented at Ignite 2023](https://techcommunity.microsoft.com/t5/ai-azure-ai-services-blog/announcing-new-ai-safety-amp-responsible-ai-features-in-azure/ba-p/3983686)
- [Overview of Responsible AI practices for Azure OpenAI models] (https://learn.microsoft.com/en-us/legal/cognitive-services/openai/overview)
- [Azure OpenAI Transparency Note](<https://learn.microsoft.com/en-us/legal/cognitive-services/openai/transparency-note>)
- [OpenAI s Usage policies](https://openai.com/policies/usage-policies)
- [Azure OpenAI s Code of Conduct](https://learn.microsoft.com/en-us/legal/cognitive-services/openai/code-of-conduct)

Users are reminded to be mindful of data privacy concerns and are encouraged to review the privacy policies associated with any models and data storage solutions interfacing with Magentic-UI.

It is the user s responsibility to ensure that the use of Magentic-UI complies with relevant data protection regulations and organizational guidelines.

For benchmarking purposes Magentic-UI has an autonomous mode that deactivates human-in-the-loop components such as co-planning and co-execution. This mode is not accessible through the UI, we strongly encourage to limit it s usage to benchmark scenarios.

## RISKS AND MITIGATIONS

Human agency and oversight are foundational to Magentic-UI s design. From the ground up, Magentic-UI was created with a human-in-the-loop (HIL) philosophy that places the user in control of agent behavior. Every action Magentic-UI takes -- whether navigating the web, manipulating data, or executing code -- is preceded by a transparent planning phase where the proposed steps are surfaced for review. Plans are only executed with explicit user approval, and users retain the ability to pause, modify, or interrupt the agent at any time. When Magentic-UI encounters a scenario it deems high-impact or non-reversible, such as navigating to a new domain or initiating a potentially risky action, it proactively requests confirmation before proceeding. The user can also configure Magentic-UI to always ask for permission before performing any action. This approach reinforces user autonomy while minimizing unintended or unsafe behavior.

One of the key safety features in Magentic-UI is the ability to set a set of allowed websites. The allowed websites represent the set of websites that Magentic-UI can visit without explicit user approval. If Magentic-UI needs to visit a website outside the allowed list, it will ask the user for explicit approval by mentioning the exact URL, the page title and the reason for visiting the website.

To address safety and security concerns, Magentic-UI underwent targeted red-teaming to assess its behavior under adversarial and failure scenarios.  Such scenarios include cross-site prompt injection attacks where web pages contain malicious instructions distinct from the user s original intents (e.g., to execute risky code, access sensitive files, or perform actions on other websites). It also contains scenarios comparable to phishing, which try to trick Magentic-UI into entering sensitive information, or granting permissions on impostor sites (e.g., a synthetic website that asks Magentic-UI to log in and enter Google credentials to read an article). In our preliminary evaluations, we found that Magentic-UI either refuses to complete the requests, stops to ask the user, or, as a final safety measure, is eventually unable to complete the request due to Docker sandboxing. We have found that this layered approach is effective for thwarting these attacks.

Magentic-UI was architected with strong isolation boundaries: every component is sandboxed in separate Docker containers, allowing fine-grained access control to only necessary resources.  This effectively shields the host environment from agent activities. Sensitive data such as chat history, user settings, and execution logs are stored locally to preserve user privacy and minimize exposure.

Together, these mitigations are intended to reduce misuse risks, promote transparency, and preserve user control at every step. Magentic-UI is not a system that operates behind the scenes; it is a collaborator designed to act *with* the user, not *for* them.

## LICENSE

```
Magentic-UI is published under MIT License.
Copyright (c) Microsoft Corporation.

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
of the Software, and to permit persons to whom the Software is furnished to do
so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE
```

## CONTACT

We welcome feedback and collaboration from our audience. If you have suggestions, questions, or observe unexpected/offensive behavior in our technology, please contact us at [magui@service.microsoft.com]

If the team receives reports of undesired behavior or identifies issues independently, we will update this repository with appropriate mitigations.
