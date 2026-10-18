# fw-fanctrl-kde 交接说明

最后更新：2026-10-19。本轮代码提交：`9ac28ca`、`9fff1b6`、`58db4c1`；本文档为单独提交。

## 一句话状态

v1.3 功能完整、可运行；本轮完成质量检查与修复（3 个提交，未发版）。本机部件已安装、`fw-fanctrl` 服务运行中；`main` 领先 `origin/main` 3 个提交，网络恢复后需要推送。

## 项目与环境

| 项 | 值 |
|---|---|
| 包 ID | `com.github.iwinoid.fw-fanctrl-kde`（`metadata.json` Version `1.3`） |
| 仓库 | 独立 git 仓库，分支 `main`；上游 `github.com/iwinoid/fw-fanctrl-kde` |
| 运行环境 | Plasma 6.8.0 / Qt 6.12.0；`fw-fanctrl` 1.1.0，systemd 服务 `fw-fanctrl.service` active |
| 配置文件 | `/etc/fw-fanctrl/config.json` 与 `config.schema.json`（服务所有，GUI 只经 CLI 读写） |
| 本机安装位置 | `~/.local/share/plasma/plasmoids/com.github.iwinoid.fw-fanctrl-kde/` |

## 代码地图

| 路径 | 作用 |
|---|---|
| `contents/ui/main.qml` | 托盘 applet 主界面：策略滑杆、风扇转速、服务控制按钮、OSD 通知、滚轮切换策略 |
| `contents/ui/FwBackend.qml` | 后端：`plasma5support.DataSource` 调 `scripts/fw_helper.py`，2 秒轮询、JSON 解析、离线检测与限流通知 |
| `contents/ui/configCurves.qml` | 配置编辑器：策略增删改/拖拽排序、曲线点编辑与自动排序、默认/电池策略、保存校验 |
| `contents/config/config.qml` | 配置页注册（`ConfigModel` → `configCurves.qml`），语言随 `Qt.locale()` |
| `scripts/fw_helper.py` | 唯一后端入口，stdout 只输出 JSON；命令：`get_status` `get_strategies` `set_strategy` `reload` `pause` `resume` `get_config` `save_config` `notify` |
| `tests/test_fw_helper.py` | 32 个 Python 单测（helper 全命令与错误路径） |
| `Makefile` | `install` / `reinstall` / `uninstall` / `pack` / `clean` / `restart-plasma` |
| `.github/workflows/ci.yml` | QML lint（Arch 容器）+ Python 单测 + 打包内容校验 |

数据流：`QML → executable DataSource → fw_helper.py → fw-fanctrl CLI → /etc/fw-fanctrl/config.json`。保存走 `fw-fanctrl set_config`，由 fw-fanctrl 自己校验并生效，GUI 不直接写系统文件。

## 本轮（2026-10-19）检查结果

全部在项目内实际执行过，命令见下节。

| 检查 | 结果 |
|---|---|
| Qt6 `qmllint` 4 个 QML 文件 | 通过：无任何警告/错误（修复前 `config.qml` 有 1 条 Unqualified access） |
| `qmlformat` 幂等性 | 4 个文件格式化后与仓库内容零差异 |
| Python 单测 | `Ran 32 tests ... OK` |
| `py_compile` | 通过 |
| 打包 + CI 包内容检查 | 通过：14 条目、无 `tests/`/`.qmllint.ini`/`.github/` 泄漏（新增排除 `tmp/`） |
| 隔离安装 `kpackagetool6` | 通过（`XDG_DATA_HOME` 指向项目 `tmp/`，未动系统） |
| 无头预览（Xvfb + plasmoidviewer，软件渲染） | applet 正常渲染，日志无 QML 错误；从打包产物安装的副本加载正常 |
| helper 对接真实服务 | `get_status` / `get_strategies` / `get_config` 均返回合法 JSON |
| 配置编辑器离屏测试 | 加载真实 `/etc/fw-fanctrl/config.json`；加载后不脏、浏览策略不脏、真实修改仍脏（缺陷修复的回归验证） |
| `config.qml` 构造测试 | `count=1`，分类名 `风扇曲线`、图标/源正确 |

### 本轮提交

| 提交 | 内容 |
|---|---|
| `9ac28ca` | `fix(config-editor)`：`updateParam`/`updateCurvePoint` 跳过同值写入，修掉“只切换策略就变成已修改、Save 误亮、重载弹丢弃确认”的问题 |
| `9fff1b6` | `lint(config)`：`contents/config/config.qml` 用根对象 id 限定 `tr()`，跑 `qmlformat`，并加入 CI 的 qmllint 文件列表（此前该文件从未被 lint） |
| `58db4c1` | `chore`：`.gitignore` 忽略 `tmp/`；`make pack` 排除 `$(PKG_DIR)/tmp`（`--exclude-vcs` 不会跳过被 gitignore 的目录，本地打包会把截图带进发布包） |

