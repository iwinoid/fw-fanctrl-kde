import QtQuick
import org.kde.plasma.configuration

ConfigModel {
    id: configModel
    readonly property bool isChinese: Qt.locale().name.startsWith("zh")
    function tr(en, zh) {
        return isChinese ? zh : en;
    }

    ConfigCategory {
        name: configModel.tr("Fan Curves", "风扇曲线")
        icon: "computer-fan"
        source: "configCurves.qml"
    }
}
