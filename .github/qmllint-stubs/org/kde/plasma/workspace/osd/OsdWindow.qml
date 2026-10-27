// qmllint stub for org.kde.plasma.workspace.osd (CI only).
//
// The real module lives in plasma-workspace, which is a very large package and
// is not installed in the CI container. Without it qmllint cannot resolve
// OsdWindow/OsdItem and emits cascading import/type warnings, which the old CI
// filtered away (and thereby hid real import errors too).
//
// This stub mirrors the API the applet uses. It is only read by qmllint
// (via `-I .github/qmllint-stubs`); it is never installed, packaged, or run.
import QtQuick

Window {
    // PlasmaQuick::PlasmaWindow (the base of the real OsdWindow) exposes the
    // item shown inside the window plus readonly paddings around it.
    property Item mainItem: null
    readonly property real topPadding: 0
    readonly property real bottomPadding: 0
    readonly property real leftPadding: 0
    readonly property real rightPadding: 0
}
