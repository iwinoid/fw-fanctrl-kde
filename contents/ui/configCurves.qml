import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.plasma.plasma5support

/**
 * Fan curve configuration page.
 */
Item {
    id: root

    readonly property bool isChinese: Qt.locale().name.startsWith("zh")
    function tr(en, zh) { return isChinese ? zh : en }

    readonly property string helperScript:
        Qt.resolvedUrl("../../scripts/fw_helper.py").toString().replace("file://", "")

    // ─── State ────────────────────────────────────────────────────
    property var configData: ({})
    property var strategyNames: []
    property string selectedStrategy: ""
    property bool configLoaded: false
    property bool configChanged: false
    property bool saving: false
    property string statusText: tr("Loading...", "加载中...")
    property bool statusSuccess: true
    property int curveVersion: 0

    // ─── DataSource ───────────────────────────────────────────────
    DataSource {
        id: executor
        engine: "executable"
        connectedSources: []

        function exec(cmd) {
            connectSource(cmd)
        }

        onNewData: function(sourceName, data) {
            var stdout = (data["stdout"] || "").trim()
            var stderr = (data["stderr"] || "").trim()
            var exitCode = data["exit code"] || -1
            disconnectSource(sourceName)

            if (sourceName.indexOf("get_config") > -1)
                handleConfig(stdout, stderr, exitCode)
            else
                handleResult(stdout, stderr, exitCode)
        }
    }

    function parseJSON(text) {
        try { return JSON.parse(text) }
        catch(e) { return null }
    }

    function handleConfig(stdout, stderr, exitCode) {
        var data = parseJSON(stdout)
        if (data && data.config) {
            configData = data.config
            refreshStrategyList()
            selectedStrategy = strategyNames.length > 0 ? strategyNames[0] : ""
            configLoaded = true
            configChanged = false
            statusText = ""
            statusSuccess = true
        } else {
            statusText = data ? (data.error || "Config error") : (stderr || "Failed to load")
            statusSuccess = false
        }
    }

    function handleResult(stdout, stderr, exitCode) {
        saving = false
        var data = parseJSON(stdout)
        if (data && data.success) {
            configChanged = false
            statusText = tr("Configuration saved! fw-fanctrl reloaded.", "配置已保存！已重载 fw-fanctrl。")
            statusSuccess = true
            executor.exec(helperScript + " reload")
        } else {
            statusText = data ? (data.message || "Error") : (stderr || "Save failed")
            statusSuccess = false
        }
    }

    function refreshStrategyList() {
        var names = []
        for (var key in configData.strategies) {
            if (configData.strategies.hasOwnProperty(key))
                names.push(key)
        }
        strategyNames = names
    }

    function getStrategyValue(key, defaultVal) {
        if (!configData.strategies || !selectedStrategy) return defaultVal
        var s = configData.strategies[selectedStrategy]
        return s && s[key] !== undefined ? s[key] : defaultVal
    }

    function getCurvePoints() {
        if (!configData.strategies || !selectedStrategy) return []
        var s = configData.strategies[selectedStrategy]
        return s && s.speedCurve ? s.speedCurve : []
    }

    function updateParam(key, value) {
        if (!configData.strategies || !selectedStrategy) return
        if (!configData.strategies[selectedStrategy])
            configData.strategies[selectedStrategy] = { speedCurve: [] }
        configData.strategies[selectedStrategy][key] = value
        configChanged = true
    }

    function updateCurvePoint(index, key, value) {
        var pts = getCurvePoints()
        if (index >= 0 && index < pts.length) {
            pts[index][key] = value
            configChanged = true
        }
    }

    function addCurvePoint() {
        var pts = getCurvePoints()
        var lastTemp = pts.length > 0 ? pts[pts.length - 1].temp : 0
        pts.push({ temp: Math.min(lastTemp + 5, 100), speed: 50 })
        configData.strategies[selectedStrategy].speedCurve = pts
        configChanged = true
        curveVersion++
    }

    function removeCurvePoint(index) {
        var pts = getCurvePoints()
        if (pts.length > 1) {
            pts.splice(index, 1)
            configData.strategies[selectedStrategy].speedCurve = pts
            configChanged = true
            curveVersion++
        }
    }

    function addStrategy(name, sourceName) {
        if (!configData.strategies) configData.strategies = {}
        var src = configData.strategies[sourceName]
        if (src) {
            configData.strategies[name] = JSON.parse(JSON.stringify(src))
        } else {
            configData.strategies[name] = {
                fanSpeedUpdateFrequency: 5, movingAverageInterval: 30,
                speedCurve: [{ temp: 0, speed: 0 }, { temp: 50, speed: 25 },
                             { temp: 75, speed: 50 }, { temp: 85, speed: 100 }]
            }
        }
        refreshStrategyList()
        selectedStrategy = name
        configChanged = true
    }

    function removeStrategy(name) {
        if (!configData.strategies || strategyNames.length <= 1) return
        if (configData.defaultStrategy === name) {
            var others = strategyNames.filter(function(s) { return s !== name })
            configData.defaultStrategy = others.length > 0 ? others[0] : ""
        }
        delete configData.strategies[name]
        if (selectedStrategy === name)
            selectedStrategy = strategyNames.length > 0 ? strategyNames[0] : ""
        refreshStrategyList()
        configChanged = true
    }

    function renameStrategy(oldName, newName) {
        if (oldName === newName || !configData.strategies[oldName]) return
        if (configData.strategies[newName]) return
        configData.strategies[newName] = configData.strategies[oldName]
        delete configData.strategies[oldName]
        if (configData.defaultStrategy === oldName) configData.defaultStrategy = newName
        selectedStrategy = newName
        refreshStrategyList()
        configChanged = true
    }

    function saveConfigData() {
        saving = true
        statusText = tr("Saving... (admin password may be required)", "保存中... (可能需要管理员密码)")
        statusSuccess = true
        var json = JSON.stringify(configData, null, 4)
        executor.exec(helperScript + " save_config '" + json.replace(/'/g, "'\\''") + "'")
    }

    Component.onCompleted: {
        executor.exec(helperScript + " get_config")
    }

    // ═══════════════════════════════════════════════════════════════
    // UI
    // ═══════════════════════════════════════════════════════════════

    // Status bar
    Controls.Label {
        anchors { top: parent.top; left: parent.left; right: parent.right; margins: Kirigami.Units.smallSpacing }
        text: statusText
        visible: statusText.length > 0
        color: statusSuccess ? Kirigami.Theme.positiveTextColor : Kirigami.Theme.negativeTextColor
        font.bold: true
        z: 2
    }

    // Loading
    Controls.BusyIndicator {
        anchors.centerIn: parent
        running: !configLoaded
        visible: !configLoaded
    }

    // Editor
    Controls.ScrollView {
        visible: configLoaded
        anchors { top: parent.top; left: parent.left; right: parent.right; bottom: saveBar.top; margins: Kirigami.Units.smallSpacing }
        clip: true

        ColumnLayout {
            width: parent.width
            spacing: Kirigami.Units.smallSpacing

            // Default + Battery strategy
            Kirigami.AbstractCard {
                Layout.fillWidth: true
                contentItem: GridLayout {
                    columns: 2
                    anchors.margins: Kirigami.Units.smallSpacing
                    rowSpacing: Kirigami.Units.smallSpacing
                    columnSpacing: Kirigami.Units.smallSpacing

                    Controls.Label { text: tr("Default Strategy:", "默认策略:") }
                    Controls.ComboBox {
                        Layout.fillWidth: true
                        model: strategyNames
                        currentIndex: strategyNames.indexOf(configData.defaultStrategy || "")
                        onActivated: function(idx) {
                            if (idx >= 0) { configData.defaultStrategy = strategyNames[idx]; configChanged = true }
                        }
                    }


                }
            }

            // Strategies
            RowLayout {
                Layout.fillWidth: true
                Layout.preferredHeight: Kirigami.Units.gridUnit * 18
                spacing: Kirigami.Units.largeSpacing

                // LEFT: Strategy list
                ColumnLayout {
                    Layout.preferredWidth: Kirigami.Units.gridUnit * 8
                    Layout.fillHeight: true
                    spacing: Kirigami.Units.smallSpacing

                    RowLayout {
                        Layout.fillWidth: true
                        Controls.Label { text: tr("Strategies", "策略列表"); font.bold: true; Layout.fillWidth: true }
                        Controls.ToolButton {
                            icon.name: "list-add"
                            onClicked: addDialog.open()
                            Controls.ToolTip { text: tr("Add", "添加") }
                        }
                    }

                    ListView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        model: strategyNames
                        currentIndex: strategyNames.indexOf(selectedStrategy)
                        delegate: Controls.ItemDelegate {
                            width: parent.width
                            text: modelData
                            highlighted: ListView.isCurrentItem
                            onClicked: selectedStrategy = modelData
                            contentItem: RowLayout {
                                Controls.Label { text: modelData; Layout.fillWidth: true; font.bold: modelData === configData.defaultStrategy }
                                Controls.ToolButton {
                                    icon.name: "list-remove"
                                    visible: strategyNames.length > 1
                                    onClicked: removeStrategy(modelData)
                                }
                            }
                        }
                    }
                }

                // RIGHT: Strategy editor
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    visible: selectedStrategy.length > 0
                    spacing: Kirigami.Units.smallSpacing

                    Controls.TextField {
                        text: selectedStrategy
                        Layout.fillWidth: true
                        onTextChanged: {
                            if (text !== selectedStrategy && text.length > 0) renameStrategy(selectedStrategy, text)
                        }
                    }

                    GridLayout {
                        columns: 2
                        columnSpacing: Kirigami.Units.smallSpacing
                        rowSpacing: Kirigami.Units.smallSpacing
                        Layout.fillWidth: true

                        Controls.Label { text: tr("Update Freq (s):", "更新频率(秒):") }
                        Controls.SpinBox { from: 1; to: 10; value: getStrategyValue("fanSpeedUpdateFrequency", 5); onValueChanged: updateParam("fanSpeedUpdateFrequency", value); Layout.fillWidth: true }

                        Controls.Label { text: tr("Moving Avg (s):", "移动平均(秒):") }
                        Controls.SpinBox { from: 1; to: 100; value: getStrategyValue("movingAverageInterval", 30); onValueChanged: updateParam("movingAverageInterval", value); Layout.fillWidth: true }
                    }

                    RowLayout { Layout.fillWidth: true
                        Controls.Label { text: tr("Speed Curve", "速度曲线"); font.bold: true; Layout.fillWidth: true }
                        Controls.ToolButton { icon.name: "list-add"; onClicked: addCurvePoint(); Controls.ToolTip { text: tr("Add point", "添加点") } }
                    }

                    Repeater {
                        model: { curveVersion; return getCurvePoints() }
                        delegate: RowLayout {
                            width: parent.width; spacing: Kirigami.Units.smallSpacing
                            Controls.TextField {
                                Layout.fillWidth: true
                                text: modelData.temp.toString()
                                validator: DoubleValidator { bottom: 0; top: 100; decimals: 2 }
                                onTextChanged: { if (acceptableInput) updateCurvePoint(index, "temp", parseFloat(text)) }
                            }
                            Controls.Label { text: "°C →" }
                            Controls.TextField {
                                Layout.fillWidth: true
                                text: modelData.speed.toString()
                                validator: IntValidator { bottom: 0; top: 100 }
                                onTextChanged: { if (acceptableInput) updateCurvePoint(index, "speed", parseInt(text)) }
                            }
                            Controls.Label { text: "%" }
                            Controls.ToolButton { icon.name: "list-remove"; enabled: getCurvePoints().length > 1; onClicked: removeCurvePoint(index) }
                        }
                    }
                }

                Controls.Label {
                    visible: configLoaded && selectedStrategy.length === 0
                    text: tr("Select a strategy", "选择要编辑的策略")
                    opacity: 0.5
                    Layout.alignment: Qt.AlignCenter
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                }
            }
        }
    }

    // Save bar at bottom
    Rectangle {
        id: saveBar
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        height: Kirigami.Units.gridUnit * 3
        visible: configLoaded
        color: Kirigami.Theme.backgroundColor

        RowLayout {
            anchors.fill: parent
            anchors.margins: Kirigami.Units.smallSpacing
            Item { Layout.fillWidth: true }
            Controls.Button {
                text: tr("Reload", "重新加载")
                icon.name: "view-refresh"
                enabled: !saving
                onClicked: executor.exec(helperScript + " get_config")
            }
            Controls.Button {
                text: tr("Save", "保存")
                icon.name: "document-save"
                highlighted: true
                enabled: configChanged && !saving
                onClicked: saveConfigData()
            }
        }
    }

    // ─── Add Strategy Dialog ─────────────────────────────────────
    Kirigami.Dialog {
        id: addDialog
        title: tr("Add New Strategy", "添加新策略")
        preferredWidth: Kirigami.Units.gridUnit * 22
        leftPadding: Kirigami.Units.gridUnit
        rightPadding: Kirigami.Units.gridUnit
        topPadding: Kirigami.Units.gridUnit
        bottomPadding: Kirigami.Units.gridUnit

        ColumnLayout {
            spacing: Kirigami.Units.smallSpacing

            Controls.Label { text: tr("Name:", "名称:") }
            Controls.TextField {
                id: newName
                Layout.fillWidth: true
                placeholderText: "MyCustom"
                validator: RegularExpressionValidator { regularExpression: /^[a-zA-Z0-9_-]+$/ }
            }

            Controls.Label { text: tr("Copy from:", "从现有复制:") }
            Controls.ComboBox { id: copyFrom; Layout.fillWidth: true; model: strategyNames; currentIndex: 0 }

            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                Controls.Button { text: tr("Cancel", "取消"); onClicked: { newName.text = ""; addDialog.close() } }
                Controls.Button {
                    text: tr("Add", "添加"); highlighted: true
                    enabled: newName.acceptableInput
                    onClicked: {
                        var n = newName.text.trim()
                        if (n.length > 0 && strategyNames.indexOf(n) < 0) {
                            addStrategy(n, copyFrom.currentText)
                            newName.text = ""; addDialog.close()
                        }
                    }
                }
            }
        }
    }
}
