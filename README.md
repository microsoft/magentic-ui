<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/_assets/magentic-lite-logo-dark.png">
    <img src="docs/_assets/magentic-lite-logo-light.png" alt="MagenticLite" width="420">
  </picture>
</p>

<p align="center">
  <em>Big tasks. Small models.</em>
</p>

---

**MagenticLite** is the next generation of Magentic-UI — an agentic application from **Microsoft AI Frontiers**, redesigned to do more with less. It pairs an on-device-friendly orchestrator model ([MagenticBrain](https://aka.ms/MagenticBrain-foundry)) with a specialized browser-use model ([Fara](https://aka.ms/fara-foundry)) so you can automate real work without depending on frontier-scale compute.

- **Built for small models, efficient by design.** Strong agentic performance without heavy compute — no frontier-scale models required.
- **Works across the browser and your local file system.** Web research, form filling, file management — in one workflow.
- **Keeps you in the loop and in control.** Steer, approve, or take over at any point. MagenticLite stops and checks in before taking critical actions.
- **Safe by design.** Browser sessions run inside a lightweight VM sandbox ([Quicksand](https://microsoft.github.io/quicksand/)) so the agent can't reach the rest of your machine without your say-so.

## See it in action

Click any task below to expand and watch MagenticLite handle it end to end.

<details open>
  <summary><b>Fill expense forms</b></summary>

  https://github.com/user-attachments/assets/a982b60d-127e-4310-96e6-9f094dffb7f0

</details>

<details>
  <summary><b>Find prices for recipe ingredients</b></summary>

  https://github.com/user-attachments/assets/7ff87917-752f-4e40-b319-8036e08ab8f9

</details>

<details>
  <summary><b>Find and book a restaurant</b></summary>

  https://github.com/user-attachments/assets/ee5f967e-ee1b-4554-b329-36b56b595aa4

</details>

<details>
  <summary><b>Organize local files</b></summary>

  https://github.com/user-attachments/assets/aff385dd-f856-4db4-8f26-08fd0f940aa4

</details>

## Quick start

These steps get you running on macOS or Windows (WSL). Need more detail or a different platform? See the [Installation Guide](./docs/installation.md).

### 1. Install MagenticLite

```bash
# Create a project directory
mkdir magentic-lite && cd magentic-lite

# Create and activate a virtual environment
uv venv --python=3.12 --seed .venv
source .venv/bin/activate

# Install the latest 0.2.x release from PyPI
uv pip install "magentic_ui>=0.2.0"
```

### 2. Run

```bash
magentic-ui --port 8081
```

Open <http://127.0.0.1:8081/> and follow the in-app onboarding to connect a model endpoint. If you don't have one yet, see the [Model Hosting Guide](./docs/model-hosting-guide.md).

> **Looking for the previous Magentic-UI 0.1 release** (optimized to run with frontier models)? It lives on the [`magentic-ui-0.1`](https://github.com/microsoft/magentic-ui/tree/magentic-ui-0.1) branch.

## Documentation

| Doc                                                  | What's in it                                                                             |
| ---------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| [Installation](./docs/installation.md)               | Supported platforms, macOS / WSL prerequisites, install + run commands                   |
| [Build from source](./docs/build-from-source.md)     | How to run MagenticLite from a clone of this repo (`uv sync`, `pnpm dev`, etc.)          |
| [Model hosting guide](./docs/model-hosting-guide.md) | End-to-end walkthrough of standing up a model endpoint and connecting MagenticLite to it |
| [Configuration](./docs/configuration.md)             | Sandbox, agent mode, tool approval, full `config.yaml` example                           |
| [Troubleshooting](./docs/troubleshooting.md)         | Common errors and how to fix them                                                        |
| [Limitations](./docs/limitations.md)                 | Tasks and usage patterns MagenticLite doesn't handle well today                          |
| [Transparency Note](./docs/TRANSPARENCY_NOTE.md)     | Intended uses, responsible-use guidance, risks, and mitigations                          |

## License

Microsoft, and any contributors, grant you a license to any code in the repository under the [MIT License](https://opensource.org/licenses/MIT). See the [LICENSE](LICENSE) file.

Microsoft, Windows, Microsoft Azure, and/or other Microsoft products and services referenced in the documentation may be either trademarks or registered trademarks of Microsoft in the United States and/or other countries. The licenses for this project do not grant you rights to use any Microsoft names, logos, or trademarks. Microsoft's general trademark guidelines can be found at <http://go.microsoft.com/fwlink/?LinkID=254653>.

Any use of third-party trademarks or logos are subject to those third-party's policies.

Privacy information can be found at <https://go.microsoft.com/fwlink/?LinkId=521839>.

Microsoft and any contributors reserve all other rights, whether under their respective copyrights, patents, or trademarks, whether by implication, estoppel, or otherwise.