## 复现验证命令

```bash
cd /home/iwinoid/Documents/项目/KDE/fw-fanctrl-kde

# QML lint（必须用 Qt6，/usr/bin/qmllint 是 Qt5）——无输出才算干净
/usr/lib/qt6/bin/qmllint \
  contents/ui/main.qml contents/ui/FwBackend.qml contents/ui/configCurves.qml \
  contents/config/config.qml

# 格式化（就地；复核时先拷到 tmp/ 再对比，避免改工作区）
/usr/lib/qt6/bin/qmlformat -i contents/ui/*.qml contents/config/config.qml

# Python 编译与单测
python3 -m py_compile scripts/fw_helper.py
python3 -m unittest discover -s tests -v

# 后端对接真实服务（只读命令，不会改风扇策略）
python3 scripts/fw_helper.py get_status
python3 scripts/fw_helper.py get_strategies

# 打包（注意：输出在仓库父目录，即工作区根目录）
make pack
# 或在项目内验证包内容而不写根目录：
#   cp -r contents scripts metadata.json tmp/stage/<PKG_ID>/ && cd tmp/stage && tar ...
```

无头预览/截图用 `tools/preview-headless.sh`（若存在）或按 `AGENTS.md` 的 Xvfb + `plasmoidviewer` 手动流程；截图只写 `tmp/`，用完删除。**不要**截用户桌面。

## 已知问题 / 技术债

1. **i18n 自造方案**：全项目用 `tr(en, zh)` + `Qt.locale()` 手写双语，没有 `i18n()`/po，不符合 KDE 翻译体系；要上 KDE Store 或接社区翻译需迁移（工作量大，涉及所有文案与 `config.qml`）。
2. **CI lint 过滤规则偏宽**：`grep -viE "...cannot resolve alias..."` 等会掩盖真实告警；`.qmllint.ini` 的 `MaxWarnings=-1` 让本地 qmllint 有警告也返回 0，必须看输出不能只看 exit code。
3. **`make pack` 写仓库父目录**：产物落在工作区根目录，与工作区“只在项目目录内写文件”的约定冲突；CI 依赖该路径，暂未改动，发布时注意清理。
4. **配置页无自动化 UI 测试**：现有保障是 Python 单测 + 离屏 QML 测试脚本（脚本未入库）。QML 层逻辑（曲线排序、脏标记、重命名校验）可以做成 `tests/qml/` 的 `qmltestrunner` 用例。
5. **helper 中少量英文硬编码**：如 `"Command failed"`、`"OK"`、`get_status` 的错误消息，直接显示在状态行；中文界面下不完全本地化。
6. **README 截图是 2026-08 的旧图**：界面目前没有变化，可暂不更新；若发新版建议用无头预览重截。
7. **网络**：本机当前 GitHub git/API 均不通（TLS/EOF），`git push` 会失败；推送前先确认网络。
8. **配置编辑器交互细节**：曲线点 `TextField` 在 `onEditingFinished` 触发自动排序时会重建 delegate（失去焦点），属既有设计，未改动。

## 后续建议（按优先级）

1. 发 v1.3.1：包含本轮 3 个提交，补 README 更新日志一条。
2. 把离屏 QML 验证脚本整理进 `tests/qml/` 并接入 CI（`qmltestrunner`），覆盖曲线排序与脏标记。
3. 增加 `make lint` / `make test` 统一本地入口，与 CI 命令保持一致。
4. i18n 迁移（若计划上 KDE Store 或接受外部翻译）。
5. KDE Store 提交流程：截图、描述、许可证标注。
6. 用 `tools/preview-headless.sh`（若保留）更新 README 双语文截图。

## 回滚

```bash
cd /home/iwinoid/Documents/项目/KDE/fw-fanctrl-kde
git revert 58db4c1 9fff1b6 9ac28ca   # 逆序回滚本轮提交
```

安装/卸载（会写 `~/.local/share/plasma`，`make install` 默认重启 plasmashell，`RESTART=n make install` 可跳过）：

```bash
make install     # 安装/覆盖当前工作区版本
make uninstall   # 卸载
```

## 参考

- `README.md` / `README.zh_CN.md`：用户向文档（standard-readme 结构）
- `vendor/develop-kde-org/content/docs/plasma/widget/`：Plasmoid 教程与 API（工作区只读镜像）
- `AGENTS.md`（工作区根目录）：环境、文档查阅、写文件范围与验证约定
