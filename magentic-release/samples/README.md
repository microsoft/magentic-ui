# Magentic-UI Sample Scripts

This directory contains sample scripts to help explore Magentic-UI. Each script showcases a different agent or team configuration. See below for a brief explanation of each sample:

We will be adding more samples to help you get the most out of magentic-ui.

## 1. `sample_azure_agent.py`

**Description:**

- Demonstrates how to use an Azure AI Foundry agent within the Magentic-UI team.

**Usage:**

- Configure your Azure credentials and deployment names as needed.
- Run the script to see the Azure agent respond to a simple message or in the Magentic-UI team.

## 2. `sample_coder.py`

**Description:**

- Runs the coding agent (`CoderAgent`) in a round-robin manner with the user.

**Usage:**

- Run with `python sample_coder.py --work_dir <directory>` (default: `debug`).
- Enter your coding task at the prompt.

## 3. `sample_file_surfer.py`

**Description:**

- Runs the `FileSurfer` agent, which can browse and read files in a directory.

**Usage:**

- Run with `python sample_file_surfer.py --work-dir <directory>` (default: `debug`).
- Enter your file-related task at the prompt.

## 4. `sample_web_surfer.py`

**Description:**

- Runs the `WebSurfer` agent, which can interact with web pages using a Playwright browser (local or Dockerized).
- Supports both headless and VNC (noVNC) browser modes for web automation and browsing tasks.

**Usage:**

- Run with `python sample_web_surfer.py` for local browser.
- Use `--port` and `--novnc-port` for Docker/VNC modes (see script help for details).
- Enter your web task at the prompt.
