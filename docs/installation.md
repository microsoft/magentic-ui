# Installation

This guide walks you through installing MagenticLite. It covers macOS and Windows (WSL); Linux is similar to the Windows/WSL path.

## Supported platforms

| Platform           | Status                           | Notes                                                              |
| ------------------ | -------------------------------- | ------------------------------------------------------------------ |
| macOS ARM64        | ✅ tested                        | Apple Silicon.                                                     |
| Windows x64 + WSL2 | ✅ tested                        | Run everything inside the Ubuntu shell. Requires KVM enabled.      |
| Linux x64 (native) | ⚠️ untested but expected to work | Same path as WSL2 minus the `wsl --install` step.                  |
| Windows ARM64      | ❌ not supported                 | Not currently supported. Support may be added in a future release. |

Pick the section that matches your machine and follow it end to end. The "Install and run" steps at the bottom apply to both platforms.

## Install prerequisites on macOS

Tested on macOS ARM64 (Apple Silicon).

```bash
# Install Homebrew if you don't have it
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# If you just installed Homebrew, add it to your shell PATH
# (Apple Silicon path; for Intel Macs use /usr/local/bin/brew)
eval "$(/opt/homebrew/bin/brew shellenv)"

# Python 3.12+
brew install python@3.12

# uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env  # add uv to PATH for this shell
```

Skip ahead to [Install and run MagenticLite](#install-and-run-magenticlite).

## Install prerequisites on Windows (WSL)

Tested on Windows 11 x64 with WSL2 + Ubuntu.

### 1. Install WSL and Ubuntu

In **PowerShell as Administrator**:

```powershell
wsl --install
```

Reboot if prompted, then launch Ubuntu — either from the Start menu, or by running `wsl` (or `ubuntu`) in a new PowerShell window — and complete the first-time user setup. **Every command from here on runs inside the Ubuntu (WSL) shell.**

### 2. Enable KVM

```bash
sudo usermod -aG kvm $USER
```

Close and reopen the WSL terminal for the group change to take effect.

KVM gives the [Quicksand](https://microsoft.github.io/quicksand/) VM hardware acceleration. Without it the VM falls back to software emulation, which is significantly slower.

### 3. Install tools

```bash
# uv (Python package manager) — installed first because we use uv to manage Python
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env  # add uv to PATH for this shell

# Python 3.12 (managed by uv; the apt python3.12 package isn't available on Ubuntu 22.04)
uv python install 3.12
```

## Install and run MagenticLite

Once the platform-specific prerequisites are in place, the install + run steps are the same on both platforms.

```bash
# Create a project directory
mkdir magentic-lite && cd magentic-lite

# Create and activate a virtual environment
uv venv --python=3.12 --seed .venv
source .venv/bin/activate

# Install the latest 0.2.x release from PyPI
uv pip install "magentic_ui>=0.2.0"

# Run
magentic-ui --port 8081
```

Then visit <http://127.0.0.1:8081/> in your browser.

For subsequent runs:

```bash
cd magentic-lite
source .venv/bin/activate
magentic-ui --port 8081
```

> Only one MagenticLite instance can run at a time on the same port (default 8081).

## Coming from Magentic-UI 0.1.x?

If you previously ran a 0.1.x release of Magentic-UI on the same machine, two things to know:

- **Pin the version when you install.** PyPI still hosts the 0.1.x line under the same `magentic_ui` package name, so a plain `uv pip install magentic_ui` may pick up an older release. Pin to a 0.2.x version explicitly:

  ```bash
  uv pip install "magentic_ui>=0.2.0"
  ```

- **Use a fresh data directory.** MagenticLite (0.2.x) does not migrate the 0.1.x database. To keep the two installs side-by-side, point this run at a different `--appdir`:

  ```bash
  magentic-ui --port 8081 --appdir ~/.magentic-lite
  ```

  Without `--appdir`, MagenticLite uses the same default data directory as 1.0, which can lead to confusing state.

## A note on running MagenticLite as a shared service

MagenticLite is designed to be installed and run **locally on your own machine** by the same person who uses it. We don't recommend hosting it as a shared service for other users:

- **Concurrent multi-user sessions weren't a design goal**, so the UX degrades when several people share one instance.
- **The app exposes host-level capabilities to whoever can reach it** — most notably the file-system mounting controls used for browser uploads and downloads. Running it as a multi-user service effectively grants every user of that service the same file-system access as the host account.

If you do choose to host it, treat the resulting URL as you would shell access to the host machine.

## Next steps

- [Model Hosting Guide](./model-hosting-guide.md) — get a model endpoint to point MagenticLite at.
- [Configuration](./configuration.md) — sandbox, agent mode, and tool approval policies.
- [Troubleshooting](./troubleshooting.md) — common issues and fixes.
