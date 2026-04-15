import sys
from typing import Callable, Optional

from qtpy import QtCore, QtGui, QtWidgets


class TextStream(QtCore.QObject):
    text_written = QtCore.Signal(str, str)

    def __init__(self, original_stream, source: str = "stdout"):
        super().__init__()
        self._original_stream = original_stream
        self._source = source


    @property
    def source(self) -> str:
        return self._source


    def write(self, text):
        if text:
            try:
                self.text_written.emit(text, self._source)
            except Exception:
                if self._original_stream:
                    try:
                        self._original_stream.write(text)
                    except Exception:
                        pass
        return len(text) if text else 0


    def flush(self):
        if self._original_stream:
            self._original_stream.flush()


    def isatty(self):
        return False


    def readable(self):
        return False


    def writable(self):
        return True


    def seekable(self):
        return False


class ConsoleOutputWidget(QtWidgets.QWidget):
    def __init__(self, parent=None, capture_stdout: bool = True, capture_stderr: bool = True, text_callback: Optional[Callable[[str, str], None]] = None, max_lines: int = 10000):
        super().__init__(parent)
        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr
        self._stdout_stream: Optional[TextStream] = None
        self._stderr_stream: Optional[TextStream] = None
        self._capture_stdout = capture_stdout
        self._capture_stderr = capture_stderr
        self._text_callback = text_callback
        self._max_lines = max_lines
        self._auto_scroll = True
        self._setup_ui()
        self._setup_streams()


    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        toolbar = QtWidgets.QHBoxLayout()

        clear_btn = QtWidgets.QPushButton("Clear")
        clear_btn.clicked.connect(self.clear)
        toolbar.addWidget(clear_btn)

        auto_scroll_cb = QtWidgets.QCheckBox("Auto-scroll")
        auto_scroll_cb.setChecked(True)
        auto_scroll_cb.toggled.connect(self._on_auto_scroll_toggled)
        toolbar.addWidget(auto_scroll_cb)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        self._text_edit = QtWidgets.QPlainTextEdit(self)
        self._text_edit.setReadOnly(True)
        self._text_edit.setFont(QtWidgets.QApplication.font())
        self._text_edit.setLineWrapMode(QtWidgets.QPlainTextEdit.WidgetWidth)
        layout.addWidget(self._text_edit)


    def _setup_streams(self):
        if self._capture_stdout:
            self._stdout_stream = TextStream(self._original_stdout, source="stdout")
            self._stdout_stream.text_written.connect(self._on_text_written)
            sys.stdout = self._stdout_stream

        if self._capture_stderr:
            self._stderr_stream = TextStream(self._original_stderr, source="stderr")
            self._stderr_stream.text_written.connect(self._on_text_written)
            sys.stderr = self._stderr_stream


    def _on_text_written(self, text: str, source: str):
        self._append_text_internal(text, source)


    def _append_text_internal(self, text: str, source: str):
        if not text:
            return

        if self._text_callback is not None:
            try:
                self._text_callback(text, source)
            except Exception:
                pass

        if not hasattr(self, "_text_edit") or self._text_edit is None:
            if self._original_stdout:
                self._original_stdout.write(text)
            return

        try:
            self._text_edit.moveCursor(QtGui.QTextCursor.End)
            self._text_edit.insertPlainText(text)

            document = self._text_edit.document()
            if document.blockCount() > self._max_lines:
                cursor = QtGui.QTextCursor(document)
                cursor.movePosition(QtGui.QTextCursor.Start)
                cursor.movePosition(QtGui.QTextCursor.Down, QtGui.QTextCursor.MoveAnchor, document.blockCount() - self._max_lines)
                cursor.movePosition(QtGui.QTextCursor.StartOfBlock)
                cursor.movePosition(QtGui.QTextCursor.End, QtGui.QTextCursor.KeepAnchor)
                cursor.removeSelectedText()

            if self._auto_scroll:
                scrollbar = self._text_edit.verticalScrollBar()
                scrollbar.setValue(scrollbar.maximum())
        except Exception:
            if self._original_stdout:
                try:
                    self._original_stdout.write(text)
                except Exception:
                    pass


    def append_text(self, text: str, source: str = "manual"):
        self._append_text_internal(text, source)


    def set_capture(self, stdout: bool, stderr: bool):
        if stdout and not self._capture_stdout:
            self._stdout_stream = TextStream(self._original_stdout, source="stdout")
            self._stdout_stream.text_written.connect(self._on_text_written)
            sys.stdout = self._stdout_stream
            self._capture_stdout = True
        elif (not stdout) and self._capture_stdout:
            if sys.stdout is self._stdout_stream:
                sys.stdout = self._original_stdout
            self._stdout_stream = None
            self._capture_stdout = False

        if stderr and not self._capture_stderr:
            self._stderr_stream = TextStream(self._original_stderr, source="stderr")
            self._stderr_stream.text_written.connect(self._on_text_written)
            sys.stderr = self._stderr_stream
            self._capture_stderr = True
        elif (not stderr) and self._capture_stderr:
            if sys.stderr is self._stderr_stream:
                sys.stderr = self._original_stderr
            self._stderr_stream = None
            self._capture_stderr = False


    def set_text_callback(self, callback: Optional[Callable[[str, str], None]]):
        self._text_callback = callback


    def _on_auto_scroll_toggled(self, checked):
        self._auto_scroll = checked


    def clear(self):
        self._text_edit.clear()


    def restore_streams(self):
        if self._stdout_stream is not None and sys.stdout is self._stdout_stream:
            sys.stdout = self._original_stdout
        if self._stderr_stream is not None and sys.stderr is self._stderr_stream:
            sys.stderr = self._original_stderr


    def closeEvent(self, event):
        self.restore_streams()
        super().closeEvent(event)
