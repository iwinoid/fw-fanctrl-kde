import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.plasma.plasma5support

/**
 * Fan curve configuration page.
 *
 * Data flow:
 *   fw_helper.py get_config  -> configData / strategyNames
 *   editor                    -> configData mutations
 *   fw_helper.py save_config  -> fw-fanctrl validates and applies the config
 */
Item {
    id: root

    implicitWidth: Kirigami.Units.gridUnit * 24
    implicitHeight: Kirigami.Units.gridUnit * 27
    Layout.minimumWidth: Kirigami.Units.gridUnit * 23
    Layout.minimumHeight: Kirigami.Units.gridUnit * 23

    readonly property bool isChinese: Qt.locale().name.startsWith("zh")
    function tr(en, zh) { return isChinese ? zh : en }

    readonly property string helperScript: decodeURIComponent(
        Qt.resolvedUrl("../../scripts/fw_helper.py").toString().replace("file://", "")
    )

    function shellQuote(arg) {
        return "'" + arg.replace(/'/g, "'\\''") + "'"
    }

    function commandFromSource(sourceName) {
        var prefix = shellQuote(helperScript) + " "
        if (sourceName.indexOf(prefix) !== 0)
            return ""
        var rest = sourceName.substring(prefix.length).trim()
        var space = rest.indexOf(" ")
        return space < 0 ? rest : rest.substring(0, space)
    }

    // ─── State ────────────────────────────────────────────────────
    property var configData: ({})
    property var strategyNames: []
    property string selectedStrategy: ""
    property bool configLoaded: false
    property bool configChanged: false
    property bool configLoadError: false
    property bool saving: false
    property string statusText: tr("Loading...", "加载中...")
    property bool statusSuccess: true
    property int curveVersion: 0

    function isValidStrategyName(name) {
        return /^[a-zA-Z0-9_-]+$/.test(name)
    }

    function showStatus(message, success) {
        statusText = message
        statusSuccess = success
    }

    // ─── DataSource ───────────────────────────────────────────────
    DataSource {
        id: executor
        engine: "executable"
        connectedSources: []

        function exec(cmd, arg) {
            var line = root.shellQuote(root.helperScript) + " " + cmd
            if (arg !== undefined && arg !== "")
                line += " " + arg
            connectSource(line)
        }

        onNewData: function(sourceName, data) {
            var stdout = (data["stdout"] || "").trim()
            var stderr = (data["stderr"] || "").trim()
            var exitCode = data["exit code"] !== undefined ? data["exit code"] : -1
            var command = root.commandFromSource(sourceName)

            disconnectSource(sourceName)

            if (command === "get_config")
                handleConfig(stdout, stderr, exitCode)
            else
                handleResult(stdout, stderr, exitCode)
        }
    }

    function parseJSON(text) {
        try { return JSON.parse(text) }
        catch (e) { return null }
    }

    function loadConfig() {
        statusText = tr("Loading...", "加载中...")
        statusSuccess = true
        executor.exec("get_config")
    }

    function handleConfig(stdout, stderr, exitCode) {
        var data = parseJSON(stdout)
        if (data && data.config) {
            var previous = selectedStrategy
            configData = data.config
            refreshStrategyList()
            selectedStrategy = strategyNames.indexOf(previous) >= 0 ? previous : (strategyNames.length > 0 ? strategyNames[0] : "")
            configLoaded = true
            configLoadError = false
            configChanged = false
            statusText = ""
            statusSuccess = true
        } else {
            configLoadError = !configLoaded
            statusText = data ? (data.error || "Config error") : (stderr || tr("Failed to load config", "配置加载失败"))
            statusSuccess = false
        }
    }

    function handleResult(stdout, stderr, exitCode) {
        saving = false
        var data = parseJSON(stdout)
        if (data && data.success) {
            configChanged = false
            statusText = tr("Configuration saved!", "配置已保存！")
            statusSuccess = true
        } else {
            statusText = data ? (data.message || data.error || "Error") : (stderr || tr("Save failed", "保存失败"))
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
        syncStrategyModel()
    }

    function syncStrategyModel() {
        strategyListModel.clear()
        for (var i = 0; i < strategyNames.length; i++)
            strategyListModel.append({ name: strategyNames[i] })
    }

    function finalizeStrategyOrder() {
        var ordered = []
        for (var i = 0; i < strategyListModel.count; i++)
            ordered.push(strategyListModel.get(i).name)

        if (JSON.stringify(ordered) === JSON.stringify(strategyNames))
            return

        var newStrategies = {}
        for (var j = 0; j < ordered.length; j++) {
            var key = ordered[j]
            if (configData.strategies && configData.strategies.hasOwnProperty(key))
                newStrategies[key] = configData.strategies[key]
        }

        configData.strategies = newStrategies
        strategyNames = ordered
        configChanged = true
    }

    // ─── Strategy editing helpers ──────────────────────────────────
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

    function sortPoints(pts) {
        return pts.slice().sort(function(a, b) {
            return (Number(a.temp) || 0) - (Number(b.temp) || 0)
        })
    }

    function sortCurrentCurve() {
        var pts = getCurvePoints()
        if (pts.length < 2)
            return

        var sorted = sortPoints(pts)
        if (JSON.stringify(sorted) === JSON.stringify(pts))
            return

        for (var i = 0; i < pts.length; i++) {
            pts[i].temp = sorted[i].temp
            pts[i].speed = sorted[i].speed
        }
        curveVersion++
    }

    function curveMaxTemp() {
        var pts = getCurvePoints()
        var maxTemp = -1
        for (var i = 0; i < pts.length; i++)
            maxTemp = Math.max(maxTemp, Number(pts[i].temp) || 0)
        return maxTemp
    }

    function addCurvePoint() {
        var pts = getCurvePoints()
        if (!configData.strategies || !selectedStrategy) return

        var maxTemp = curveMaxTemp()
        if (maxTemp >= 100) {
            showStatus(tr("Curve already reaches 100°C", "曲线已到达 100°C"), false)
            return
        }

        var newTemp = maxTemp < 0 ? 0 : Math.min(maxTemp + 5, 100)
        pts.push({ temp: newTemp, speed: 50 })
        sortCurrentCurve()
        curveVersion++
        configChanged = true
    }

    function removeCurvePoint(index) {
        var pts = getCurvePoints()
        if (pts.length <= 1 || index < 0 || index >= pts.length) return
        pts.splice(index, 1)
        curveVersion++
        configChanged = true
    }

    function addStrategy(name, sourceName) {
        if (!configData.strategies) configData.strategies = {}
        var src = configData.strategies[sourceName]
        if (src) {
            configData.strategies[name] = JSON.parse(JSON.stringify(src))
        } else {
            configData.strategies[name] = {
                fanSpeedUpdateFrequency: 5,
                movingAverageInterval: 30,
                speedCurve: [
                    { temp: 0, speed: 0 },
                    { temp: 50, speed: 25 },
                    { temp: 75, speed: 50 },
                    { temp: 85, speed: 100 }
                ]
            }
        }
        selectedStrategy = name
        refreshStrategyList()
        configChanged = true
    }

    function removeStrategy(name) {
        if (!configData.strategies || !configData.strategies.hasOwnProperty(name)) return
        if (strategyNames.length <= 1) return

        var remaining = strategyNames.filter(function(s) { return s !== name })

        if (configData.defaultStrategy === name)
            configData.defaultStrategy = remaining.length > 0 ? remaining[0] : ""
        if (configData.strategyOnDischarging === name)
            configData.strategyOnDischarging = ""

        if (selectedStrategy === name)
            selectedStrategy = remaining.length > 0 ? remaining[0] : ""

        delete configData.strategies[name]
        strategyNames = remaining
        syncStrategyModel()
        configChanged = true
    }

    function renameStrategy(oldName, newName) {
        if (oldName === newName)
            return true
        if (!isValidStrategyName(newName)) return false
        if (!configData.strategies || !configData.strategies.hasOwnProperty(oldName)) return false
        if (configData.strategies.hasOwnProperty(newName)) return false

        configData.strategies[newName] = configData.strategies[oldName]
        delete configData.strategies[oldName]

        if (configData.defaultStrategy === oldName)
            configData.defaultStrategy = newName
        if (configData.strategyOnDischarging === oldName)
            configData.strategyOnDischarging = newName
        if (selectedStrategy === oldName)
            selectedStrategy = newName

        refreshStrategyList()
        configChanged = true
        return true
    }

    function commitStrategyRename() {
        var newName = strategyNameField.text.trim()
        if (newName === selectedStrategy)
            return

        if (!isValidStrategyName(newName)) {
            showStatus(tr("Invalid strategy name: only letters, numbers, '_' and '-' are allowed.",
                          "策略名无效：只能包含字母、数字、下划线和连字符。"), false)
            strategyNameField.text = Qt.binding(function() { return root.selectedStrategy })
            return
        }

        if (strategyNames.indexOf(newName) >= 0) {
            showStatus(tr("A strategy with this name already exists.", "同名策略已存在。"), false)
            strategyNameField.text = Qt.binding(function() { return root.selectedStrategy })
            return
        }

        if (!renameStrategy(selectedStrategy, newName)) {
            showStatus(tr("Could not rename strategy.", "无法重命名策略。"), false)
            strategyNameField.text = Qt.binding(function() { return root.selectedStrategy })
        }
    }

    function validateAndNormalizeCurves() {
        if (!configData.strategies)
            return tr("No strategies configured", "没有配置任何策略")

        var changed = false
        for (var key in configData.strategies) {
            if (!configData.strategies.hasOwnProperty(key))
                continue

            var strategy = configData.strategies[key]
            if (!strategy || !Array.isArray(strategy.speedCurve) || strategy.speedCurve.length === 0)
                return tr("Strategy '%1' has no speed curve", "策略 '%1' 没有速度曲线").arg(key)

            var sorted = sortPoints(strategy.speedCurve)
            for (var i = 1; i < sorted.length; i++) {
                if (Math.abs(Number(sorted[i].temp) - Number(sorted[i - 1].temp)) < 0.001)
                    return tr("Strategy '%1' has duplicate temperature points", "策略 '%1' 存在重复的温度点").arg(key)
            }

            if (JSON.stringify(sorted) !== JSON.stringify(strategy.speedCurve)) {
                strategy.speedCurve = sorted
                changed = true
            }
        }

        if (changed)
            curveVersion++
        return ""
    }

    function validateReferences() {
        if (!configData.strategies) return tr("No strategies configured", "没有配置任何策略")
        if (!configData.strategies.hasOwnProperty(configData.defaultStrategy))
            return tr("Default strategy is invalid", "默认策略无效")
        if (configData.strategyOnDischarging && !configData.strategies.hasOwnProperty(configData.strategyOnDischarging))
            return tr("Battery strategy is invalid", "电池供电策略无效")
        return ""
    }

    function saveConfigData() {
        var curveError = validateAndNormalizeCurves()
        if (curveError) {
            showStatus(curveError, false)
            return
        }

        var referenceError = validateReferences()
        if (referenceError) {
            showStatus(referenceError, false)
            return
        }

        saving = true
        statusText = tr("Saving...", "保存中...")
        statusSuccess = true
        var json = JSON.stringify(configData, null, 4)
        executor.exec("save_config", shellQuote(json))
    }

    function retryLoadConfig() {
        configLoadError = false
        loadConfig()
    }

    // ─── Strategy list model for ListItemDragHandle ────────────────
    ListModel {
        id: strategyListModel
    }

    Component.onCompleted: {
        loadConfig()
    }

    // ═══════════════════════════════════════════════════════════════
    // UI
    // ═══════════════════════════════════════════════════════════════
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Kirigami.Units.smallSpacing
        spacing: Kirigami.Units.smallSpacing

        Controls.Label {
            Layout.fillWidth: true
            text: statusText
            visible: statusText.length > 0
            color: statusSuccess ? Kirigami.Theme.positiveTextColor : Kirigami.Theme.negativeTextColor
            font.bold: true
            wrapMode: Text.WordWrap
            elide: Text.ElideRight
            maximumLineCount: 2
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            Controls.BusyIndicator {
                anchors.centerIn: parent
                running: !configLoaded && !configLoadError
                visible: !configLoaded && !configLoadError
            }

            Controls.Button {
                anchors.centerIn: parent
                visible: !configLoaded && configLoadError
                text: tr("Retry", "重试")
                icon.name: "view-refresh"
                onClicked: retryLoadConfig()
            }

            ColumnLayout {
                                    visible: configLoaded
                anchors.fill: parent
                spacing: Kirigami.Units.smallSpacing

                    RowLayout {
                        id: strategyArea
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.minimumHeight: Kirigami.Units.gridUnit * 10
                        spacing: 0

                        // ── Strategy list ─────────────────────────
                        Kirigami.AbstractCard {
                            id: strategyListCard
                                                                                                                        clip: true
                            Layout.preferredWidth: Kirigami.Units.gridUnit * 9.5
                            Layout.minimumWidth: Kirigami.Units.gridUnit * 9.5
                            Layout.maximumWidth: Kirigami.Units.gridUnit * 9.5
                            Layout.fillHeight: true

                            contentItem: ColumnLayout {
                                width: strategyListCard.availableWidth
                                height: strategyListCard.availableHeight
                                spacing: Kirigami.Units.smallSpacing

                                RowLayout {
                                    Layout.fillWidth: true
                                    Controls.Label {
                                        text: tr("Strategies", "策略列表")
                                        font.bold: true
                                        Layout.fillWidth: true
                                    }
                                    Controls.ToolButton {
                                        icon.name: "list-add"
                                        onClicked: addDialog.open()
                                        Controls.ToolTip { text: tr("Add strategy", "添加策略") }
                                    }
                                }

                                ListView {
                                    id: strategyList
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    clip: true
                                    model: strategyListModel
                                    spacing: Kirigami.Units.smallSpacing

                                    moveDisplaced: Transition {
                                        YAnimator {
                                            duration: Kirigami.Units.longDuration
                                            easing.type: Easing.InOutQuad
                                        }
                                    }

                                    delegate: Item {
                                        id: strategyDelegateContainer
                                        required property string name
                                        required property int index
                                        width: strategyList.width
                                        height: strategyItem.implicitHeight

                                        Controls.ItemDelegate {
                                            id: strategyItem
                                            width: parent.width
                                            highlighted: name === root.selectedStrategy
                                            onClicked: root.selectedStrategy = name

                                            contentItem: RowLayout {
                                                spacing: Kirigami.Units.smallSpacing

                                                Kirigami.ListItemDragHandle {
                                                    listItem: strategyItem
                                                    listView: strategyList
                                                    onMoveRequested: (oldIndex, newIndex) => {
                                                        strategyListModel.move(oldIndex, newIndex, 1)
                                                    }
                                                    onDropped: root.finalizeStrategyOrder()
                                                }

                                                Controls.Label {
                                                    text: name
                                                    Layout.fillWidth: true
                                                    elide: Text.ElideRight
                                                    font.bold: name === configData.defaultStrategy
                                                }

                                                Controls.ToolButton {
                                                    icon.name: "list-remove"
                                                    visible: strategyNames.length > 1
                                                    onClicked: requestRemoveStrategy(name)
                                                    Controls.ToolTip { text: tr("Delete strategy", "删除策略") }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        // ── Strategy editor ──────────────────────
                        Kirigami.AbstractCard {
                            id: strategyEditorCard
                                                                                                                        clip: true
                            leftPadding: Kirigami.Units.smallSpacing
                            rightPadding: Kirigami.Units.smallSpacing
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            Layout.minimumWidth: Kirigami.Units.gridUnit * 13

                            contentItem: ColumnLayout {
                                                                                                            width: strategyEditorCard.availableWidth
                                height: strategyEditorCard.availableHeight
                                spacing: Kirigami.Units.smallSpacing
                                visible: selectedStrategy.length > 0

                                Controls.Label {
                                    text: tr("Strategy Editor", "策略编辑器")
                                    font.bold: true
                                }

                                GridLayout {
                                    columns: 2
                                    columnSpacing: Kirigami.Units.smallSpacing
                                    rowSpacing: Kirigami.Units.smallSpacing
                                    Layout.fillWidth: true

                                    Controls.Label { text: tr("Name:", "名称:") }
                                    Controls.TextField {
                                        id: strategyNameField
                                        Layout.fillWidth: true
                                        text: root.selectedStrategy
                                        validator: RegularExpressionValidator { regularExpression: /^[a-zA-Z0-9_-]+$/ }
                                        onEditingFinished: commitStrategyRename()
                                    }

                                    Controls.Label { text: tr("Update Freq (s):", "更新频率(秒):") }
                                    Controls.SpinBox {
                                        from: 1
                                        to: 10
                                        value: getStrategyValue("fanSpeedUpdateFrequency", 5)
                                        onValueChanged: updateParam("fanSpeedUpdateFrequency", value)
                                        Layout.fillWidth: true
                                    }

                                    Controls.Label { text: tr("Moving Avg (s):", "移动平均(秒):") }
                                    Controls.SpinBox {
                                        from: 1
                                        to: 100
                                        value: getStrategyValue("movingAverageInterval", 30)
                                        onValueChanged: updateParam("movingAverageInterval", value)
                                        Layout.fillWidth: true
                                    }
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    Controls.Label {
                                        text: tr("Speed Curve", "速度曲线")
                                        font.bold: true
                                        Layout.fillWidth: true
                                    }
                                    Controls.Label {
                                        text: tr("Points are sorted by temperature automatically.", "曲线点会按温度自动排序。")
                                        opacity: 0.6
                                        font.pointSize: Kirigami.Theme.smallFont.pointSize
                                    }
                                    Controls.ToolButton {
                                        icon.name: "list-add"
                                        enabled: curveMaxTemp() < 100
                                        onClicked: addCurvePoint()
                                        Controls.ToolTip { text: tr("Add point", "添加点") }
                                    }
                                }

                                Controls.ScrollView {
                                    id: curveScrollView
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    clip: true
                                    Controls.ScrollBar.vertical.policy: Controls.ScrollBar.AsNeeded
                                    Controls.ScrollBar.horizontal.policy: Controls.ScrollBar.AlwaysOff

                                    ColumnLayout {
                                        width: curveScrollView.availableWidth
                                        spacing: Kirigami.Units.smallSpacing

                                        Repeater {
                                            model: {
                                                curveVersion
                                                return getCurvePoints()
                                            }

                                            delegate: RowLayout {
                                                width: parent.width
                                                spacing: Kirigami.Units.smallSpacing

                                        Controls.TextField {
                                            Layout.fillWidth: true
                                            Layout.minimumWidth: Kirigami.Units.gridUnit * 2
                                            horizontalAlignment: Text.AlignHCenter
                                            text: modelData.temp.toString()
                                            validator: DoubleValidator { bottom: 0; top: 100; decimals: 2 }
                                            onTextChanged: {
                                                if (acceptableInput)
                                                    updateCurvePoint(index, "temp", parseFloat(text))
                                            }
                                            onEditingFinished: sortCurrentCurve()
                                        }

                                        Controls.Label { text: "°C →" }

                                        Controls.TextField {
                                            Layout.fillWidth: true
                                            Layout.minimumWidth: Kirigami.Units.gridUnit * 1.5
                                            horizontalAlignment: Text.AlignHCenter
                                            text: modelData.speed.toString()
                                            validator: IntValidator { bottom: 0; top: 100 }
                                            onTextChanged: {
                                                if (acceptableInput)
                                                    updateCurvePoint(index, "speed", parseInt(text))
                                            }
                                        }

                                        Controls.Label { text: "%" }

                                                Controls.ToolButton {
                                                    icon.name: "list-remove"
                                                    enabled: getCurvePoints().length > 1
                                                    onClicked: removeCurvePoint(index)
                                                    Controls.ToolTip { text: tr("Remove point", "删除点") }
                                                }
                                            }
                                        }
                                    }
                                }
                            }

                            Controls.Label {
                                anchors.centerIn: parent
                                visible: configLoaded && selectedStrategy.length === 0
                                text: tr("Select a strategy", "选择要编辑的策略")
                                opacity: 0.5
                            }
                        }
                    }

                    // ── Default / battery strategy ───────────────
                    Kirigami.AbstractCard {
                        id: defaultStrategyCard
                                                                                            clip: true
                        Layout.fillWidth: true

                        contentItem: GridLayout {
                            width: defaultStrategyCard.availableWidth
                            height: defaultStrategyCard.availableHeight
                            columns: 2
                            columnSpacing: Kirigami.Units.smallSpacing
                            rowSpacing: Kirigami.Units.smallSpacing

                            Controls.Label { text: tr("Default:", "默认:") }
                            Controls.ComboBox {
                                Layout.fillWidth: true
                                model: strategyNames
                                currentIndex: strategyNames.indexOf(configData.defaultStrategy || "")
                                onActivated: function(idx) {
                                    if (idx >= 0) {
                                        configData.defaultStrategy = strategyNames[idx]
                                        configChanged = true
                                    }
                                }
                            }

                            Controls.Label { text: tr("Battery:", "电池:") }
                            Controls.ComboBox {
                                Layout.fillWidth: true
                                model: [""].concat(strategyNames)
                                currentIndex: strategyNames.indexOf(configData.strategyOnDischarging || "") + 1
                                onActivated: function(idx) {
                                    configData.strategyOnDischarging = idx <= 0 ? "" : strategyNames[idx - 1]
                                    configChanged = true
                                }
                            }
                        }
                    }
                }
            }

        RowLayout {
            visible: configLoaded
            Layout.fillWidth: true
            spacing: Kirigami.Units.smallSpacing

            Item { Layout.fillWidth: true }

            Controls.Button {
                text: tr("Reload", "重新加载")
                icon.name: "view-refresh"
                enabled: !saving
                onClicked: {
                    if (configChanged)
                        discardDialog.open()
                    else
                        loadConfig()
                }
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

    // ─── Add strategy dialog ──────────────────────────────────────
    Kirigami.Dialog {
        id: addDialog
        title: tr("Add New Strategy", "添加新策略")
        preferredWidth: Kirigami.Units.gridUnit * 22
        leftPadding: Kirigami.Units.gridUnit
        rightPadding: Kirigami.Units.gridUnit
        topPadding: Kirigami.Units.gridUnit
        bottomPadding: Kirigami.Units.gridUnit

        property string errorText: ""

        onVisibleChanged: {
            if (visible) {
                newName.clear()
                errorText = ""
                copyFrom.currentIndex = strategyNames.indexOf(selectedStrategy)
                if (copyFrom.currentIndex < 0)
                    copyFrom.currentIndex = 0
            }
        }

        ColumnLayout {
            spacing: Kirigami.Units.smallSpacing

            Controls.Label { text: tr("Name:", "名称:") }
            Controls.TextField {
                id: newName
                Layout.fillWidth: true
                placeholderText: "MyCustom"
                validator: RegularExpressionValidator { regularExpression: /^[a-zA-Z0-9_-]+$/ }
            }

            Controls.Label {
                visible: addDialog.errorText.length > 0
                text: addDialog.errorText
                color: Kirigami.Theme.negativeTextColor
                font.pointSize: Kirigami.Theme.smallFont.pointSize
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }

            Controls.Label { text: tr("Copy from:", "从现有复制:") }
            Controls.ComboBox {
                id: copyFrom
                Layout.fillWidth: true
                model: strategyNames
                currentIndex: 0
            }

            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                Controls.Button {
                    text: tr("Cancel", "取消")
                    onClicked: addDialog.close()
                }
                Controls.Button {
                    text: tr("Add", "添加")
                    highlighted: true
                    enabled: newName.acceptableInput
                    onClicked: {
                        var n = newName.text.trim()
                        if (n.length === 0) {
                            addDialog.errorText = tr("Name cannot be empty", "名称不能为空")
                            return
                        }
                        if (strategyNames.indexOf(n) >= 0) {
                            addDialog.errorText = tr("A strategy with this name already exists.", "同名策略已存在。")
                            return
                        }
                        addStrategy(n, copyFrom.currentText)
                        addDialog.close()
                    }
                }
            }
        }
    }

    // ─── Delete confirmation ──────────────────────────────────────
    Kirigami.Dialog {
        id: deleteDialog
        title: tr("Delete Strategy", "删除策略")
        preferredWidth: Kirigami.Units.gridUnit * 18
        leftPadding: Kirigami.Units.gridUnit
        rightPadding: Kirigami.Units.gridUnit
        topPadding: Kirigami.Units.gridUnit
        bottomPadding: Kirigami.Units.gridUnit
        property string pendingName: ""

        ColumnLayout {
            spacing: Kirigami.Units.smallSpacing
            Controls.Label {
                Layout.fillWidth: true
                text: tr("Delete strategy '%1'?", "确定删除策略 '%1' 吗？").arg(deleteDialog.pendingName)
                wrapMode: Text.WordWrap
            }
            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                Controls.Button {
                    text: tr("Cancel", "取消")
                    onClicked: deleteDialog.close()
                }
                Controls.Button {
                    text: tr("Delete", "删除")
                    highlighted: true
                    onClicked: {
                        removeStrategy(deleteDialog.pendingName)
                        deleteDialog.close()
                    }
                }
            }
        }
    }

    function requestRemoveStrategy(name) {
        deleteDialog.pendingName = name
        deleteDialog.open()
    }

    // ─── Discard changes confirmation ─────────────────────────────
    Kirigami.Dialog {
        id: discardDialog
        title: tr("Discard Changes", "放弃修改")
        preferredWidth: Kirigami.Units.gridUnit * 18
        leftPadding: Kirigami.Units.gridUnit
        rightPadding: Kirigami.Units.gridUnit
        topPadding: Kirigami.Units.gridUnit
        bottomPadding: Kirigami.Units.gridUnit

        ColumnLayout {
            spacing: Kirigami.Units.smallSpacing
            Controls.Label {
                Layout.fillWidth: true
                text: tr("Discard unsaved changes and reload?", "未保存的修改将被丢弃，确定重新加载吗？")
                wrapMode: Text.WordWrap
            }
            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                Controls.Button {
                    text: tr("Cancel", "取消")
                    onClicked: discardDialog.close()
                }
                Controls.Button {
                    text: tr("Discard and Reload", "放弃并重载")
                    highlighted: true
                    onClicked: {
                        discardDialog.close()
                        loadConfig()
                    }
                }
            }
        }
    }
}
