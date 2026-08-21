# Fan Control UI for Plasma
[简体中文](README.zh_CN.md)

[![standard-readme compliant](https://img.shields.io/badge/readme%20style-standard-brightgreen?style=for-the-badge)](https://github.com/RichardLitt/standard-readme)
[![CI](https://img.shields.io/github/actions/workflow/status/iwinoid/fw-fanctrl-kde/ci.yml?style=for-the-badge&label=CI&logo=github)](https://github.com/iwinoid/fw-fanctrl-kde/actions/workflows/ci.yml)
[![License: GPL-3.0-or-later](https://img.shields.io/badge/License-GPL--3.0--or--later-blue?style=for-the-badge)](https://spdx.org/licenses/GPL-3.0-or-later.html)
[![powered by DeepSeek](https://img.shields.io/badge/powered_by-DeepSeek-4D6BFE?style=for-the-badge&logo=deepseek&logoColor=white)](https://deepseek.com)
[![powered by dsh](https://img.shields.io/badge/powered_by-dsh-4D6BFE?style=for-the-badge&logo=deepseek&logoColor=white)](https://github.com/deepseek-ai/deepseek-harness)
[![Platform: Linux](https://img.shields.io/badge/Platform-Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black)](https://www.linux.org/)
[![KDE Plasma 6](https://img.shields.io/badge/KDE_Plasma-6-1D99F3?style=for-the-badge&logo=kde&logoColor=white)](https://kde.org/plasma-desktop)

Control Framework laptop fan strategies on KDE Plasma 6

A KDE Plasma 6 widget for Framework laptops and other Chrome-EC machines. It wraps the fw-fanctrl fan-control service in a GUI. You can watch temperature and fan speed, switch strategies, and tune speed curves without the terminal. fw-fanctrl validates and applies the configuration when you save.

## Screenshots

|                Popup UI                |          Configuration Editor          |
| :------------------------------------: | :------------------------------------: |
| ![Main Window](image/README/mainwindow.png) | ![Config Editor](image/README/conf.png) |

## Table of Contents

- [Background](#background)
- [Install](#install)
  - [Dependencies](#dependencies)
  - [From Release](#from-release)
  - [From Source](#from-source)
  - [Uninstall](#uninstall)
- [Usage](#usage)
- [Features](#features)
- [Architecture](#architecture)
- [API](#api)
- [Maintainers](#maintainers)
- [Thanks](#thanks)
- [Contributing](#contributing)
- [Changelog](#changelog)
- [License](#license)

## Background

Linux laptop fan control usually needs manual tooling. fw-fanctrl reads a JSON configuration from `/etc/fw-fanctrl/config.json` and drives Chrome-EC fans through speed curves, one per strategy. This project gives fw-fanctrl a Plasma 6 interface: a tray widget for status and switching, and a graphical editor for strategies and curves.

Developed by DeepSeek V4 via [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness).

## Install

### Dependencies

- Linux kernel ≥ 6.11 on a laptop with Chrome EC, such as Chromebooks and Framework Laptops; tested on an HP Elite Dragonfly Chromebook.
- KDE Plasma 6
- Python ≥ 3.12
- [fw-fanctrl](https://github.com/TamtamHero/fw-fanctrl), installed and running. The service owns `/etc/fw-fanctrl/config.json`.

The kernel and Python minimum versions are inherited from fw-fanctrl.

### From Release

1. Download `com.github.iwinoid.fw-fanctrl-kde-1.3.tar.xz` from the [Releases](https://github.com/iwinoid/fw-fanctrl-kde/releases) page.
2. In Plasma, open **Add Widgets → Get New Widgets... → Install from local file** and select the package.
3. Or install from a terminal:

```bash
kpackagetool6 --type=Plasma/Applet --install com.github.iwinoid.fw-fanctrl-kde-1.3.tar.xz
```

### From Source

```bash
git clone https://github.com/iwinoid/fw-fanctrl-kde.git
cd fw-fanctrl-kde
make install
```

`make install` installs the widget through `kpackagetool6`, sets the helper script executable, and restarts Plasma. `make reinstall` reinstalls, `make uninstall` removes it, `make pack` creates the release archive, and `RESTART=n make install` skips the Plasma restart.

### Uninstall

```bash
kpackagetool6 --type=Plasma/Applet --remove com.github.iwinoid.fw-fanctrl-kde
```

## Usage

1. Right-click the panel, open **Add Widgets** and search for "Fan".
2. Click the tray icon to open the popup.
3. Use the slider, or hover the tray icon and scroll the wheel, to switch strategy.
4. Right-click the tray icon and choose **Configure** to edit strategies and fan curves.
5. Click **Save**. fw-fanctrl validates and applies the configuration automatically.

## Features

- Real-time status: temperature, fan speed, active strategy (2 second poll)
- Strategy switching: popup slider, or scroll wheel on the tray icon
- KDE OSD notification when the strategy changes
- Service control: reload, pause, resume, refresh
- Online/offline indication: icon, status text, paused animation
- Config editor: create, edit, rename, delete, and drag-to-reorder strategies
- Speed curve editor with automatic sorting by temperature
- Default strategy, plus a separate strategy while on battery
- Safe saving: fw-fanctrl validates and applies the configuration
- Bilingual UI: English and Chinese

## Architecture

The project has three parts.

### 1. Backend — `scripts/fw_helper.py`

A Python wrapper around the fw-fanctrl CLI. It always prints JSON on stdout, so the QML side only needs to parse JSON. It normalizes errors, and every command has a timeout so a stuck fw-fanctrl process cannot freeze the widget.

### 2. Widget frontend — `contents/ui/FwBackend.qml` and `contents/ui/main.qml`

The tray widget. It polls fw-fanctrl every 2 seconds for status, renders temperature and fan speed, switches strategies from the slider or the scroll wheel, and shows the strategy change with a KDE OSD notification.

### 3. Editor frontend — `contents/ui/configCurves.qml`

A graphical config editor. It loads the configuration, edits strategies and speed curves, and saves through the backend. Saving validates the curves (no empty curves, no duplicate temperature points), normalizes their order, and lets fw-fanctrl apply them.

### Data flow

QML calls `fw_helper.py` through the Plasma executable `DataSource`. The helper invokes the fw-fanctrl CLI and returns JSON. Saving goes through fw-fanctrl's `set_config`, which validates and applies the configuration.

```
QML (plasmoid UI)  ──executable DataSource──▶  scripts/fw_helper.py  ──CLI──▶  fw-fanctrl  ──▶  fan control
                                              (JSON over stdout)                 (validates & applies
                                                                                  /etc/fw-fanctrl/config.json)
```

## API

The backend exposes these commands. Each one prints a single JSON object on stdout.

| Command | Description |
|---|---|
| `get_status` | Temperature, fan speed, current strategy, list of strategies |
| `get_strategies` | List of strategy names |
| `set_strategy <name>` | Switch the active strategy |
| `reload` | Reload the fw-fanctrl configuration |
| `pause` / `resume` | Pause or resume fan control |
| `get_config` | The configuration and its schema |
| `save_config <json>` | Validate and apply a new configuration |

## Maintainers

- [Iwinoid](https://github.com/iwinoid) — iwinoid@outlook.com

## Thanks

- [fw-fanctrl](https://github.com/TamtamHero/fw-fanctrl), GPL-2.0
- [waicool20/fw-fanctrl-ui](https://github.com/waicool20/fw-fanctrl-ui), backend design reference

## Contributing

Bug reports and questions are welcome on the [GitHub Issues](https://github.com/iwinoid/fw-fanctrl-kde/issues) page. Pull requests are accepted.

This project follows a code-of-conduct style common to open source; be respectful and constructive. If you are unsure whether a change fits, open an issue first.

## Changelog

- **1.3** : first normalized release: standard-readme docs, QML formatting and lint cleanup, unit tests, CI
- **1.2.2** : replace the PNG icons with a monochrome SVG icon, notify when the service goes down
- **1.2.1** — fix the curve auto-sort corrupting temperature points and blocking save
- **1.2** — rewrite the config editor: drag-to-reorder strategies, battery strategy, safe saving
- **1.1** — add the OSD popup and scroll-wheel strategy switching
- **1.0.1** — first public release

## License

[GPL-3.0-or-later](LICENSE) © Iwinoid

This project uses [fw-fanctrl](https://github.com/TamtamHero/fw-fanctrl) (GPL-2.0), [KDE Plasma & Kirigami](https://kde.org) (LGPL-2.0+), and [Qt 6](https://qt.io) (LGPL-3.0 / GPL-2.0).
