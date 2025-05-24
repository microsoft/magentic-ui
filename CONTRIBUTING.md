# Contributing to Magentic-UI

Thank you for your interest in contributing to Magentic-UI! This document provides guidelines and instructions for contributing to this project.

## Table of Contents

- [How to Contribute](#how-to-contribute)
- [Prerequisites](#prerequisites)
- [Development Setup](#development-setup)
  - [Windows-specific Pre Setup (WSL)](#windows-specific-pre-setup-wsl)
  - [General Setup](#general-setup)
- [Development Workflow](#development-workflow)
  - [Backend Development](#backend-development)
  - [Frontend Development](#frontend-development)
- [Testing](#testing)
- [Pull Requests](#pull-requests)
- [Code of Conduct](#code-of-conduct)
- [Recognition](#recognition)
- [Getting Help](#getting-help)

## How to Contribute

You can help by looking at issues or helping review PRs. Any issue or PR is welcome, but we have also marked some as 'open for contribution' and 'open for reviewing' to help facilitate community contributions.

<div align="center">

|            | All                                                           | Especially Needs Help from Community                                                                                                       |
| ---------- | ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| **Issues** | [All Issues](https://github.com/microsoft/magentic-ui/issues) | [Issues open for contribution](https://github.com/microsoft/magentic-ui/issues?q=is%3Aissue+is%3Aopen+label%3A%22open+for+contribution%22) |
| **PRs**    | [All PRs](https://github.com/microsoft/magentic-ui/pulls)     | [PRs open for reviewing](https://github.com/microsoft/magentic-ui/pulls?q=is%3Apr+is%3Aopen+label%3A%22open+for+reviewing%22)              |

</div>

## Prerequisites

Before you begin, ensure you have the following installed:

- Git
- Docker (Docker Desktop for Windows/Mac)
- Python 3.10+
- Node.js and Yarn (for frontend development)
- WSL2 if you're on Windows

## Development Setup

### Windows-specific Pre Setup (WSL)

If you're on Windows, you'll need to use WSL2:

1. Install and connect to a WSL2 distro (Ubuntu is recommended)
   - **Important**: Don't use the Docker Desktop WSL distro for development
   - Follow [Microsoft's WSL installation guide](https://learn.microsoft.com/en-us/windows/wsl/install)

2. Configure Docker Desktop to use WSL2
   - Go to Settings > Resources > WSL Integration
   - Enable integration with your development distro

3. Work inside the Linux environment
   - As per [Microsoft's recommendations](https://learn.microsoft.com/en-us/windows/wsl/filesystems):
     > "We recommend against working across operating systems with your files, unless you have a specific reason for doing so"

### General Setup

1. Fork this repository on GitHub

2. Clone your fork:
   ```bash
   # Create a repos directory inside WSL if you don't have one
   mkdir -p ~/repos
   cd ~/repos
   
   # Clone the repository
   git clone https://github.com/YOUR-USERNAME/magentic-ui.git
   cd magentic-ui
   ```

3. Install dependencies with uv (recommended):
   ```bash
   # Install uv if you don't have it
   # See https://docs.astral.sh/uv/getting-started/installation/
   
   # Create a virtual environment
   uv venv --python=3.12 .venv
   
   # Install dependencies
   uv sync --all-extras
   
   # Activate the virtual environment
   source .venv/bin/activate
   ```

4. Set up your API keys:
   ```bash
   export OPENAI_API_KEY=YOUR-API-KEY
   ```

## Development Workflow

First, make sure you have Node.js installed:

```bash
# Install nvm to manage Node.js
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash

# Restart your terminal, then install Node.js
nvm install node
```

Reactivate your .venv for subsequent sections

### Backend Development

**Important**: Before running the backend for the first time, we recommend you must build a static frontend:

```bash
# From the frontend directory
cd frontend
npm install -g gatsby-cli
npm install --global yarn
yarn install
yarn build
cd ..  # Return to project root
```

Then you can run the backend:

```bash
# From the project root directory
magentic ui --port 8081
```

**Note**: The first time you run this command, it will build two Docker containers which can take some time. If you encounter issues, you can build the Docker images manually:

```bash
docker build -t magentic-ui-vnc-browser:latest ./src/magentic_ui/docker/magentic-ui-browser-docker
docker build -t magentic-ui-python-env:latest ./src/magentic_ui/docker/magentic-ui-python-env
```

After both the frontend is built and the backend is running, the complete application will be available at http://localhost:8081.
 > If you get errors, ensure you have exported your API key

### Frontend Development

If you're only working on the frontend code, use the development server for live reloading:

1. First, install the required packages:
   ```bash
   cd frontend
   npm install -g gatsby-cli
   npm install --global yarn
   yarn install
   ```

2. Create a development environment file:
   ```bash
   cp .env.default .env.development
   ```

3. Launch the frontend dev server:
   ```bash
   npm run start
   ```

4. In another terminal, run the backend:
   ```bash
   # Remember to activate your .venv and export your keys again
   source .venv/bin/activate
   export OPENAI_API_KEY=YOUR-API-KEY
   magentic ui --port 8081
   ```

With this setup:
- The frontend development server will be available at http://localhost:8000
- Changes to frontend code will be reflected immediately without manual rebuilding
- The backend will still be available at http://localhost:8081
- You should use http://localhost:8000 for frontend development

**Note**: You don't need to run `yarn build` during development. That command is only needed when preparing for production or package distribution.

## Testing

All PRs contributing new features are expected to include new tests. You can find existing tests in the `tests` directory.

To run the continuous integration checks locally:

```bash
poe check
```

## Pull Requests

1. Create a branch for your changes
2. Make your changes
3. Run tests to ensure they pass
4. Submit a pull request

Most contributions require you to agree to a Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us the rights to use your contribution. A CLA bot will automatically determine whether you need to provide a CLA and guide you through the process.

## Code of Conduct

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/). For more information, see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## Recognition

We appreciate all contributors to this project. Your contributions help improve Magentic-UI for everyone!

## Getting Help

If you need help with anything related to contributing, please open an issue on GitHub or refer to the documentation.