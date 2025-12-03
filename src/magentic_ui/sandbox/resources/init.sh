#!/usr/bin/env bash
# Per-boot setup for the magentic-ui Quicksand VM.
#
# Runs on every VM boot. quicksand-cua (>=0.3.10) ships novnc, websockify,
# socat, rsync, flake8, and file pre-installed. This script disables the
# default systemd services (magentic-ui manages them per-slot) and creates
# the shared browser-profile directory.
set -e

echo "[1/2] Disabling default systemd services..."
systemctl disable --now xvfb x11vnc chromium novnc 2>/dev/null || true

echo "[2/2] Creating profile directory..."
mkdir -p /profiles/master

echo "Init setup complete."
