import QtQuick 2.12
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Rectangle {
    anchors.fill: parent
    color: "grey"

    ListView {
        id: streamlist
        anchors.fill: parent
        spacing: 1
        model: MyModel
        anchors.margins: 1
        delegate:
            Rectangle {
                id: delegateRoot
                color: "lightgrey"
                width: parent ? parent.width : 0
                height: 80
                property int activityFlashNonce: model.activityFlashNonce
                onActivityFlashNonceChanged: { if (activityFlashNonce > 0) activityLed.triggerFlash() }
                GridLayout {
                    anchors.margins: 2
                    clip: true
                    anchors.fill: parent
                    columns: 3
                    rows: 3
                    Text {
                        text: '<b>Name:</b> ' + name
                        Layout.row: 0; Layout.column: 0
                    }
                    Text {
                        text: '<b>Type:</b> ' + type
                        Layout.row: 0; Layout.column: 1
                    }
                    Row {
                        id: statusRow
                        Layout.row: 0; Layout.column: 2
                        spacing: 5
                        Rectangle {
                            id: activityLed
                            width: 16
                            height: 16
                            radius: 8
                            border.width: 1
                            border.color: "#888"
                            property bool flashOn: false
                            property color idleColor: {
                                if (activityState === 'active') return '#00ff00'
                                if (activityState === 'warning') return '#ffaa00'
                                if (activityState === 'critical') return '#ff0000'
                                return 'gray'
                            }
                            color: flashOn ? 'lime' : idleColor
                            function triggerFlash() {
                                flashOn = true
                                flashTimer.restart()
                            }
                            Timer {
                                id: flashTimer
                                interval: 120
                                repeat: false
                                onTriggered: activityLed.flashOn = false
                            }
                        }
                        CheckBox {
                            id: notifyCheckbox
                            checked: notifyEnabled
                            onCheckedChanged: {
                                OuterWidget.setNotifyEnabled(index, checked)
                            }
                        }
                    }
                    Text {
                        text: '<b>Host:</b> ' + hostname
                        Layout.row: 1; Layout.column: 0
                    }
                    Text {
                        text: '<b>Channels:</b> ' + channel_count + " (" + channel_format + ")"
                        Layout.row: 1; Layout.column: 1
                    }
                    Text {
                        text: '<b>Nom.Rate:</b> ' + nominal_srate
                        Layout.row: 2; Layout.column: 0
                    }
                    Text {
                        text: '<b>Eff.Rate:</b> ' + effective_rate
                        Layout.row: 2; Layout.column: 1
                    }
//                    Text {
//                        text: uid; elide: Text.ElideRight; Layout.preferredWidth: 150
//                        Layout.row: 2; Layout.column: 2
//                    }
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: streamlist.currentIndex = index
                    onDoubleClicked: OuterWidget.activated(index)  // console.warn("Double clicked " + index)
                }
                MouseArea {
                    x: activityLed.mapToItem(delegateRoot, 0, 0).x
                    y: activityLed.mapToItem(delegateRoot, 0, 0).y
                    width: activityLed.width
                    height: activityLed.height
                    z: 1
                    hoverEnabled: true
                    acceptedButtons: Qt.NoButton
                    ToolTip.text: streamLastReceived
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 400
                }
                ListView.onAdd: {
                    OuterWidget.added(index)
                }
                ListView.onRemove: {
                    OuterWidget.removed()
                }
            }
        ScrollIndicator.vertical: ScrollIndicator { }
//        onCountChanged: console.warn('Model count has changed: ' + count)
//        onCurrentItemChanged: console.warn(streamlist.currentIndex + ' selected')
    }

    Button {
        width: 40
        height: 20
        anchors.bottom: parent.bottom
        anchors.right: parent.right
        Text {
            font.pointSize: 8
            text: "refresh"
            anchors.verticalCenter: parent.verticalCenter
        }
        onClicked: {
            MyModel.refresh();
        }
    }
}
