# Build from Source

This guide is for anyone who wants to run MagenticLite from a clone of this
repo — for example to make local changes to the backend or frontend, to test
an unreleased commit, or to dig into the code.

If you only want to run MagenticLite, the released `magentic_ui` package on
PyPI is what you want — see [Installation](./installation.md) instead.

## Prerequisites

Platform-level prerequisites (Homebrew / WSL2 / KVM / `uv` / Python 3.12) are
the same as a regular install — follow the [Installation guide](./installation.md#supported-platforms)
through the **macOS** or **Windows (WSL)** prerequisites section, then come
back here.

In addition, building the frontend requires:

- **Node.js v24 or later**
- **pnpm v10+**

```bash
# Install Node via nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
nvm install 24

# Install pnpm
npm install -g pnpm
```

## Clone the repo

```bash
git clone https://github.com/microsoft/magentic-ui.git
cd magentic-ui
```

## Backend setup

```bash
uv venv --python=3.12 --seed .venv
source .venv/bin/activate
uv sync --all-extras
```

`uv sync` installs MagenticLite in editable mode along with all dev
dependencies. The Quicksand VM image is downloaded automatically the first time
you launch `magentic-ui`; you don't need to run a separate install step for it.

## Frontend setup

The frontend is a Vite + React app under `frontend/`. Production builds are
written into `src/magentic_ui/backend/web/ui/`, where the backend serves them as
static files.

```bash
cd frontend
pnpm install
```

You then have two ways to run the UI, depending on what you're working on.

### Option 1: Production-style run

Build the frontend once into the backend's static directory, then launch the
backend and let it serve the bundle. Use this when you're working only on
backend code.

```bash
# from frontend/
pnpm build      # outputs to ../src/magentic_ui/backend/web/ui/
cd ..

magentic-ui --port 8081
```

Open <http://127.0.0.1:8081/>. Re-run `pnpm build` whenever the frontend
changes.

### Option 2: Frontend dev mode

Run the Vite dev server with hot reload, and run the backend separately. Use
this when you're iterating on the UI.

```bash
# Terminal 1 — backend
source .venv/bin/activate
magentic-ui --port 8081

# Terminal 2 — frontend dev server
cd frontend
pnpm dev        # serves at http://localhost:5173
```

Open <http://localhost:5173/>. The Vite dev server proxies API and WebSocket
calls to the backend on port 8081.

For UI component conventions, see
[`frontend/src/components/ui/README.md`](../frontend/src/components/ui/README.md).
