import QtQuick
import org.kde.plasma.configuration

ConfigModel {
    readonly property bool isChinese: Qt.locale().name.startsWith("zh")
    function tr(en, zh) { return isChinese ? zh : en }

    ConfigCategory {
        name: tr("Fan Curves", "风扇曲线")
        icon: "computer-fan"
        source: "configCurves.qml"
    }
}
