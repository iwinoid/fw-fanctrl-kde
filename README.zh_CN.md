# Fan Control UI for KDE Plasma

[English](README.md)

[![standard-readme compliant](https://img.shields.io/badge/readme%20style-standard-brightgreen?style=for-the-badge)](https://github.com/RichardLitt/standard-readme)
[![License: GPL-3.0-or-later](https://img.shields.io/badge/License-GPL--3.0--or--later-blue?style=for-the-badge)](https://spdx.org/licenses/GPL-3.0-or-later.html)
[![powered by DeepSeek](https://img.shields.io/badge/powered_by-DeepSeek-4D6BFE?style=for-the-badge&logo=deepseek&logoColor=white)](https://deepseek.com)
[![powered by dsh](https://img.shields.io/badge/powered_by-dsh-4D6BFE?style=for-the-badge&logo=deepseek&logoColor=white)](https://github.com/deepseek-ai/deepseek-harness)
[![Platform: Linux](https://img.shields.io/badge/Platform-Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black)](https://www.linux.org/)
[![KDE Plasma 6](https://img.shields.io/badge/KDE_Plasma-6-1D99F3?style=for-the-badge&logo=kde&logoColor=white)](https://kde.org/plasma-desktop)


在 KDE Plasma 6 上控制 Framework 笔记本电脑的风扇策略

一个 KDE Plasma 6 小部件，给 Framework 笔记本和其他 Chrome-EC 机器使用。它给 fw-fanctrl 风扇控制服务套上图形界面。不用命令行，就能看温度和风扇转速、切换策略、调整速度曲线。保存时由 fw-fanctrl 自动校验并应用配置。

## 截图

|               弹出窗口               |             配置编辑器             |
| :----------------------------------: | :--------------------------------: |
| ![主窗口](image/README/mainwindow.png) | ![配置编辑器](image/README/conf.png) |

## 目录

- [背景](#背景)
- [安装](#安装)
  - [依赖](#依赖)
  - [从 Release 安装](#从-release-安装)
  - [从源码安装](#从源码安装)
  - [卸载](#卸载)
- [使用](#使用)
- [功能](#功能)
- [架构](#架构)
- [API](#api)
- [维护者](#维护者)
- [致谢](#致谢)
- [贡献](#贡献)
- [更新日志](#更新日志)
- [许可](#许可)

## 背景

笔记本在 Linux 上控制风扇，通常要靠命令行工具。fw-fanctrl 读取 `/etc/fw-fanctrl/config.json`，按每个策略的速度曲线驱动 Chrome-EC 风扇。本项目给 fw-fanctrl 提供 Plasma 6 界面。托盘小部件看状态、切策略。图形编辑器调策略和曲线。

## 安装

### 依赖

- 带 Chrome-EC 的笔记本，Linux系统。Framework 笔记本可用。在 HP Elite Dragonfly Chromebook 上测试过。
- KDE Plasma 6
- Python 3
- [fw-fanctrl](https://github.com/TamtamHero/fw-fanctrl)，已安装并运行。服务拥有 `/etc/fw-fanctrl/config.json`。

### 从 Release 安装

1. 从 [Releases](https://github.com/iwinoid/fw-fanctrl-kde/releases) 页面下载 `com.github.iwinoid.fw-fanctrl-kde-1.2.2.tar.xz`。
2. 在 Plasma 里打开 **添加小部件 → 获取新小部件... → 从本地文件安装**，选择该包。
3. 或用终端安装：

```bash
kpackagetool6 --type=Plasma/Applet --install com.github.iwinoid.fw-fanctrl-kde-1.2.2.tar.xz
```


### 从源码安装

```bash
git clone https://github.com/iwinoid/fw-fanctrl-kde.git
cd fw-fanctrl-kde
make install
```

`make install` 通过 `kpackagetool6` 安装小部件，设置辅助脚本执行权限，并重启 Plasma。`make reinstall` 重装，`make uninstall` 卸载，`make pack` 打 Release 包。不想自动重启时用 `RESTART=n make install`。

### 卸载

```bash
kpackagetool6 --type=Plasma/Applet --remove com.github.iwinoid.fw-fanctrl-kde
```

## 使用

1. 右键面板，打开 **添加小部件**，搜索"风扇"。
2. 点击托盘图标打开弹出窗口。
3. 用滑条切换策略，或悬停托盘图标滚动滚轮。
4. 右键托盘图标，选择 **配置**，编辑策略和风扇曲线。
5. 点击 **保存**。fw-fanctrl 自动校验并应用配置。

## 功能

- 实时状态：温度、风扇转速、当前策略（2 秒轮询）
- 切换策略：弹出窗滑条，或托盘图标滚轮
- 策略切换时显示 KDE OSD 通知
- 服务控制：重载、暂停、恢复、刷新
- 在线/离线提示：图标、状态文字、暂停动画
- 配置编辑器：新建、编辑、重命名、删除、拖拽排序策略
- 速度曲线编辑器，按温度自动排序
- 默认策略，以及电池供电时的独立策略
- 安全保存：fw-fanctrl 校验并应用配置
- 中英双语界面

## 架构

项目分三部分。

### 1. 后端 ： `scripts/fw_helper.py`

fw-fanctrl 命令行的 Python 封装。所有命令都在 stdout 输出 JSON，QML 侧只需解析 JSON。错误会归一化。每条命令都有超时，fw-fanctrl 卡住也不会冻住小部件。

### 2. 小组件前端 ： `contents/ui/FwBackend.qml` 和 `contents/ui/main.qml`

托盘小部件。每 2 秒轮询 fw-fanctrl 获取状态，显示温度和风扇转速。用滑条或滚轮切换策略。用 KDE OSD 通知策略变化。

### 3. 编辑器前端 ： `contents/ui/configCurves.qml`

图形化配置编辑器。加载配置，编辑策略和速度曲线，通过后端保存。保存前校验曲线（不允许空曲线、不允许重复温度点），归一化顺序，再交给 fw-fanctrl 应用。

### 数据流

QML 通过 Plasma 的 executable `DataSource` 调用 `fw_helper.py`。辅助脚本调用 fw-fanctrl 命令行并返回 JSON。保存走 fw-fanctrl 的 `set_config`，由它校验并应用配置。

```
QML (小组件界面)  ──executable DataSource──▶  scripts/fw_helper.py  ──CLI──▶  fw-fanctrl  ──▶  风扇控制
                                              (stdout 输出 JSON)                (校验并应用
                                                                                /etc/fw-fanctrl/config.json)
```

## API

后端提供以下命令。每条命令在 stdout 输出一个 JSON 对象。

| 命令 | 说明 |
|---|---|
| `get_status` | 温度、风扇转速、当前策略、策略列表 |
| `get_strategies` | 策略名列表 |
| `set_strategy <name>` | 切换当前策略 |
| `reload` | 重载 fw-fanctrl 配置 |
| `pause` / `resume` | 暂停或恢复风扇控制 |
| `get_config` | 配置及其 schema |
| `save_config <json>` | 校验并应用新配置 |

## 维护者

- [Iwinoid](https://github.com/iwinoid) ： iwinoid@outlook.com

## 致谢

- [fw-fanctrl](https://github.com/TamtamHero/fw-fanctrl)，GPL-2.0
- [KDE Plasma & Kirigami](https://kde.org)，LGPL-2.0+
- [Qt 6](https://qt.io)，LGPL-3.0 / GPL-2.0
- [waicool20/fw-fanctrl-ui](https://github.com/waicool20/fw-fanctrl-ui)，设计参考
- 由 DeepSeek V4 经 [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness) 开发

## 贡献

问题报告和提问请到 [GitHub Issues](https://github.com/iwinoid/fw-fanctrl-kde/issues) 页面。接受 Pull Request。

请保持友善和建设性。不确定改动是否合适时，先开 issue 讨论。

## 更新日志

- **1.2.2** ： 用单色 SVG 图标替换 PNG 图标，服务异常时弹通知
- **1.2.1** ： 修复曲线自动排序污染温度点、导致保存失败的问题
- **1.2** ： 重写配置编辑器：拖拽排序策略、电池策略、安全保存
- **1.1** ： 增加 OSD 弹窗和滚轮切换策略
- **1.0.1** ： 首个公开发布

## 许可

[GPL-3.0-or-later](LICENSE)，版权归 Iwinoid。

项目使用了 [fw-fanctrl](https://github.com/TamtamHero/fw-fanctrl)（GPL-2.0）、[KDE Plasma & Kirigami](https://kde.org)（LGPL-2.0+）和 [Qt 6](https://qt.io)（LGPL-3.0 / GPL-2.0）。