// qmllint stub for org.kde.plasma.workspace.osd (CI only). See OsdWindow.qml.
//
// Mirrors the public properties of plasma-workspace's OsdItem.qml so that the
// applet can be linted without installing plasma-workspace.
import QtQuick

Item {
    // OSD timeout in msecs - how long it stays on screen.
    property int timeout: 1800
    // Text, or a number when showingProgress is true.
    property var osdValue
    // Maximum percent value.
    property int osdMaxValue: 100
    // Additional text shown together with progress.
    property string osdAdditionalText: ""
    // Icon name to display.
    property string icon: ""
    // true renders osdValue as a progress bar instead of text.
    property bool showingProgress: false
}
