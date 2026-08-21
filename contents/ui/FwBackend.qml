import QtQuick
import org.kde.plasma.plasma5support

/**
 * Backend for the fw-fanctrl plasmoid (Plasma 6).
 *
 * Uses plasma5support.DataSource with the executable engine to call
 * scripts/fw_helper.py.  The helper wraps fw-fanctrl and always returns JSON.
 */
Item {
    id: root

    // ─── Public Properties ────────────────────────────────────────
    readonly property bool online: m_online
    readonly property bool serviceActive: m_active
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
    property bool m_active: false
    property string m_currentStrategy: ""
    property var m_strategies: []
    property real m_temperature: 0
    property int m_fanSpeed: 0
    property string m_lastMessage: ""
    property bool m_lastSuccess: true
    property bool m_busy: false
    property bool m_statusPending: false
    property string m_pendingStrategy: ""
    property int m_offlineStreak: 0
    property int m_notifyCooldown: 0

    readonly property bool isChinese: Qt.locale().name.startsWith("zh")
    function tr(en, zh) { return isChinese ? zh : en }

    // Emitted when the service has been offline for several consecutive
    // polls and enough time has passed since the last notice (rate-limited).
    signal serviceOfflineNotice(string reason)

    readonly property string helperScript: decodeURIComponent(
        Qt.resolvedUrl("../../scripts/fw_helper.py").toString().replace("file://", "")
    )

    // ─── Command construction ─────────────────────────────────────
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

    function commandLine(cmd, arg) {
        var line = shellQuote(helperScript) + " " + cmd
        if (arg !== undefined && arg !== "")
            line += " " + arg
        return line
    }

    function execCommand(cmd, arg) {
        if (cmd === "get_status") {
            if (m_statusPending)
                return
            m_statusPending = true
        } else {
            if (m_busy)
                return
            m_busy = true
        }

        executor.connectSource(commandLine(cmd, arg))
    }

    // ─── Executable DataSource ────────────────────────────────────
    DataSource {
        id: executor
        engine: "executable"
        connectedSources: []

        onNewData: function(sourceName, data) {
            var stdout = (data["stdout"] || "").trim()
            var stderr = (data["stderr"] || "").trim()
            var exitCode = data["exit code"] !== undefined ? data["exit code"] : -1
            var command = root.commandFromSource(sourceName)

            disconnectSource(sourceName)

            if (command === "get_status")
                root.handleStatus(stdout, stderr, exitCode)
            else if (command === "notify")
                {} // fire-and-forget, result is ignored
            else
                root.handleResult(command, stdout, stderr, exitCode)
        }
    }

    // ─── Response Handlers ────────────────────────────────────────
    function parseJSON(text) {
        try { return JSON.parse(text) }
        catch (e) { return null }
    }

    function handleStatus(stdout, stderr, exitCode) {
        m_statusPending = false
        var data = parseJSON(stdout)
        if (!data || data.error) {
            setOffline(data ? data.error : stderr)
            trackOffline()
            return
        }

        m_online = data.online === true

        if (m_online) {
            m_active = data.active === true
            if (data.currentStrategy !== undefined)
                m_currentStrategy = data.currentStrategy
            if (data.temperature !== undefined)
                m_temperature = data.temperature
            if (data.fanSpeed !== undefined)
                m_fanSpeed = data.fanSpeed
            if (data.strategies !== undefined && JSON.stringify(data.strategies) !== JSON.stringify(m_strategies))
                m_strategies = data.strategies
        } else {
            m_active = false
            m_currentStrategy = ""
            m_strategies = []
            m_temperature = 0
            m_fanSpeed = 0
        }

        trackOffline()
    }

    // Offline detection: notify only after 3 consecutive failed polls
    // (~6s), and never more than once per 60s.
    function trackOffline() {
        if (m_online) {
            m_offlineStreak = 0
        } else {
            m_offlineStreak++
            if (m_offlineStreak >= 3 && m_notifyCooldown <= 0) {
                m_notifyCooldown = 30
                serviceOfflineNotice(m_lastMessage || tr("fw-fanctrl unavailable", "fw-fanctrl 不可用"))
            }
        }
        if (m_notifyCooldown > 0)
            m_notifyCooldown--
    }

    function handleResult(command, stdout, stderr, exitCode) {
        m_busy = false

        var data = parseJSON(stdout)
        if (data) {
            m_lastSuccess = data.success === true
            m_lastMessage = data.message || (data.success ? "OK" : "Error")
        } else {
            m_lastSuccess = exitCode === 0
            m_lastMessage = m_lastSuccess ? (stdout || "OK") : (stderr || "Command failed")
        }

        if (command === "set_strategy") {
            if (m_lastSuccess && m_pendingStrategy !== "")
                strategyApplied(m_pendingStrategy)
            m_pendingStrategy = ""
        }

        if (m_lastSuccess)
            refresh()
    }

    function setOffline(reason) {
        m_online = false
        m_active = false
        m_currentStrategy = ""
        m_strategies = []
        m_temperature = 0
        m_fanSpeed = 0

        if (reason) {
            m_lastSuccess = false
            m_lastMessage = reason
        }
    }

    signal strategyApplied(string name)

    // ─── Polling Timer ────────────────────────────────────────────
    // Repeating independently of command completion: one hung poll must not
    // stop all future polling.
    Timer {
        id: pollTimer
        interval: root.pollInterval
        repeat: true
        onTriggered: root.refresh()
    }

    // ─── Public Methods ───────────────────────────────────────────
    function refresh() {
        execCommand("get_status")
    }

    function useStrategy(name) {
        if (!name) return
        m_pendingStrategy = name
        execCommand("set_strategy", shellQuote(name))
    }

    function reload() { execCommand("reload") }
    function pause()  { execCommand("pause") }
    function resume() { execCommand("resume") }

    // Fire-and-forget desktop notification; does not touch busy/status state.
    function notify(title, body) {
        executor.connectSource(commandLine("notify", shellQuote(title) + " " + shellQuote(body)))
    }

    // ─── Init ─────────────────────────────────────────────────────
    Component.onCompleted: {
        pollTimer.start()
        refresh()
    }
}
