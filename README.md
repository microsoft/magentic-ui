<div align="center">
<div align="center" style="display: flex; align-items: center; justify-content: center; gap: 16px;">
  <img src="frontend/src/assets/logo.svg" alt="Magentic-UI Logo" height="60" style="vertical-align: middle;"/>
  <span style="font-size: 2.8em; font-weight: bold; color: #444; vertical-align: middle;">Magentic-UI</span>
</div>

_Automate your web tasks while you stay in control_

[![GitHub stars](https://img.shields.io/github/stars/microsoft/magentic-ui?style=social)](https://github.com/microsoft/magentic-ui/stargazers)
[![image](https://img.shields.io/pypi/v/magentic_ui.svg)](https://pypi.python.org/pypi/magentic_ui)
[![image](https://img.shields.io/pypi/l/magentic_ui.svg)](https://pypi.python.org/pypi/magentic_ui)
![Python Versions](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)

</div>

## 🚀 Quick Navigation

<p align="center">
  <a href="#🟪-about-magentic-ui">🟪 About</a> &nbsp;|&nbsp;
  <a href="#✨-features">✨ Features</a> &nbsp;|&nbsp;
  <a href="#🛠️-installation">🛠️ Installation</a> &nbsp;|&nbsp;
  <a href="#⚠️-troubleshooting">⚠️ Troubleshooting</a> &nbsp;|&nbsp; 
  <a href="#🤝-contributing">🤝 Contributing</a> &nbsp;|&nbsp;
  <a href="#📄-license">📄 License</a>
</p>

---

<div align="center">
  <a href="https://www.youtube.com/watch?v=wOs-5SR8xOc" target="_blank">
    <img src="https://img.youtube.com/vi/wOs-5SR8xOc/maxresdefault.jpg" alt="Watch the demo video" width="600"/>
  </a>
  <br>
  ▶️ <em> Click to watch a video and learn more about Magentic-UI </em>
</div>


## 🟪 About Magentic-UI

Magentic-UI is a **research prototype** of a human-centered interface powered by a multi-agent system that can browse and perform actions on the web, generate and execute code, and generate and analyze files.

Magentic-UI is especially useful for web tasks that require actions on the web (e.g., filling a form, customizing a food order), deep navigation through websites not indexed by search engines (e.g., filtering flights, finding a link from a personal site) or tasks that need web navigation and code execution (e.g., generate a chart from online data).


<p align="center">
  <img src="./docs/magenticui_running.png" alt="Magentic-UI" height="400">
</p>


The interface of Magentic-UI is displayed in the screenshot above and consists of two panels. The left side panel is the sessions navigator where users can create new sessions to solve new tasks, switch between sessions and check on session progress with the session status indicators (🔴 needs input, ✅ task done, ↺ task in progress).

The right-side panel displays the session selected. This is where you can type your query to Magentic-UI alongside text and image attachments and observe detailed task progress as well as  interact with the agents. The session display itself is split in two panels: the left side is where Magentic-UI presents the plan, task progress and asks for action approvals, the right side is a browser view where you can see web agent actions in real time and interact with the browser. Finally, at the top of the session display is a progress bar that updates as Magentic-UI makes progress.

### ℹ️ Agentic Workflow

Magentic-UI's underlying system is a team of specialized agents adapted from AutoGen's Magentic-One system illustrated in the figure below.

<p align="center">
  <img src="./docs/magenticui.jpg" alt="Magentic-UI" height="400">
</p>

 The agents work together to create a modular system:

- 🧑‍💼 **Orchestrator** is the lead agent, powered by a large language model (LLM), that performs co-planning with the user, decides when to ask the user for feedback, and delegates sub-tasks to the remaining agents to complete.  
- 🌐 **WebSurfer** is an LLM agent equipped with a web browser that it can control. Given a request by the Orchestrator, it can click, type, scroll, and visit pages in multiple rounds to complete the request from the Orchestrator. This agent is a significant improvement over the AutoGen ``MultimodalWebSurfer``  in terms of the actions it can do (tab management, select options, file upload, multimodal queries).
- 💻 **Coder** is an LLM agent equipped with a Docker code-execution container. It can write and execute Python and shell commands and provide a response back to the Orchestrator.
- 📁 **FileSurfer** is an LLM agent equipped with a Docker code-execution container and file-conversion tools from the MarkItDown package. It can locate files in the directory controlled by Magentic-UI, convert files to markdown, and answer questions about them.
- 🧑 **UserProxy** is an agent that represents the user interacting with Magentic-UI. The Orchestrator can delegate work to the user instead of the other agents.

To interact with Magentic-UI, **users can enter a text message and attach images**. In response, Magentic-UI creates a natural-language step-by-step plan with which users can interact through a plan-editing interface. **Users can add, delete, edit, regenerate steps, and write follow-up messages to iterate on the plan.** While the user editing the plan adds an upfront cost to the interaction, it can potentially save a significant amount of time in the agent executing the plan and increase its chance at success.

The plan is stored inside the Orchestrator and is used to execute the task. **For each step of the plan, the Orchestrator determines which of the agents (WebSurfer, Coder, FileSurfer) or the user should complete the step.** Once that decision is made, the Orchestrator sends a request to one of the agents or the user and waits for a response. After the response is received, the Orchestrator decides whether that step is complete. If the step is complete, the Orchestrator moves on to the following step.

**Once all steps are completed, the Orchestrator generates a final answer that is presented to the user.** If, while executing any of the steps, the Orchestrator decides that the plan is inadequate (for example, because a certain website is unreachable), the Orchestrator can replan with user permission and execute a new plan.

All intermediate progress steps are clearly displayed to the user. Furthermore, the user can pause the execution of the plan and send additional requests or feedback. The user can also configure through the interface whether agent actions (e.g., clicking a button) require approval.

## ✨ Features

What differentiates Magentic-UI from other browser use offerings is its transparent and controllable interface that allows for **efficient human-in-the-loop involvement.** Magentic-UI is built using [AutoGen](https://github.com/microsoft/autogen) and provides a platform to study human-agent interaction and experiment with web agents. Key features include:

- 🧑‍🤝‍🧑 **Co-Planning**: Collaboratively create and approve step-by-step plans using chat and the plan editor.
- 🤝 **Co-Tasking**: Interrupt and guide the task execution using the web browser directly or through chat. Magentic-UI can also ask for clarifications and help when needed.
- 🛡️ **Action Guards**: Sensitive actions are only executed with explicit user approvals.
- 🧠 **Plan Learning and Retrieval**: Learn from previous runs to improve future task automation and save them in a plan gallery. Automatically or manually retrieve saved plans in future tasks.
- 🔀 **Parallel Task Execution**: You can run multiple tasks in parallel and session status indicators will let you know when Magentic-UI needs your input or has completed the task.

The example below shows a step by step user interaction with Magentic-UI:

<!-- Screenshots -->
<p align="center">
  <img src="docs/magui-landing.png" alt="Magentic-UI Landing" width="45%" style="margin:10px;">
  <img src="docs/magui-coplanning.png" alt="Co-Planning UI" width="45%" style="margin:10px;">
  <img src="docs/magui-cotasking.png" alt="Co-Tasking UI" width="45%" style="margin:10px;">
  <img src="docs/magui-actionguard.png" alt="Action Guard UI" width="45%" style="margin:10px;">
</p>

## 🛠️ Installation

Magentic-UI has a couple moving components, so it is important to follow along carefully. 


### 📝 Pre-Requisites

1. If running on **Windows** or **Mac** you must use [Docker Desktop](https://www.docker.com/products/docker-desktop/). If running on **Linux**, you should use [Docker Engine](https://docs.docker.com/engine/install/). **Magentic-UI was not tested with other container providers.**

    2. If using Docker Desktop, make sure it is set up to use WSL2:
        - Go to Settings > Resources > WSL Integration
        - Enable integration with your development distro You can find more detailed instructions about this step [here](https://docs.microsoft.com/en-us/windows/wsl/tutorials/wsl-containers).



2. During the Installation step, you will need to set up your `OPENAI_API_KEY`. Make sure you create an API key on [here](https://platform.openai.com/api-keys). To use other models, review the [Custom Client Configuration](#🧩-using-custom-clients) section below.

3. You need at least [Python 3.10](https://www.python.org/downloads/) installed, [Git](https://git-scm.com/downloads) to clone the project and [uv](https://docs.astral.sh/uv/getting-started/installation/) for managing dependencies. 


---
#### 🪟 For **Windows** Users

If you are on Windows, you **must** run Magentic-UI inside [WSL2](https://docs.microsoft.com/en-us/windows/wsl/install) (Windows Subsystem for Linux) for correct Docker and file path compatibility. The steps below assume you are using VS Code. 

How to work on Linux if you are a Windows user:
1. Open VS Code.
2. Click the green button on the bottom left corner (with the `><` icon).
3. Click "Connect to WSL using Distro".
4. Select Ubuntu (or your preferred WSL2 distribution).
5. Open a new terminal in VS Code (it should say `bash` or your distro name, **not** `cmd` or `powershell`).
6. Run the application from this WSL2 terminal, **not** from a Windows terminal.
7. Ensure Docker is set up to use the WSL2 backend (see more info in the `README.md`).

This ensures file paths are Linux-style and compatible with Docker, preventing errors when running Magentic-UI. Once that is done, proceed to [Quick Installation](#⚡-quick-installation) below.

---

### ⚡ Quick Installation 

This is the installation that **most users** will prefer. It is straightforward and allows you use Magentic-UI immediately. If you would like to build from source instead, please see the [Building From Source](#🏗️-building-from-source) section.


> **Please Read**: Before installing, please read the [pre-requisites](#📝-pre-requisites) carefully.  
> **Windows Users**: Please read the [For Windows Users](#🪟-for-windows-users) section above.  

---
**One-liner Installation for advanced users:**  

If you already have [uvx](https://docs.astral.sh/uvx/) installed, you can launch Magentic-UI instantly with:

```bash
uvx --from magentic-ui magentic ui --port 8081
```
Or, for Ollama support:
```bash
uvx --from magentic-ui[ollama] magentic ui --port 8081
```
---

**Regular Installation for general users (recommended):**  

Alternatively, you can follow the steps below for a regular (and still very fast) installation:

#### 1. Clone the repository: 

```bash
git clone https://github.com/microsoft/magentic-ui.git
cd magentic-ui
```

#### 2. Set your OpenAI key:

Alternatively, skip this step and see the [Using Custom Clients](#🧩-using-custom-clients) section.

```bash
export OPENAI_API_KEY=<YOUR API KEY>
```

#### 3. Use [`uv`](https://docs.astral.sh/uv/getting-started/installation/) for managing dependencies:

```bash
uv venv --python=3.12 .venv
source .venv/bin/activate
```

#### 4. Magentic-UI is available on PyPI:

```bash
uv pip install magentic-ui
```

#### 5. Start Magentic-UI (make sure Docker is running)

```bash
magentic ui --port 8081
```

The first time that you run this command, it will take a while to build the Docker images, so go grab a coffee in the meantime. The next time you run it, it will be much faster as it doesn't have to build the Docker again.

You should now be able to access Magentic-UI at <http://localhost:8081>.

**Note**: If you encounter problems, you can build the containers directly with the following commands from inside the repository: 

```bash
docker build -t magentic-ui-vnc-browser:latest ./src/magentic_ui/docker/magentic-ui-browser-docker
docker build -t magentic-ui-python-env:latest ./src/magentic_ui/docker/magentic-ui-python-env
```

If this still **does not work**, try restarting Docker. Alternatively, see our [Troubleshooting](#⚠️-troubleshooting) section for common errors.

---



### 🏗️ Building From Source

This step is primarily for users seeking to make modifications to the code or users that are having issues installing Magentic-UI with the commands above. If you have already installed Magentic-UI with the previous steps and is satisfied, you can ignore this section.

#### 1. Ensure the [pre-requisites](#📝-pre-requisites) are installed, and that Docker is running.

#### 2. Clone the repository to your local machine:

```bash
git clone https://github.com/microsoft/magentic-ui.git
cd magentic-ui
```

#### 3. Install Magentic-UI's dependencies with uv:

```bash
uv venv --python=3.12 .venv
uv sync --all-extras
source .venv/bin/activate
```

#### 4. Build the frontend:

First make sure to have install `node`:

```bash
# install nvm to install node
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
nvm install node
```

Then install the frontend:

```bash
cd frontend
npm install -g gatsby-cli
npm install --global yarn
yarn install
yarn build
```

#### 5. Run Magentic-UI, as usual.

```bash
magentic ui --port 8081
```

### 🧩 Using Custom Clients

To use Azure models or Ollama please install with the optional dependencies:
```bash
# for Azure
pip install magentic-ui[azure] 
# for Ollama
pip install magentic-ui[ollama]
```

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



## ⚠️ Troubleshooting

If you were unable to get Magentic-UI running, do not worry! The first step is to make sure you have followed the steps outlined above, particularly with the [pre-requisites](#📝-pre-requisites) and the [For Windows Users](#🪟-for-windows-users) (if you are on Windows) sections.

For common issues and their solutions, please refer to the [TROUBLESHOOTING.md](TROUBLESHOOTING.md) file in this repository. If you do not see your problem there, please open a `GitHub Issue`. 

**When opening a GitHub Issue, please include**:
  1. A detailed description of your problem
  2. Information about your system (OS, Docker version, etc.)
  3. Steps to replicate the issue (if possible)

## 🤝 Contributing

This project welcomes contributions and suggestions. For information about contributing to Magentic-UI, please see our [CONTRIBUTING.md](CONTRIBUTING.md) guide, which includes current issues to be resolved and other forms of contributing.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/). For more information, see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## 📄 License

Microsoft, and any contributors, grant you a license to any code in the repository under the [MIT License](https://opensource.org/licenses/MIT). See the [LICENSE](LICENSE) file.

Microsoft, Windows, Microsoft Azure, and/or other Microsoft products and services referenced in the documentation
may be either trademarks or registered trademarks of Microsoft in the United States and/or other countries.
The licenses for this project do not grant you rights to use any Microsoft names, logos, or trademarks.
Microsoft's general trademark guidelines can be found at <http://go.microsoft.com/fwlink/?LinkID=254653>.

Any use of third-party trademarks or logos are subject to those third-party's policies.

Privacy information can be found at <https://go.microsoft.com/fwlink/?LinkId=521839>

Microsoft and any contributors reserve all other rights, whether under their respective copyrights, patents, or trademarks, whether by implication, estoppel, or otherwise.