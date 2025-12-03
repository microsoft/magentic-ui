# Troubleshooting

## Model endpoint cold starts

If you're using a managed model endpoint that scales to zero when idle (Hugging Face Inference Endpoints with scale-to-zero, for example), the **first call after the endpoint has been idle** may take **30–90 seconds** while the platform brings a replica back up. During that window you may see:

- a `503` response or a `Verify & Save` error in MagenticLite's Settings, or
- the first chat turn appearing to hang.

Wait a minute and try again. Subsequent requests respond at normal speed until the endpoint scales to zero again.

See the [Model Hosting Guide](./model-hosting-guide.md#a3-scale-to-zero-and-cold-starts) for the full explanation.

## Settings → Models verification fails

When you click **Verify & Save**, MagenticLite sends a probe request to the endpoint. Common failures:

| Symptom (banner)                                                      | Likely cause                                                                                       |
| --------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| `Endpoint returned HTTP 401` or `403`                                 | API Key field is empty or wrong (different endpoints return one or the other for the same problem) |
| `Endpoint returned HTTP 503` on the first attempt                     | Cold start — see the section above; wait a minute and click Verify again                           |
| `Connection refused — is the server running?` or other network errors | Endpoint URL is wrong (typo in the host, missing `https://`, VPN/firewall issue)                   |

Re-check the values against the source you copied them from (the Hugging Face dashboard, the Foundry deployment page, etc.) and try again.

## Installation and runtime

### `magentic-ui` command not found

Your virtual environment isn't activated. Re-activate it and try again:

```bash
deactivate                    # if another env is active
source .venv/bin/activate
magentic-ui --port 8081
```

### Port 8081 already in use

Another MagenticLite process is already running on the same port. Stop it, or run on a different port:

```bash
magentic-ui --port 8082
```

### Quicksand VM fails to start (Linux/WSL2)

- Confirm KVM is available: `[ -e /dev/kvm ] && echo ok` should print `ok`.
- Confirm your user is in the `kvm` group: `groups | grep -q kvm && echo ok`. If not, run `sudo usermod -aG kvm $USER` and restart your shell.
- Without KVM the VM falls back to software emulation, which is significantly slower but should still work.

### Browser viewer is blank or unresponsive

- Make sure the Quicksand VM is healthy (check the MagenticLite logs for `quicksand` errors).
- Check that any local firewall isn't blocking the noVNC port the app picks for the embedded browser viewer.
- Restart MagenticLite — the browser is recreated on each session.

## Coming from Magentic-UI 0.1.x?

The 0.1.x line of Magentic-UI is still on PyPI under the same `magentic_ui` package name, and its on-disk data lives in the same default app directory. A few things to be aware of:

### `pip install` picks up Magentic-UI 0.1.x instead of MagenticLite

A plain `uv pip install magentic_ui` (no version pin) may resolve to a 0.1.x release. Pin to a 0.2.x version explicitly:

```bash
uv pip install "magentic_ui>=0.2.0"
```

(Adjust the version to whatever 0.2.x release you intend to run.)

### MagenticLite reads / writes my old Magentic-UI 0.1.x data

MagenticLite (0.2.x) doesn't migrate the 0.1.x database. By default both versions use the same app directory, which can lead to confusing state. To keep them separate, point MagenticLite at a different `--appdir`:

```bash
magentic-ui --port 8081 --appdir ~/.magentic-lite
```

## Still having issues?

- Re-check the [Installation Guide](./installation.md) and [Configuration](./configuration.md).
- Search [GitHub Issues](https://github.com/microsoft/magentic-ui/issues) for similar problems.
- Open a new issue and include:
  1. A detailed description of your problem
  2. Information about your system (OS, hardware acceleration support, MagenticLite version)
  3. Steps to reproduce the issue
