pragma ComponentBehavior: Bound
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
    // -1 means "not reported by fw-fanctrl"; 0 is a valid temperature.
    property real m_temperature: -1
    property int m_fanSpeed: 0
    property string m_lastMessage: ""
    property bool m_lastSuccess: true
    property bool m_busy: false
    property bool m_statusPending: false
    property string m_pendingStrategy: ""
    property int m_offlineStreak: 0
    property bool m_offlineNotified: false

    readonly property bool isChinese: Qt.locale().name.startsWith("zh")
    function tr(en, zh) {
        return isChinese ? zh : en;
    }

    // Emitted when the service has been offline for several consecutive
    // polls; at most once per offline episode (see trackOffline()).
    signal serviceOfflineNotice(string reason)

    // Emitted when a strategy change was not applied: either the backend
    // refused it (offline / another command in flight) or the helper reported
    // a failure. The UI uses this to put the slider back on the real strategy.
    signal strategyRejected(string name)

    // Emitted after every finished status poll (online and offline), so the
    // applet can apply a configuration staged by the configuration dialog
    // without running its own timer.
    signal statusPolled()

    readonly property string helperScript: decodeURIComponent(Qt.resolvedUrl("../../scripts/fw_helper.py").toString().replace("file://", ""))

    // ─── Command construction ─────────────────────────────────────
    function shellQuote(arg) {
        return "'" + arg.replace(/'/g, "'\\''") + "'";
    }

    function commandFromSource(sourceName) {
        var prefix = shellQuote(helperScript) + " ";
        if (sourceName.indexOf(prefix) !== 0)
            return "";
        var rest = sourceName.substring(prefix.length).trim();
        var space = rest.indexOf(" ");
        return space < 0 ? rest : rest.substring(0, space);
    }

    function commandLine(cmd, arg) {
        var line = shellQuote(helperScript) + " " + cmd;
        if (arg !== undefined && arg !== "")
            line += " " + arg;
        return line;
    }

    // Returns false when the command was dropped because another one is still
    // in flight; callers that need to know must look at the return value
    // instead of relying on silence.
    function execCommand(cmd, arg) {
        if (cmd === "get_status") {
            if (m_statusPending)
                return false;
            m_statusPending = true;
        } else {
            if (m_busy)
                return false;
            m_busy = true;
        }

        executor.connectSource(commandLine(cmd, arg));
        return true;
    }

    // ─── Executable DataSource ────────────────────────────────────
    DataSource {
        id: executor
        engine: "executable"
        connectedSources: []

        onNewData: function (sourceName, data) {
            var stdout = (data["stdout"] || "").trim();
            var stderr = (data["stderr"] || "").trim();
            var exitCode = data["exit code"] !== undefined ? data["exit code"] : -1;
            var command = root.commandFromSource(sourceName);

            disconnectSource(sourceName);

            if (command === "get_status")
                root.handleStatus(stdout, stderr, exitCode);
            else if (command === "notify") {} // fire-and-forget, result is ignored
            else
                root.handleResult(command, stdout, stderr, exitCode);
        }
    }

    // ─── Response Handlers ────────────────────────────────────────
    function parseJSON(text) {
        try {
            return JSON.parse(text);
        } catch (e) {
            return null;
        }
    }

    function handleStatus(stdout, stderr, exitCode) {
        m_statusPending = false;
        var data = parseJSON(stdout);
        if (!data || data.error) {
            // Never surface raw helper/CLI stderr (it can be a shell error or a
            // JSON blob): keep the detail in the journal, show a stable text.
            if (data && data.error)
                console.warn("fw-fanctrl status error:", data.error);
            else if (stderr)
                console.warn("fw-fanctrl status stderr:", stderr);
            setOffline();
            trackOffline();
            statusPolled();
            return;
        }

        m_online = data.online === true;

        if (m_online) {
            m_active = data.active === true;
            if (data.currentStrategy !== undefined && data.currentStrategy !== null)
                m_currentStrategy = String(data.currentStrategy);
            // A missing temperature must not be shown as 0.0°C; null is also
            // what the helper sends when fw-fanctrl does not report it.
            m_temperature = typeof data.temperature === "number" ? data.temperature : -1;
            m_fanSpeed = typeof data.fanSpeed === "number" ? data.fanSpeed : 0;
            if (data.strategies !== undefined && JSON.stringify(data.strategies) !== JSON.stringify(m_strategies))
                m_strategies = data.strategies;
        } else {
            m_active = false;
            m_currentStrategy = "";
            m_strategies = [];
            m_temperature = -1;
            m_fanSpeed = 0;
        }

        trackOffline();
        statusPolled();
    }

    // Offline detection: notify only after 3 consecutive failed polls (~6s),
    // and only once per offline episode.
    function trackOffline() {
        if (m_online) {
            m_offlineStreak = 0;
            m_offlineNotified = false;
        } else {
            m_offlineStreak++;
            // Notify once per offline episode: a missing fw-fanctrl must not
            // keep popping critical notifications every minute.
            if (m_offlineStreak >= 3 && !m_offlineNotified) {
                m_offlineNotified = true;
                serviceOfflineNotice(m_lastMessage || tr("fw-fanctrl unavailable", "fw-fanctrl 不可用"));
            }
        }
    }

    function handleResult(command, stdout, stderr, exitCode) {
        m_busy = false;

        var data = parseJSON(stdout);
        if (data) {
            m_lastSuccess = data.success === true;
            m_lastMessage = data.message || (data.success ? "OK" : "Error");
        } else {
            m_lastSuccess = exitCode === 0;
            m_lastMessage = m_lastSuccess ? (stdout || "OK") : (stderr || "Command failed");
        }

        if (command === "set_strategy" && m_pendingStrategy !== "") {
            // The pending name is only set when the command was accepted, so
            // report exactly that strategy and clear it either way.
            const requested = m_pendingStrategy;
            m_pendingStrategy = "";
            if (m_lastSuccess)
                strategyApplied(requested);
            else
                strategyRejected(requested);
        }

        if (m_lastSuccess)
            refresh();
    }

    function setOffline() {
        m_online = false;
        m_active = false;
        m_currentStrategy = "";
        m_strategies = [];
        m_temperature = -1;
        m_fanSpeed = 0;

        m_lastSuccess = false;
        m_lastMessage = tr("fw-fanctrl is unavailable", "fw-fanctrl 不可用");
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
        execCommand("get_status");
    }

    // Returns true when the command was accepted. Refused or failed strategy
    // changes emit strategyRejected() so the UI can roll back instead of
    // showing a strategy that was never applied.
    function useStrategy(name) {
        if (!name)
            return false;
        if (!m_online || m_busy) {
            strategyRejected(name);
            return false;
        }
        m_pendingStrategy = name;
        if (!execCommand("set_strategy", shellQuote(name))) {
            m_pendingStrategy = "";
            strategyRejected(name);
            return false;
        }
        return true;
    }

    // Applies a configuration JSON staged by the configuration dialog.
    // Returns true when the command was accepted; false means another command
    // is in flight and the caller must keep the pending value for a retry.
    function saveConfig(jsonText) {
        if (!jsonText)
            return false;
        return execCommand("save_config", shellQuote(jsonText));
    }

    function reload() {
        execCommand("reload");
    }
    function pause() {
        execCommand("pause");
    }
    function resume() {
        execCommand("resume");
    }

    // Fire-and-forget desktop notification; does not touch busy/status state.
    function notify(title, body) {
        executor.connectSource(commandLine("notify", shellQuote(title) + " " + shellQuote(body)));
    }

    // ─── Init ─────────────────────────────────────────────────────
    Component.onCompleted: {
        pollTimer.start();
        refresh();
    }
}
