import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.components as PlasmaComponents3
import org.kde.kirigami as Kirigami

/**
 * Main Plasmoid UI for Fan Control.
 * Supports Chinese (zh_CN) and English languages.
 */
PlasmoidItem {
    id: root

    // ─── Translations ─────────────────────────────────────────────
    readonly property bool isChinese: Qt.locale().name.startsWith("zh")

    function tr(en, zh) {
        return isChinese ? zh : en
    }

    // ─── Backend ──────────────────────────────────────────────────
    FwBackend {
        id: backend
    }

    // ─── Plasmoid Configuration ───────────────────────────────────
    readonly property string onlineIconPath: Qt.resolvedUrl("../images/64.png")
    readonly property string offlineIconPath: Qt.resolvedUrl("../images/offline.png")

    Plasmoid.icon: backend.online ? onlineIconPath : offlineIconPath
    Plasmoid.status: backend.online
        ? PlasmaCore.Types.ActiveStatus
        : PlasmaCore.Types.PassiveStatus

    toolTipItem: ColumnLayout {
        spacing: Kirigami.Units.smallSpacing

        Controls.Label {
            text: backend.online
                ? tr("Fan: %1", "风扇: %1").arg(backend.currentStrategy || tr("unknown", "未知"))
                : tr("Fan: offline", "风扇: 离线")
            font.bold: true
        }

        Controls.Label {
            text: backend.online
                ? tr("%1°C · %2%", "%1°C · %2%").arg(backend.temperature.toFixed(1)).arg(backend.fanSpeed)
                : ""
            opacity: 0.7
            visible: backend.online
        }
    }

    // ─── Compact Representation (System Tray) ─────────────────────
    compactRepresentation: MouseArea {
        id: compactArea
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton

        onClicked: root.expanded = !root.expanded

        Kirigami.Icon {
            anchors.fill: parent
            source: Plasmoid.icon
            active: compactArea.containsMouse
        }
    }

    // ─── Full Representation ──────────────────────────────────────
    fullRepresentation: ColumnLayout {
        id: mainLayout
        implicitWidth: Kirigami.Units.gridUnit * 22
        implicitHeight: Kirigami.Units.gridUnit * 22

        spacing: Kirigami.Units.smallSpacing

        // ── Strategy Slider (KDE OSD style) ───────────────────────
        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: Kirigami.Units.smallSpacing
            Layout.leftMargin: Kirigami.Units.smallSpacing
            Layout.rightMargin: Kirigami.Units.smallSpacing
            spacing: Kirigami.Units.gridUnit
            visible: backend.online && backend.strategies.length > 0

            Kirigami.Icon {
                Layout.leftMargin: Kirigami.Units.smallSpacing
                Layout.preferredWidth: Kirigami.Units.iconSizes.medium
                Layout.preferredHeight: Kirigami.Units.iconSizes.medium
                Layout.alignment: Qt.AlignTop
                source: "speedometer"
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.topMargin: Kirigami.Units.smallSpacing
                Layout.bottomMargin: Kirigami.Units.smallSpacing
                Layout.alignment: Qt.AlignVCenter
                spacing: Kirigami.Units.smallSpacing

                RowLayout {
                    Layout.fillWidth: true
                    Controls.Label {
                        text: tr("Fan Strategy", "风扇调度方案")
                    }
                    Item { Layout.fillWidth: true }
                    Controls.Label {
                        text: backend.currentStrategy || ""
                        font.bold: true
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.smallSpacing

                    Controls.Slider {
                        id: strategySlider
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        from: 0
                        to: backend.strategies.length - 1
                        stepSize: 1
                        snapMode: Controls.Slider.SnapAlways
                        enabled: backend.online && backend.strategies.length > 0
                        value: {
                            var idx = backend.strategies.indexOf(backend.currentStrategy)
                            return idx >= 0 ? idx : 0
                        }

                        onMoved: {
                            var idx = Math.round(value)
                            if (idx >= 0 && idx < backend.strategies.length) {
                                backend.useStrategy(backend.strategies[idx])
                            }
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.smallSpacing

                    Kirigami.Icon {
                        source: "battery-profile-powersave"
                        Layout.preferredWidth: Kirigami.Units.iconSizes.smallMedium
                        Layout.preferredHeight: Kirigami.Units.iconSizes.smallMedium
                        opacity: 0.8
                    }
                    Item { Layout.fillWidth: true }
                    Kirigami.Icon {
                        source: "battery-profile-performance"
                        Layout.preferredWidth: Kirigami.Units.iconSizes.smallMedium
                        Layout.preferredHeight: Kirigami.Units.iconSizes.smallMedium
                        opacity: 0.8
                    }
                }
            }
        }

        // ── Fan Speed Display (KDE ProgressBar style) ──────────────
        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: Kirigami.Units.largeSpacing
            Layout.leftMargin: Kirigami.Units.smallSpacing
            Layout.rightMargin: Kirigami.Units.smallSpacing
            spacing: Kirigami.Units.gridUnit
            visible: backend.online

            Kirigami.Icon {
                Layout.leftMargin: Kirigami.Units.smallSpacing
                Layout.preferredWidth: Kirigami.Units.iconSizes.medium
                Layout.preferredHeight: Kirigami.Units.iconSizes.medium
                Layout.alignment: Qt.AlignTop
                source: onlineIconPath
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.topMargin: Kirigami.Units.smallSpacing
                Layout.bottomMargin: Kirigami.Units.smallSpacing
                Layout.alignment: Qt.AlignVCenter
                spacing: Kirigami.Units.smallSpacing

                RowLayout {
                    Layout.fillWidth: true
                    Controls.Label {
                        text: tr("Fan Speed", "风扇功率")
                    }
                    Item { Layout.fillWidth: true }
                    Controls.Label {
                        text: tr("%1%", "%1%").arg(backend.fanSpeed)
                        font.bold: true
                    }
                }

                PlasmaComponents3.ProgressBar {
                    id: fanSpeedBar
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    from: 0
                    to: 100
                    value: backend.fanSpeed
                }

                RowLayout {
                    Layout.fillWidth: true
                    Controls.Label {
                        text: tr("Temperature", "温度")
                        font.pointSize: Kirigami.Theme.smallFont.pointSize
                        opacity: 0.7
                    }
                    Item { Layout.fillWidth: true }
                    Controls.Label {
                        text: tr("%1°C", "%1°C").arg(backend.temperature.toFixed(1))
                        font.pointSize: Kirigami.Theme.smallFont.pointSize
                        opacity: 0.7
                    }
                }
            }
        }

        // ── Action Buttons (KDE OSD style) ──────────────────────────
        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: Kirigami.Units.largeSpacing
            Layout.leftMargin: Kirigami.Units.smallSpacing
            Layout.rightMargin: Kirigami.Units.smallSpacing
            spacing: Kirigami.Units.gridUnit

            Kirigami.Icon {
                Layout.leftMargin: Kirigami.Units.smallSpacing
                Layout.preferredWidth: Kirigami.Units.iconSizes.medium
                Layout.preferredHeight: Kirigami.Units.iconSizes.medium
                Layout.alignment: Qt.AlignTop
                source: "configure"
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.topMargin: Kirigami.Units.smallSpacing
                Layout.bottomMargin: Kirigami.Units.smallSpacing
                Layout.alignment: Qt.AlignVCenter
                spacing: Kirigami.Units.smallSpacing

                RowLayout {
                    Layout.fillWidth: true
                    Controls.Label {
                        text: tr("Service Control", "服务状态管理")
                    }
                    Item { Layout.fillWidth: true }
                    Rectangle {
                        width: Kirigami.Units.smallSpacing
                        height: Kirigami.Units.smallSpacing
                        radius: width / 2
                        color: backend.online ? Kirigami.Theme.positiveTextColor : Kirigami.Theme.negativeTextColor
                        SequentialAnimation on color {
                            running: !backend.online
                            loops: Animation.Infinite
                            ColorAnimation {
                                from: Kirigami.Theme.negativeTextColor
                                to: Kirigami.Theme.disabledTextColor
                                duration: 1000
                            }
                            ColorAnimation {
                                from: Kirigami.Theme.disabledTextColor
                                to: Kirigami.Theme.negativeTextColor
                                duration: 1000
                            }
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.smallSpacing

                    PlasmaComponents3.Button {
                        text: tr("Reload", "重载")
                        icon.name: "view-refresh"
                        enabled: backend.online && !backend.busy
                        onClicked: backend.reload()
                    }

                    PlasmaComponents3.Button {
                        text: tr("Pause", "暂停")
                        icon.name: "media-playback-pause"
                        enabled: backend.online && !backend.busy
                        onClicked: backend.pause()
                    }

                    PlasmaComponents3.Button {
                        text: tr("Resume", "恢复")
                        icon.name: "media-playback-start"
                        enabled: backend.online && !backend.busy
                        onClicked: backend.resume()
                    }

                    PlasmaComponents3.Button {
                        text: tr("Refresh", "刷新")
                        icon.name: "view-refresh"
                        enabled: !backend.busy
                        onClicked: backend.refresh()
                    }
                }
            }
        }

        // ── Service Status (only when offline) ────────────────────
        Controls.Label {
            Layout.fillWidth: true
            Layout.leftMargin: Kirigami.Units.smallSpacing
            Layout.rightMargin: Kirigami.Units.smallSpacing
            text: backend.online ? "" : tr("● fw-fanctrl unavailable", "● fw-fanctrl 不可用")
            visible: !backend.online
            wrapMode: Text.WordWrap
            color: Kirigami.Theme.negativeTextColor
            font.pointSize: Kirigami.Theme.smallFont.pointSize
        }

        // ── Status Message ────────────────────────────────────────
        Controls.Label {
            id: statusMsg
            Layout.fillWidth: true
            Layout.leftMargin: Kirigami.Units.smallSpacing
            Layout.rightMargin: Kirigami.Units.smallSpacing
            Layout.bottomMargin: Kirigami.Units.smallSpacing
            text: backend.lastMessage
            visible: backend.lastMessage.length > 0
            wrapMode: Text.WordWrap
            font.pointSize: Kirigami.Theme.smallFont.pointSize
            color: backend.lastSuccess ? Kirigami.Theme.positiveTextColor : Kirigami.Theme.negativeTextColor
            opacity: visible ? 1.0 : 0.0
            Behavior on opacity { NumberAnimation { duration: 200 } }

            Timer {
                id: msgTimer
                interval: 4000
                onTriggered: {
                    statusMsg.text = ""
                    statusMsg.visible = false
                }
            }
        }

        // ── Loading Indicator ─────────────────────────────────────
        PlasmaComponents3.BusyIndicator {
            Layout.alignment: Qt.AlignCenter
            Layout.preferredHeight: Kirigami.Units.iconSizes.medium
            Layout.preferredWidth: Kirigami.Units.iconSizes.medium
            running: backend.busy
            visible: backend.busy
        }

        // ── Spacer ────────────────────────────────────────────────
        Item {
            Layout.fillHeight: true
        }
    }

    // ─── Preferences opens configCurves via right-click → Configure
    // (Plasma auto-discovers contents/ui/config*.qml + contents/config/main.xml)
}
