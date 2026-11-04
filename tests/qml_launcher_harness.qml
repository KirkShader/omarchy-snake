// Offscreen host for tests/test_marketplace_plugin.py: loads the real BarWidget.qml the way
// shell.qml does, sends it real pointer/key events, and prints what happened. It never talks
// to the running shell; the test copies this file to scratch and runs it with an isolated env.
import QtQuick
import QtTest
import Quickshell

ShellRoot {
    id: harness

    readonly property string pluginDir: Quickshell.env("HARNESS_PLUGIN_DIR")
    readonly property string action: Quickshell.env("HARNESS_ACTION")
    readonly property string screenshotPath: Quickshell.env("HARNESS_SCREENSHOT") || ""
    readonly property bool useSlotPointer: action !== "click-direct" && action !== "click-no-bar"
    property var widget: null
    property var tooltips: []
    property int tooltipHides: 0
    property var barRuns: []
    property var result: ({ action: action })

    // Same surface as the third-party facade in Ui/PluginBarApi.qml.
    QtObject {
        id: mockBar
        property color foreground: "#eeeeee"
        property color barForeground: "#eeeeee"
        property color background: "#101010"
        property color urgent: "#ff3333"
        property string fontFamily: "monospace"
        property string position: "top"
        property bool vertical: false
        property int barSize: 26
        function showTooltip(target, text) {
            harness.tooltips = harness.tooltips.concat([{ text: text, hovered: target.tooltipHovered === true }])
        }
        function hideTooltip(target) { harness.tooltipHides += 1 }
        function run(command) { harness.barRuns = harness.barRuns.concat([String(command)]) }
    }

    function fileUrl(path) { // Commons/Util.qml fileUrl()
        return "file://" + String(path).split("/").map(encodeURIComponent).join("/")
    }

    function child(item, name) {
        if (item.objectName === name) return item
        for (var i = 0; i < item.children.length; i++) {
            var found = child(item.children[i], name)
            if (found) return found
        }
        return null
    }

    // Plugin bars inject after loading, with Qt.callLater (Bar.qml injectProps()).
    function inject(target) {
        if (action === "click-no-bar") return
        if ("bar" in target) target.bar = mockBar
        if ("moduleName" in target) target.moduleName = "io.github.kirkshader.omarchy-snake"
        if ("settings" in target) target.settings = ({})
    }

    function load() {
        var component = Qt.createComponent(fileUrl(pluginDir + "/BarWidget.qml"), Component.Asynchronous)
        function finalize() {
            if (component.status === Component.Loading) return
            if (component.status !== Component.Ready) {
                result.loadError = component.errorString()
                finish()
                return
            }
            widget = component.createObject(widgetHost)
            Qt.callLater(function() {
                inject(widget)
                actionTimer.start()
            })
        }
        if (component.status === Component.Loading) component.statusChanged.connect(finalize)
        else finalize()
    }

    function act() {
        var x = widget.width / 2
        var y = widget.height / 2
        var icon = child(widget, "icon")
        result.width = widget.width
        result.height = widget.height
        result.iconStatusReady = !!icon && icon.status === Image.Ready
        result.iconWidth = icon ? icon.width : -1
        result.iconHeight = icon ? icon.height : -1

        if (action === "click-slot" || action === "click-direct" || action === "click-no-bar") {
            events.mouseClick(widget, x, y, Qt.LeftButton, Qt.NoModifier, -1)
        } else if (action === "click-right") {
            events.mouseClick(widget, x, y, Qt.RightButton, Qt.NoModifier, -1)
        } else if (action === "press-right") {
            widget.triggerPress(Qt.RightButton) // a host forwarding another button, as WidgetButton does
        } else if (action === "hover") {
            events.mouseMove(widget, x, y, -1, Qt.NoButton, Qt.NoModifier)
            result.hoveredWhileInside = widget.tooltipHovered === true
            events.mouseMove(widget, -20, -20, -1, Qt.NoButton, Qt.NoModifier)
            result.hoveredAfterLeaving = widget.tooltipHovered === true
        } else if (action.indexOf("key-") === 0) {
            var keys = { "key-return": Qt.Key_Return, "key-enter": Qt.Key_Enter,
                         "key-space": Qt.Key_Space, "key-x": Qt.Key_X }
            var indicator = child(widget, "focusIndicator")
            result.indicatorBeforeFocus = !!indicator && indicator.visible
            widget.forceActiveFocus()
            result.activeFocus = widget.activeFocus
            result.focusOnTab = widget.activeFocusOnTab
            result.indicatorWithFocus = !!indicator && indicator.visible
            events.keyClick(keys[action], Qt.NoModifier, -1)
        }
        settleTimer.start()
    }

    function finish() {
        result.tooltips = tooltips
        result.tooltipHides = tooltipHides
        result.barRuns = barRuns
        console.log("HARNESS_RESULT " + JSON.stringify(result))
        Qt.quit()
    }

    function settled() {
        if (!screenshotPath) {
            finish()
            return
        }
        widgetHost.grabToImage(function(image) {
            result.screenshotSaved = image.saveToFile(screenshotPath)
            finish()
        }, Qt.size(widgetHost.width * 4, widgetHost.height * 4))
    }

    FloatingWindow {
        id: window
        visible: true
        implicitWidth: 80
        implicitHeight: 80
        color: "#101010"

        Item {
            id: slot
            x: 20
            y: 20
            width: harness.widget ? harness.widget.implicitWidth : 0
            height: harness.widget ? harness.widget.implicitHeight : 0

            Item {
                id: widgetHost
                anchors.fill: parent
            }

            // The relevant handlers of Bar.qml's modulePointer, which sits over every widget.
            MouseArea {
                anchors.fill: parent
                acceptedButtons: Qt.LeftButton
                enabled: harness.useSlotPointer
                propagateComposedEvents: true
                onReleased: function(mouse) { mouse.accepted = false }
                onClicked: function(mouse) {
                    var target = harness.widget
                    if (target && typeof target.triggerPress === "function") target.triggerPress(mouse.button)
                    else mouse.accepted = false
                }
            }

            TestEvent { id: events }
        }
    }

    Timer {
        id: actionTimer
        interval: 150
        onTriggered: harness.act()
    }

    Timer {
        id: settleTimer
        interval: 500
        onTriggered: harness.settled()
    }

    Component.onCompleted: load()
}
