<div align="center">

<img src="frontend/src/assets/logo.svg" alt="Magentic-UI Logo" height="100">

# Magentic-UI

_Automate your web tasks while you stay in control_

[![image](https://img.shields.io/pypi/v/magentic_ui.svg)](https://pypi.python.org/pypi/uv)
[![image](https://img.shields.io/pypi/l/magentic_ui.svg)](https://pypi.python.org/pypi/magentic_ui)
![Python Versions](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)

</div>

<!-- <img src="./docs/landing.gif" loop=infinite> -->

<!-- Screenshots -->
<p align="center">
  <img src="docs/magui-landing.png" alt="Magentic-UI Landing" width="45%" style="margin:10px;">
  <img src="docs/magui-coplanning.png" alt="Co-Planning UI" width="45%" style="margin:10px;">
  <img src="docs/magui-cotasking.png" alt="Co-Tasking UI" width="45%" style="margin:10px;">
  <img src="docs/magui-actionguard.png" alt="Action Guard UI" width="45%" style="margin:10px;">
</p>

Magentic-UI is a **research prototype** of a human-centered interface powered by a multi-agent system that can browse and perform actions on the web, generate and execute code, and generate and analyze files.
Magentic-UI is especially useful for web tasks that require actions on the web (e.g., filling a form, customizing a food order), deep navigation through websites not indexed by search engines (e.g., filtering flights, finding a link from a personal site) or tasks that need web navigation and code execution (e.g., generate a chart from online data).

What differentiates Magentic-UI from other browser use offerings is its transparent and controllable interface that allows for efficient human-in-the-loop involvement. Magentic-UI is built using [AutoGen](https://github.com/microsoft/autogen) and provides a platform to study human-agent interaction and experiment with web agents. Key features include:

- 🧑‍🤝‍🧑 **Co-Planning**: Collaboratively create and approve step-by-step plans using chat and the plan editor.
- 🤝 **Co-Tasking**: Interrupt and guide the task execution using the web browser directly or through chat. Magentic-UI can also ask for clarifications and help when needed.
- 🛡️ **Action Guards**: Sensitive actions are only executed with explicit user approvals.
- 🧠 **Plan Learning and Retrieval**: Learn from previous runs to improve future task automation and save them in a plan gallery. Automatically or manually retrieve saved plans in future tasks.
- 🔀 **Parallel Task Execution**: You can run multiple tasks in parallel and session status indicators will let you know when Magentic-UI needs your input or has completed the task.

Here's how you can get started with Magentic-UI. It's easy to install and run.

> **Note**: Before installing, please read the [prerequisites](#prerequisites) carefully. Magentic-UI requires Docker to run, and if you are on Windows, you will need WSL2. We recommend using [uv](https://docs.astral.sh/uv/getting-started/installation/) for a quicker installation. If you are using Mac or Linux, you can skip the WSL2 step.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install magentic-ui
# export OPENAI_API_KEY=<YOUR API KEY>
magentic ui --port 8081
```
If your port is 8081, you can then access Magentic-UI at <http://localhost:8081>.


To use Azure models or Ollama please install with the optional dependencies:
```bash
# for Azure
pip install 'magentic-ui[azure]' 
# for Ollama
pip install 'magentic-ui[ollama]'
```


## Table of Contents

- [About Magentic-UI](#about-magentic-ui)
- [How does it work?](#how-does-it-work)
- [How to use Magentic-UI](#how-to-use-magentic-ui)
- [Custom Client Configuration](#custom-client-configuration)
- [Contributing](#contributing)
- [Legal Notices](#legal-notices)

## About Magentic-UI
Magentic-UI is a web application that allows people to interact with a powerful multi-agent system that can browse and perform actions on the live web, generate and execute code, and generate and analyze files.


<p align="center">
  <img src="./docs/magenticui_running.png" alt="Magentic-UI" height="400">
</p>


The interface of Magentic-UI is displayed in the screenshot above and consists of two panels. The left side panel is the sessions navigator where users can create new sessions to solve new tasks, switch between sessions and check on session progress with the session status indicators (🔴 needs input, ✅ task done, ↺ task in progress).

The right-side panel displays the session selected. This is where you can type your query to Magentic-UI alongside text and image attachments and observe detailed task progress as well as  interact with the agents. The session display itself is split in two panels: the left side is where Magentic-UI presents the plan, task progress and asks for action approvals, the right side is a browser view where you can see web agent actions in real time and interact with the browser. Finally, at the top of the session display is a progress bar that updates as Magentic-UI makes progress.




### How does it work?

<p align="center">
  <img src="./docs/magenticui.jpg" alt="Magentic-UI" height="400">
</p>

Magentic-UI's underlying system is a team of specialized agents adapted from AutoGen's Magentic-One system illustrated in the figure above. The agents work together to create a modular system:

- **Orchestrator** is the lead agent, powered by a large language model (LLM), that performs co-planning with the user, decides when to ask the user for feedback, and delegates sub-tasks to the remaining agents to complete.
- **WebSurfer** is an LLM agent equipped with a web browser that it can control. Given a request by the Orchestrator, it can click, type, scroll, and visit pages in multiple rounds to complete the request from the Orchestrator. This agent is a significant improvement over the AutoGen ``MultimodalWebSurfer``  in terms of the actions it can do (tab management, select options, file upload, multimodal queries).
- **Coder** is an LLM agent equipped with a Docker code-execution container. It can write and execute Python and shell commands and provide a response back to the Orchestrator.
- **FileSurfer** is an LLM agent equipped with a Docker code-execution container and file-conversion tools from the MarkItDown package. It can locate files in the directory controlled by Magentic-UI, convert files to markdown, and answer questions about them.
- **UserProxy** is an agent that represents the user interacting with Magentic-UI. The Orchestrator can delegate work to the user instead of the other agents.

To interact with Magentic-UI, users can enter a text message and attach images. In response, Magentic-UI creates a natural-language step-by-step plan with which users can interact through a plan-editing interface. Users can add, delete, edit, regenerate steps, and write follow-up messages to iterate on the plan. While the user editing the plan adds an upfront cost to the interaction, it can potentially save a significant amount of time in the agent executing the plan and increase its chance at success.

The plan is stored inside the Orchestrator and is used to execute the task. For each step of the plan, the Orchestrator determines which of the agents (WebSurfer, Coder, FileSurfer) or the user should complete the step. Once that decision is made, the Orchestrator sends a request to one of the agents or the user and waits for a response. After the response is received, the Orchestrator decides whether that step is complete. If it is, the Orchestrator moves on to the following step.

Once all steps are completed, the Orchestrator generates a final answer that is presented to the user. If, while executing any of the steps, the Orchestrator decides that the plan is inadequate (for example, because a certain website is unreachable), the Orchestrator can replan with user permission and start executing a new plan.

All intermediate progress steps are clearly displayed to the user. Furthermore, the user can pause the execution of the plan and send additional requests or feedback. The user can also configure through the interface whether agent actions (e.g., clicking a button) require approval.

## How to Use Magentic-UI


### Prerequisites

1. Magentic-UI requires Docker as part of normal operation. If running on Windows or Mac, you can use [Docker Desktop](https://www.docker.com/products/docker-desktop/).

2. Running Magentic-UI on Windows requires WSL2. You can follow the instructions [here](https://docs.microsoft.com/en-us/windows/wsl/install) to install WSL2. Additionally, be sure that Docker Desktop is configured to use WSL2 (Settings > Resources > WSL Integration). You can find more detailed instructions about this step [here](https://docs.microsoft.com/en-us/windows/wsl/tutorials/wsl-containers).

3. Provide your OpenAI API key to Magentic-UI by setting the environmental variable `OPENAI_API_KEY`. Alternatively, review the [Custom Client Configuration](#custom-client-configuration) section below.

4. You need at least Python 3.10 installed.

### PyPI Installation

Magentic-UI is available on PyPI. We recommend using a virtual environment to avoid conflicts with other packages.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install magentic-ui
```

Alternatively, if you use [`uv`](https://docs.astral.sh/uv/getting-started/installation/) for dependency management, you can install Magentic-UI with:

```bash
uv venv --python=3.12 .venv
. .venv/bin/activate
uv pip install magentic-ui
```

### Running Magentic-UI

To run Magentic-UI, make sure that Docker is running, then run the following command:

```bash
magentic ui --port 8081
```

The first time that you run this command, it will take a while to build the Docker images -- go grab a coffee or something. The next time you run it, it will be much faster as it doesn't have to build the Docker again.

Once the server is running, you can access the UI at <http://localhost:8081>.

### Custom Client Configuration

If you want to use a different OpenAI key, or if you want to configure use with Azure OpenAI or Ollama, you can do so inside the UI by navigating to settings (top right icon) and changing model configuration with the format of the `config.yaml` file below. You can also create a `config.yaml` and import it inside the UI or point Magentic-UI to its path at startup time: 
```bash
magentic ui --config path/to/config.yaml
```

An example `config.yaml` for OpenAI is given below:

```yaml
# config.yaml

######################################
# Default OpenAI model configuration #
######################################
model_config: &client
  provider: autogen_ext.models.openai.OpenAIChatCompletionClient
  config:
    model: gpt-4o
    api_key: <YOUR API KEY>
    max_retries: 10

##########################
# Clients for each agent #
##########################
orchestrator_client: *client
coder_client: *client
web_surfer_client: *client
file_surfer_client: *client
action_guard_client: *client
```

The corresponding configuration for Azure OpenAI is:

```yaml
# config.yaml

######################################
# Azure model configuration          #
######################################
model_config: &client
  provider: AzureOpenAIChatCompletionClient
  config:
    model: gpt-4o
    azure_endpoint: "<YOUR ENDPOINT>"
    azure_deployment: "<YOUR DEPLOYMENT>"
    api_version: "2024-10-21"
    azure_ad_token_provider:
      provider: autogen_ext.auth.azure.AzureTokenProvider
      config:
        provider_kind: DefaultAzureCredential
        scopes:
          - https://cognitiveservices.azure.com/.default
    max_retries: 10

##########################
# Clients for each agent #
##########################
orchestrator_client: *client
coder_client: *client
web_surfer_client: *client
file_surfer_client: *client
action_guard_client: *client
```

## Contributing

This project welcomes contributions and suggestions. For information about contributing to Magentic-UI, please see our [CONTRIBUTING.md](CONTRIBUTING.md) guide, which includes detailed setup instructions and development workflows.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/). For more information, see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## Legal Notices

Microsoft, and any contributors, grant you a license to any code in the repository under the [MIT License](https://opensource.org/licenses/MIT). See the [LICENSE](LICENSE) file.

Microsoft, Windows, Microsoft Azure, and/or other Microsoft products and services referenced in the documentation
may be either trademarks or registered trademarks of Microsoft in the United States and/or other countries.
The licenses for this project do not grant you rights to use any Microsoft names, logos, or trademarks.
Microsoft's general trademark guidelines can be found at <http://go.microsoft.com/fwlink/?LinkID=254653>.

Any use of third-party trademarks or logos are subject to those third-party's policies.

Privacy information can be found at <https://go.microsoft.com/fwlink/?LinkId=521839>

Microsoft and any contributors reserve all other rights, whether under their respective copyrights, patents,
or trademarks, whether by implication, estoppel, or otherwise.
