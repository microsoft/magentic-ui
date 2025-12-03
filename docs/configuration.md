# Configuration

For most users, the **Settings** panel inside the app is all you need. It walks you through model endpoints during the first-launch onboarding flow, and lets you change everything later from **Settings → Models** (and the other Settings tabs).

If you'd rather use a YAML file — for example to share a setup across machines or check it into source control — the same options are also exposed via `config.yaml`. The repo ships a [`config.yaml.example`](../config.yaml.example) at the project root that you can copy as a starting point:

```bash
cp config.yaml.example config.yaml
# then edit config.yaml to taste, and pass it on launch:
magentic-ui --port 8081 --config config.yaml
```

Each option below shows both the YAML key and (where applicable) the equivalent place in the UI.

## How configuration is stored

MagenticLite keeps your effective configuration in a local database, not in the YAML file. There are three ways that database can be populated, and the rule is simple — **whichever source wrote last wins, and the result persists across restarts**:

- **Onboarding UI** — runs once on first launch and writes your answers to the database.
- **Settings UI** — change anything at any time; the new values overwrite the database immediately.
- **YAML file via `--config`** — at startup, MagenticLite reads `config.yaml` and **merges** it into the database (only fields you explicitly set are overwritten; the rest are left alone). This means starting with `--config` every time effectively pins those YAML fields back to your file values on every launch, regardless of what the UI changed in between.

A handful of **Settings → General** options — the display preferences like theme, "show reasoning details", "show tool call details" — are saved to your browser's local storage instead of the backend database. They're per-browser, not per-installation, and they don't show up in `config.yaml`. Other items in the same panel (e.g. agent step limits) do write to the database like the rest of Settings.

```bash
magentic-ui --port 8081 --config config.yaml
```

To start fresh — clear the saved model endpoints and re-run the onboarding flow — pass `--reset-config`:

```bash
magentic-ui --port 8081 --reset-config
```

This only clears the model endpoints (orchestrator and browser-use); other configuration (sandbox, agent mode, tool approval) is preserved.

You can combine the two: `--reset-config` first clears the model endpoints, then `--config` (if also passed) seeds them from your YAML file.

## Model clients

`model_client_configs` tells MagenticLite which model serves which agent role. There are two roles:

- `orchestrator` — used in the `all` and `omniagent_only` agent modes.
- `web_surfer` — used in the `all` and `websurfer_only` agent modes.

Each entry is an OpenAI-compatible client config — any server that speaks `/v1/chat/completions` (vLLM, an OpenAI-compatible managed endpoint, your own gateway, …) will work. The full set of fields:

```yaml
model_client_configs:
  orchestrator:
    provider: OpenAIChatCompletionClient
    config:
      model: <model id the server expects>
      base_url: <https://your-endpoint/v1>
      api_key: <bearer token; leave as a placeholder if your server requires none>
      max_retries: 5
      model_info:
        vision: false
        function_calling: false
        json_output: true
        family: unknown
        structured_output: false
        multiple_system_messages: false

  web_surfer:
    provider: OpenAIChatCompletionClient
    config:
      model: <model id the server expects>
      base_url: <https://your-endpoint/v1>
      api_key: <bearer token>
      max_retries: 5
      model_info:
        vision: true # browser-use models are vision-language
        function_calling: false
        json_output: true
        family: unknown
        structured_output: false
        multiple_system_messages: false
```

Notes:

- `model_info` describes the capabilities of the model behind the endpoint. The values shown above are the ones MagenticLite has been tested with for the orchestrator (text-only) and browser-use (vision) roles; use them as-is unless you have a reason to differ for your specific model.
- **MagenticLite is tuned for the recommended models ([MagenticBrain](https://aka.ms/MagenticBrain-foundry) for the orchestrator, [Fara](https://aka.ms/fara-foundry) for browser use).** Pointing the same fields at a different model will probably work, but expect to tweak prompts and run your own evals; the orchestrator and browser-use code paths are not generic across arbitrary models.
- **Azure OpenAI** is supported via `config.yaml` only (the in-app Settings UI doesn't expose it yet): set `provider: AzureOpenAIChatCompletionClient` and use Azure-specific keys (`azure_endpoint`, `azure_deployment`, `api_version`, `azure_ad_token_provider`) under `config`. See [`config.yaml.example`](../config.yaml.example) for a worked example.
- If you don't have an endpoint to point at yet, see the [Model Hosting Guide](./model-hosting-guide.md) for one end-to-end way to stand one up.

## Agent mode

`agent_mode` controls which agents are active. It can also be changed in **Settings → Models** without restarting. The three modes let you trade capability for setup cost — you can run with both agents, or with only one of them if that's all your task needs.

| Mode             | Description                                                                                 |
| ---------------- | ------------------------------------------------------------------------------------------- |
| `all`            | Orchestrator + Browser use — capable of both local tasks and web browsing (default)         |
| `omniagent_only` | Orchestrator only — local tasks only; only `model_client_configs.orchestrator` required     |
| `websurfer_only` | Browser use only — web browsing tasks only; only `model_client_configs.web_surfer` required |

Which mode to pick:

- **`all`** is the default and gives you the full product. You need both an orchestrator endpoint and a browser-use endpoint.
- **`omniagent_only`** is useful if you only want local file / code-execution work and don't have a browser-use endpoint to point at. The agent can't use web browser.
- **`websurfer_only`** is useful if you only want web automation and don't have an orchestrator endpoint to point at. The agent can't read or write local files.

```yaml
agent_mode: all
```

## Sandbox

`sandbox.type` controls how agent code runs:

| Type        | Description                                                   |
| ----------- | ------------------------------------------------------------- |
| `quicksand` | Lightweight QEMU VM with browser isolation (recommended)      |
| `null`      | No isolation — agent runs on host directly (dev/testing only) |

```yaml
sandbox:
  type: quicksand
```

See [Quicksand browser architecture](./dev/quicksand-browser-architecture.md) for the technical details and environment variables.

## Tool approval

MagenticLite's safety harness prompts the user before executing potentially dangerous tool calls. Three policies are available:

| Policy                       | Behavior                                                                    |
| ---------------------------- | --------------------------------------------------------------------------- |
| `auto_approve`               | Execute all tool calls without prompting (eval / trusted setups only)       |
| `require_approval_untrusted` | Prompt before tool calls deemed untrusted; auto-approve read-only (default) |
| `require_approval_all`       | Prompt before every tool call                                               |

Set the policy in YAML:

```yaml
harness_config:
  orchestrator:
    approval_policy: require_approval_untrusted
```

## Next steps

- [Model Hosting Guide](./model-hosting-guide.md) — stand up a model endpoint to point `model_client_configs` at.
- [Troubleshooting](./troubleshooting.md) — what to do when something doesn't work.
