[English](README.md)

# Fan Control UI for Plasma

用于在 Framework 笔记本电脑（或其他兼容Chrome EC的笔记本）上控制 **fw-fanctrl** 风扇策略的 KDE Plasma 6 小部件。我的笔记本是HP Elite Dragonfly Chromebook。

一个Vibe Coding项目，由 ![DeepSeek V4](https://img.shields.io/badge/DeepSeek%20V4-1477D1?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyByb2xlPSJpbWciIHZpZXdCb3g9IjAgMCAyNCAyNCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cGF0aCBkPSJNMjMuNzQ4IDQuNjUxYy0uMjU0LS4xMjQtLjM2NC4xMTMtLjUxMi4yMzMtLjA1MS4wNC0uMDk0LjA5LS4xMzcuMTM3LS4zNzIuMzk3LS44MDYuNjU3LTEuMzczLjYyNi0uODI5LS4wNDYtMS41MzcuMjE0LTIuMTYzLjg0OC0uMTMzLS43ODItLjU3NS0xLjI0OC0xLjI0Ny0xLjU0OC0uMzUyLS4xNTUtLjcwOC0uMzExLS45NTUtLjY1LS4xNzItLjI0LS4yMTktLjUwOS0uMzA1LS43NzQtLjA1NS0uMTYtLjExLS4zMjMtLjI5My0uMzUtLjItLjAzMS0uMjc4LjEzNi0uMzU2LjI3Ni0uMzEzLjU3Mi0uNDM0IDEuMjAyLS40MjIgMS44NC4wMjcgMS40MzYuNjMzIDIuNTggMS44MzggMy4zOTMuMTM3LjA5NC4xNzIuMTg3LjEyOS4zMjMtLjA4Mi4yOC0uMTguNTUzLS4yNjYuODMzLS4wNTUuMTc5LS4xMzcuMjE4LS4zMjguMTRhNS41IDUuNSAwIDAgMS0xLjczNy0xLjE3OWMtLjg1Ny0uODI4LTEuNjMxLTEuNzQzLTIuNTk3LTIuNDZhMTIgMTIgMCAwIDAtLjY4OS0uNDdjLS45ODUtLjk1Ny4xMy0xLjc0My4zODctMS44MzYuMjctLjA5OC4wOTQtLjQzMy0uNzc4LS40MjgtLjg3Mi4wMDMtMS42Ny4yOTUtMi42ODcuNjg1YTMgMyAwIDAgMS0uNDY1LjEzNiA5LjYgOS42IDAgMCAwLTIuODgzLS4xMDFjLTEuODg1LjIxLTMuMzkgMS4xLTQuNDk3IDIuNjIyQy4wODIgOC43NzYtLjIzMSAxMC44NTQuMTUyIDEzLjAyYy40MDMgMi4yODQgMS41NjggNC4xNzUgMy4zNiA1LjY1MyAxLjg1NyAxLjUzMyAzLjk5NyAyLjI4NCA2LjQzOCAyLjE0IDEuNDgyLS4wODUgMy4xMzItLjI4NCA0Ljk5NC0xLjg2LjQ3LjIzNC45NjIuMzI4IDEuNzguMzk4LjYyOS4wNTggMS4yMzUtLjAzMSAxLjcwNS0uMTI5LjczNS0uMTU1LjY4NC0uODM2LjQxOC0uOTYxLTIuMTU1LTEuMDA0LTEuNjgyLS41OTUtMi4xMTItLjkyNiAxLjA5NS0xLjI5NSAyLjc2OC0zLjU5OCAzLjI4NC02LjczMy4wNS0uMzQ2LjExNS0uODM0LjEwOC0xLjExNC0uMDA0LS4xNzEuMDM1LS4yMzguMjMtLjI1N2E0LjIgNC4yIDAgMCAwIDEuNTQ1LS40NzVjMS4zOTctLjc2MyAxLjk2LTIuMDE2IDIuMDkzLTMuNTE3LjAyLS4yMy0uMDA0LS40NjctLjI0Ny0uNTg4TTExLjU4IDE4LjE2OGMtMi4wODgtMS42NDItMy4xMDEtMi4xODMtMy41Mi0yLjE2LS4zOS4wMjQtLjMyLjQ3Mi0uMjM0Ljc2My4wOS4yODguMjA3LjQ4Ny4zNzEuNzQuMTE0LjE2Ny4xOTIuNDE2LS4xMTMuNjAzLS42NzMuNDE2LTEuODQyLS4xNC0xLjg5Ny0uMTY4LTEuMzYxLS44MDEtMi41LTEuODYtMy4zMDEtMy4zMDYtLjc3NS0xLjM5My0xLjIyNS0yLjg4OC0xLjI5OS00LjQ4Mi0uMDItLjM4NS4wOTQtLjUyMi40NzctLjU5MmE0LjcgNC43IDAgMCAxIDEuNTMtLjAzOGMyLjEzMS4zMTEgMy45NDYgMS4yNjQgNS40NjcgMi43NzQuODY4Ljg2IDEuNTI1IDEuODg3IDIuMjAyIDIuODkuNzIgMS4wNjYgMS40OTQgMi4wODIgMi40OCAyLjkxNS4zNDguMjkxLjYyNi41MTMuODkyLjY3Ny0uODAyLjA5LTIuMTQuMTA5LTMuMDU1LS42MTV6bTEuMDAxLTYuNDRhLjMwNi4zMDYgMCAwIDEgLjQxNS0uMjg3LjMuMyAwIDAgMSAuMTEzLjA3NC4zLjMgMCAwIDEgLjA4Ni4yMTRjMCAuMTctLjEzNi4zMDctLjMwOC4zMDdhLjMwMy4zMDMgMCAwIDEtLjMwNi0uMzA3bTMuMTEgMS41OTZjLS4yLjA4MS0uNC4xNTEtLjU5MS4xNmExLjI1IDEuMjUgMCAwIDEtLjc5OC0uMjU0Yy0uMjc0LS4yMy0uNDctLjM1OC0uNTUxLS43NThhMS43IDEuNyAwIDAgMSAuMDE1LS41ODhjLjA3LS4zMjctLjAwNy0uNTM3LS4yMzgtLjcyNy0uMTg4LS4xNTYtLjQyNi0uMTk5LS42ODktLjE5OWEuNi42IDAgMCAxLS4yNTQtLjA3OC4yNTMuMjUzIDAgMCAxLS4xMTQtLjM1OCAxIDEgMCAwIDEgLjE5Mi0uMjFjLjM1Ni0uMjAyLjc2Ny0uMTM2IDEuMTQ2LjAxNi4zNTIuMTQ0LjYxOC40MDggMS4wMDEuNzgyLjM5Mi40NTEuNDYyLjU3Ni42ODUuOTE1LjE3Ni4yNjQuMzM2LjUzNi40NDYuODQ4LjA2Ni4xOTQtLjAyLjM1My0uMjUuNDUiLz48L3N2Zz4=&logoColor=white)驱动

功能

- **实时状态**：显示当前温度、风扇转速和策略
- **策略滑条**：快速在静音↔性能之间切换策略
- **系统托盘集成**
- **配置编辑器**：创建、编辑、重命名、删除策略，配置速度曲线

## 截图

|               弹出窗口               |             配置编辑器             |
| :----------------------------------: | :--------------------------------: |
| ![主窗口](image/README/mainwindow.png) | ![配置编辑器](image/README/conf.png) |

## 依赖

![Linux](https://img.shields.io/badge/Platform-Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black) （在 ![Arch](https://img.shields.io/badge/-Arch_Linux-1793D1?style=for-the-badge&logo=archlinux&logoColor=white) 上测试）

![KDE Plasma](https://img.shields.io/badge/KDE_Plasma-1D99F3?style=for-the-badge&logo=kde&logoColor=white)

![Python 3](https://img.shields.io/badge/Python%203-3776AB?style=for-the-badge&logo=python&logoColor=white)

**fw-fanctrl** — [TamtamHero/fw-fanctrl](https://github.com/TamtamHero/fw-fanctrl)

## 安装

### 源码安装

```bash
git clone https://github.com/iwinoid/fw-fanctl-kde.git
cd fw-fanctl-kde
make install
```

将自动：

1. 通过 `kpackagetool6` 安装小部件
2. 设置辅助脚本的可执行权限
3. 自动重启 Plasma

### 手动安装

```bash
kpackagetool6 --type=Plasma/Applet --install .
```

然后重启 Plasma：`kquitapp6 plasmashell; plasmashell &`

## 使用

1. 右键面板 → **添加小部件** → 搜索"风扇"
2. 点击托盘图标打开弹出窗口
3. 拖动滑条切换策略
4. 右键托盘图标 → **配置** 编辑策略和风扇曲线
5. 点击 **保存** 应用更改（需通过 `pkexec` 输入管理员密码）

## 项目结构

```
fw-fanctrl-kde/
├── LICENSE                        # GPL-3.0
├── Makefile                       # 安装/卸载/打包
├── README.md
├── README.zh_CN.md
├── metadata.json                  # Plasmoid 元数据
├── scripts/
│   └── fw_helper.py              # Python 后端 (fw-fanctrl CLI 封装)
├── contents/
│   ├── config/
│   │   ├── config.qml            # 配置页注册
│   │   └── main.xml              # KConfigXT 配置表
│   ├── images/
│   │   ├── 16.png, 32.png, 64.png # 工具栏图标
│   │   └── offline.png           # 离线状态图标
│   └── ui/
│       ├── configCurves.qml      # 配置编辑器界面
│       ├── FwBackend.qml         # QML 后端 (DataSource + 轮询定时器)
│       └── main.qml              # 主界面
└── image/
    └── README/
        ├── conf.png              # 配置编辑器截图
        └── mainwindow.png        # 弹出窗口截图
```

## 许可

**GPL-3.0-or-later** — 详见 [LICENSE](LICENSE)。

本项目使用了 [fw-fanctrl](https://github.com/TamtamHero/fw-fanctrl) (GPL-2.0)、
[KDE Plasma &amp; Kirigami](https://kde.org) (LGPL-2.0+) 和 [Qt 6](https://qt.io) (LGPL-3.0 / GPL-2.0)。

本项目还参考了 [waicool20/fw-fanctrl-ui](https://github.com/waicool20/fw-fanctrl-ui) 的代码设计。
