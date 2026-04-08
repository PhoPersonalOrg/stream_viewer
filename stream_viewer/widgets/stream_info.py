from pathlib import Path
import pandas as pd
import time
from qtpy import QtWidgets, QtCore, QtGui, QtQuick


class StreamInfoItemDelegate(QtWidgets.QStyledItemDelegate):

    def paint(self, painter: QtGui.QPainter, option: 'QStyleOptionViewItem', index: QtCore.QModelIndex) -> None:
        # super().paint(painter, option, index)
        if option.state & QtWidgets.QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
            painter.setPen(option.palette.highlightedText().color())
        else:
            painter.setPen(option.palette.text().color())
        # painter.setFont(QtGui.QFont("Arial", 10))
        painter.drawText(option.rect, QtCore.Qt.AlignLeft, index.data())


class StreamInfoListView(QtWidgets.QListView):
    stream_activated = QtCore.Signal(pd.Series)

    def __init__(self, model, **kwargs):
        super().__init__(**kwargs)
        self.setFont(QtGui.QFont("Helvetica", 8))
        self.setModel(model)
        # self.setItemDelegate(StreamInfoItemDelegate())
        self.doubleClicked.connect(self.on_doubleClicked)

    @QtCore.Slot(QtCore.QModelIndex)
    def on_doubleClicked(self, index: QtCore.QModelIndex):
        self.stream_activated.emit(index.data(QtCore.Qt.UserRole + 1))


class StreamStatusQMLWidget(QtWidgets.QWidget):
    """ a stream status indicator widget for a single stream that shows its info, connection status, and activity (via a little indicator light) 
    """
    stream_activated = QtCore.Signal(dict)
    stream_added = QtCore.Signal(dict)
    stream_removed = QtCore.Signal()

    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.model = model
        self.monitor_sources = {}
        self._alerted_streams = set()  # Track streams that have been alerted to prevent spam

        self.view = QtQuick.QQuickView()
        self.view.statusChanged.connect(self.on_statusChanged)  # Error handler
        self.view.setResizeMode(QtQuick.QQuickView.SizeRootObjectToView)
        engine = self.view.engine()
        context = engine.rootContext()
        context.setContextProperty("MyModel", self.model)
        context.setContextProperty("OuterWidget", self)
        qml_path = Path(__file__).parents[1] / 'qml' / 'streamInfoListView.qml'
        self.view.setSource(QtCore.QUrl.fromLocalFile(str(qml_path)))
        widget = QtWidgets.QWidget.createWindowContainer(self.view)

        self.setLayout(QtWidgets.QHBoxLayout())
        self.layout().addWidget(widget)
        
        # Monitor timer for checking stream activity
        self._monitor_timer = QtCore.QTimer()
        self._monitor_timer.timeout.connect(self._check_stream_activity)
        self._monitor_timer.start(1500)  # Check every 1.5 seconds

    @QtCore.Slot(QtQuick.QQuickView.Status)
    def on_statusChanged(self, status):
        if status == QtQuick.QQuickView.Error:
            for error in self.view.errors():
                print(error.toString())

    @QtCore.Slot(int)
    def activated(self, index):
        strm = self.model._data.iloc[index].to_dict()  # TODO: give self.model a non-private accessor.
        self.stream_activated.emit(strm)

    @QtCore.Slot(int)
    def added(self, index):
        strm = self.model._data.iloc[index].to_dict()  # TODO: give self.model a non-private accessor.
        self.stream_added.emit(strm)

    @QtCore.Slot()
    def removed(self):
        # TODO: How can we track _what_ was removed?
        self.stream_removed.emit()


    @QtCore.Slot(int)
    def printStreamInfo(self, index):
        if index < 0 or index >= len(self.model._data):
            return
        strm = self.model._data.iloc[index].to_dict()
        print('--- LSL stream info ---')
        for k, v in strm.items():
            print(f'  {k}: {v}')
        print('-----------------------')


    @QtCore.Slot(int)
    def openStreamConfig(self, index):
        if index < 0 or index >= len(self.model._data):
            return
        strm = self.model._data.iloc[index].to_dict()
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(f"Configure stream — {strm.get('name', index)}")
        form = QtWidgets.QFormLayout(dlg)
        col_names = getattr(self.model, 'col_names', None)
        shown = set()
        if col_names is not None:
            for key in col_names:
                if key in strm:
                    form.addRow(key, QtWidgets.QLabel(str(strm[key])))
                    shown.add(key)
        for key in sorted(strm.keys()):
            if key not in shown:
                form.addRow(key, QtWidgets.QLabel(str(strm[key])))
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok)
        bb.accepted.connect(dlg.accept)
        form.addRow(bb)
        dlg.exec_()


    def _check_stream_activity(self):
        """Check stream activity and show alerts if needed."""
        if not hasattr(self.model, '_stream_last_received'):
            return
        
        current_time = time.time()
        stream_last_received = self.model._stream_last_received
        
        # Update activity states in model (triggers QML update)
        # Emit dataChanged for all rows to update activity state display
        if len(self.model._data) > 0:
            top_left = self.model.index(0, 0)
            bottom_right = self.model.index(len(self.model._data) - 1, 0)
            self.model.dataChanged.emit(top_left, bottom_right, [self.model.ActivityStateRole])
        
        # Stall alerts for every listed stream that has received data at least once
        for _, row in self.model._data.iterrows():
            stream_key = (row['name'], row['type'], row['hostname'], row['uid'])
            if stream_key not in stream_last_received:
                continue
            last_received = stream_last_received[stream_key]
            time_since = current_time - last_received
            if time_since > 10.0:
                if stream_key not in self._alerted_streams:
                    msg = QtWidgets.QMessageBox()
                    msg.setIcon(QtWidgets.QMessageBox.Warning)
                    msg.setWindowTitle("Stream Data Alert")
                    msg.setText(f"Stream '{stream_key[0]}' ({stream_key[1]}) has not received data for {int(time_since)} seconds.")
                    msg.setInformativeText("The data stream may have stopped or the source may have disconnected.")
                    msg.exec_()
                    self._alerted_streams.add(stream_key)
            else:
                self._alerted_streams.discard(stream_key)
