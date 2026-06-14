# Codex Tray

Linux system-tray monitor for [Codex CLI](https://github.com/openai/codex) usage. Shows remaining 5-hour and 7-day rolling token limits at a glance.

## Install

### Debian / Ubuntu (one-click)

Download the latest `.deb` from [Releases](https://github.com/anomalyco/tray-app/releases/latest) and double-click to install.

### Other Linux distros

```bash
git clone https://github.com/anomalyco/tray-app.git
cd tray-app
./install.sh
```

## Prerequisites

[Codex CLI](https://github.com/openai/codex) must be installed and logged in at least once:

```bash
npm install -g @openai/codex
codex
```

This creates `~/.codex/auth.json` which the tray app reads. If the file is missing when the app starts, a dialog will guide you through the setup.

## Usage

```bash
codex-tray
```

Run it in the background to keep it in the tray:

```bash
codex-tray &
```

The icon appears in your system tray. Hover to see remaining percentages. Left-click to open the detail popup showing usage bars, session stats, and recent sessions.

The app auto-refreshes every 60 seconds and starts automatically on login (via `~/.config/autostart/`).

### What the popup shows

- **Usage bars** — remaining percentage for the 5-hour rolling window and 7-day window. Colors indicate status: green (>75% remaining), yellow (25–75%), red (<25%).
- **Last refreshed** — timestamp of the most recent successful API fetch, so you know how stale the data is.
- **Session stats** — total tokens, weekly tokens, session count.
- **Recent sessions** — last 5 sessions with title, token count, and date.

If the API is unreachable, the app keeps the last known data and shows an offline notice with a Retry button.

## Notes

- **Wayland** — `Gtk.StatusIcon` is deprecated and may not appear in all Wayland environments. If the tray icon doesn't show, try running under X11 or use a tray compatibility layer.
- **Logs** — written to `~/.cache/codex-tray.log`.

## Development

```bash
git clone https://github.com/anomalyco/tray-app.git
cd tray-app
pip install -e .
codex-tray
```

Requires system packages: `python3-gi`, `python3-gi-cairo`, `gir1.2-gtk-3.0`.

## Build

```bash
scripts/build-deb.sh <version>
```

Example: `scripts/build-deb.sh 0.1.0` produces `codex-tray_0.1.0_all.deb`.

## License

[Unlicense](LICENSE) — public domain.
