// Omarchy bar launcher for the standalone GTK game in this checkout. It starts nothing until
// activated; grid_preview.py itself refocuses an already running game.
import QtQuick
import Quickshell

Item {
    id: root

    property var bar
    property string moduleName
    property var settings

    // Bar.qml shows its shared tooltip only while the target reports being hovered.
    readonly property bool tooltipHovered: pointer.containsMouse
    readonly property string tooltipText: "Omarchy Snake — play"

    implicitWidth: 28
    implicitHeight: bar && bar.barSize > 0 ? bar.barSize : 28
    activeFocusOnTab: true

    Accessible.role: Accessible.Button
    Accessible.name: tooltipText
    Accessible.onPressAction: launch()

    function localPath(url) {
        const text = String(url)
        if (!text.startsWith("file://")) throw new Error("Not a local file: " + text)
        return decodeURIComponent(text.slice("file://".length))
    }

    function launch() {
        if (bar) bar.hideTooltip(root)
        Quickshell.execDetached(["/usr/bin/python", localPath(Qt.resolvedUrl("grid_preview.py")), "--show-difficulty"])
    }

    // The bar's own pointer sits over every widget and delivers left clicks here.
    function triggerPress(button) {
        if (button === Qt.LeftButton) launch()
    }

    Keys.onPressed: function(event) {
        if (event.key !== Qt.Key_Return && event.key !== Qt.Key_Enter && event.key !== Qt.Key_Space) return
        event.accepted = true
        if (!event.isAutoRepeat) launch()
    }

    Rectangle {
        objectName: "focusIndicator"
        anchors.fill: parent
        anchors.margins: 1
        radius: 4
        color: "transparent"
        border.width: 1
        border.color: root.bar ? root.bar.foreground : "#87d96c"
        visible: root.activeFocus
    }

    Image {
        objectName: "icon"
        anchors.centerIn: parent
        width: 16
        height: 16
        source: Qt.resolvedUrl("omarchy-snake.svg")
        sourceSize.width: 40
        sourceSize.height: 40
        opacity: pointer.containsMouse ? 1.0 : 0.88
    }

    MouseArea {
        id: pointer
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onEntered: if (root.bar) root.bar.showTooltip(root, root.tooltipText)
        onExited: if (root.bar) root.bar.hideTooltip(root)
        onClicked: function(mouse) { root.triggerPress(mouse.button) }
    }
}
