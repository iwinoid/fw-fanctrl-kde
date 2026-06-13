import QtQuick
import org.kde.plasma.plasmoid
import org.kde.plasma.plasma5support

/**
 * Backend for fw-fanctrl plasmoid (Plasma 6).
 * Uses plasma5support.DataSource (executable engine) to run fw_helper.py,
 * which in turn calls fw-fanctrl CLI via subprocess (same approach as the original Python tray app).
 */
Item {
    id: root

    // ─── Public Properties ────────────────────────────────────────
    readonly property bool online: m_online
    readonly property string currentStrategy: m_currentStrategy
    readonly property var strategies: m_strategies
    readonly property real temperature: m_temperature
    readonly property int fanSpeed: m_fanSpeed
    readonly property string lastMessage: m_lastMessage
    readonly property bool lastSuccess: m_lastSuccess
    readonly property bool busy: m_busy

    property int pollInterval: 2000

    // ─── Private State ────────────────────────────────────────────
    property bool m_online: false
    property string m_currentStrategy: ""
    property var m_strategies: []
    property real m_temperature: 0
    property int m_fanSpeed: 0
    property string m_lastMessage: ""
    property bool m_lastSuccess: true
    property bool m_busy: false
    property var pendingResolve: null

    readonly property string helperScript: Qt.resolvedUrl("../../scripts/fw_helper.py").toString().replace("file://", "")

    // ─── Executable DataSource (Plasma 5 compat layer, works in KF6) ──
    DataSource {
        id: executor
        engine: "executable"
        connectedSources: []

        function exec(cmd) {
            if (m_busy && cmd.indexOf("get_status") < 0) return
            if (cmd.indexOf("get_status") < 0) {
                m_busy = true
                busyChanged()
            }
            connectSource(cmd)
        }

        onNewData: function(sourceName, data) {
            var stdout = (data["stdout"] || "").trim()
            var stderr = (data["stderr"] || "").trim()
            var exitCode = data["exit code"] || -1

            disconnectSource(sourceName)

            if (sourceName.indexOf("get_status") > -1) {
                handleStatus(stdout, stderr, exitCode)
            } else if (sourceName.indexOf("get_config") > -1) {
                handleConfig(stdout, stderr, exitCode)
            } else if (sourceName.indexOf("save_config") > -1) {
                handleResult(stdout, stderr, exitCode)
            } else {
                handleResult(stdout, stderr, exitCode)
            }
        }
    }

    // ─── Response Handlers ────────────────────────────────────────
    function parseJSON(text) {
        try { return JSON.parse(text) }
        catch(e) { return null }
    }

    function handleStatus(stdout, stderr, exitCode) {
        var data = parseJSON(stdout)
        if (!data || data.error) {
            setOffline(data ? data.error : stderr)
            pollTimer.restart()
            return
        }

        var wasOnline = m_online
        m_online = data.online === true

        if (m_online) {
            if (data.currentStrategy !== undefined && data.currentStrategy !== m_currentStrategy) {
                m_currentStrategy = data.currentStrategy
                currentStrategyChanged()
            }
            if (data.temperature !== undefined) {
                m_temperature = data.temperature
                temperatureChanged()
            }
            if (data.fanSpeed !== undefined) {
                m_fanSpeed = data.fanSpeed
                fanSpeedChanged()
            }
            if (data.strategies !== undefined) {
                var newStrats = data.strategies
                if (JSON.stringify(newStrats) !== JSON.stringify(m_strategies)) {
                    m_strategies = newStrats
                    strategiesChanged()
                }
            }
        } else {
            if (m_currentStrategy !== "" || m_strategies.length > 0) {
                m_currentStrategy = ""
                m_strategies = []
                m_temperature = 0
                m_fanSpeed = 0
                currentStrategyChanged()
                strategiesChanged()
                temperatureChanged()
                fanSpeedChanged()
            }
        }

        if (wasOnline !== m_online) onlineChanged()
        pollTimer.restart()
    }

    function handleResult(stdout, stderr, exitCode) {
        m_busy = false
        busyChanged()
        var data = parseJSON(stdout)
        if (data) {
            m_lastSuccess = data.success === true
            m_lastMessage = data.message || (data.success ? "OK" : "Error")
        } else {
            m_lastSuccess = exitCode === 0
            m_lastMessage = m_lastSuccess ? (stdout || "OK") : (stderr || "Command failed")
        }
        lastMessageChanged()
        lastSuccessChanged()
        commandFinished()

        if (m_lastSuccess) refresh()
    }

    function handleConfig(stdout, stderr, exitCode) {
        m_busy = false
        busyChanged()
        var data = parseJSON(stdout)
        if (data && data.config) {
            configLoaded(data.config, data.schema || {})
        } else {
            m_lastSuccess = false
            m_lastMessage = data ? (data.error || "Config error") : (stderr || "No output")
            lastMessageChanged()
            lastSuccessChanged()
        }
    }

    function setOffline(reason) {
        var wasOnline = m_online
        m_online = false
        if (m_currentStrategy !== "" || m_strategies.length > 0) {
            m_currentStrategy = ""
            m_strategies = []
            currentStrategyChanged()
            strategiesChanged()
        }
        if (wasOnline) onlineChanged()
        if (reason) {
            m_lastSuccess = false
            m_lastMessage = reason
            lastMessageChanged()
            lastSuccessChanged()
        }
    }

    // ─── Signals ──────────────────────────────────────────────────
    signal commandFinished()
    signal configLoaded(var config, var schema)

    // ─── Polling Timer ────────────────────────────────────────────
    Timer {
        id: pollTimer
        interval: root.pollInterval
        onTriggered: { executor.exec(helperScript + " get_status") }
    }

    // ─── Public Methods ───────────────────────────────────────────
    function refresh() {
        executor.exec(helperScript + " get_status")
    }

    function useStrategy(name) {
        if (!name) return
        executor.exec(helperScript + " set_strategy " + name)
    }

    function reload() { executor.exec(helperScript + " reload")  }
    function pause()  { executor.exec(helperScript + " pause")   }
    function resume() { executor.exec(helperScript + " resume")  }

    function loadConfig() {
        executor.exec(helperScript + " get_config")
    }

    function saveConfig(jsonString) {
        executor.exec(helperScript + " save_config '" + jsonString.replace(/'/g, "'\\''") + "'")
    }

    // ─── Init ─────────────────────────────────────────────────────
    Component.onCompleted: {
        executor.exec(helperScript + " get_status")
    }
}
