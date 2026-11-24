# Changelog | سجل التغييرات

All notable changes to Eidak are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- GitHub Actions CI running the headless test suites on Windows and Linux.
- Config validation: invalid `config.json` values fall back to defaults with a warning.
- `pyproject.toml` project metadata and a Ruff lint configuration.

## [1.0.0] - 2026-11-24

First public release.

### Added
- **Mouse mode** — move the cursor with the index finger; pinch thumb+index
  for left click (hold to drag); pinch thumb+middle for right click; two
  quick pinches for double click; index+middle swipe up/down to scroll;
  hold an open palm to pause/resume.
- **Video mode** (press `M` to switch) — open palm play/pause; swipe
  right/left to seek; swipe up/down for volume; fist twice to close the
  video/tab (first fist arms, second confirms); hold 3 fingers to speed up;
  hold 4 fingers (no thumb) to slow down; hold thumb up for fullscreen.
- **Keyboard controls** — `Q` quit, `M` switch mouse/video mode, `P` pause,
  `+` / `-` cursor sensitivity.
- **Camera reliability** — auto-probing of camera indices 0–4 and every
  Windows driver path (DirectShow, MediaFoundation); frame validation
  (black/empty frames are rejected); auto-reconnect with backoff if the
  camera freezes or is unplugged; on-screen low-light warning;
  `Diagnose-Camera.bat` standalone camera report.
- **Safety** — PyAutoGUI fail-safe: slam the real mouse into any screen
  corner for an emergency stop.
- **Settings** in `config.json` (camera index, sensitivity, speeds, …),
  written after the first run.
- **Privacy by design** — everything runs locally and offline; the camera
  feed is never recorded, uploaded or sent anywhere.
- **Guides** — full user manuals in Arabic (`UserGuide-AR.pdf`) and English
  (`UserGuide-EN.pdf`).
- **Windows installer** — `Install-And-Run.bat` installs dependencies on the
  first run and starts the app afterwards.
- MIT license.
