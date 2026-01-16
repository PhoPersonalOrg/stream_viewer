#  Copyright (C) 2014-2021 Syntrogi Inc dba Intheon. All rights reserved.

import sys
import io
from qtpy import QtWidgets, QtCore


class TextStream(QtCore.QObject):
    """A thread-safe text stream that emits signals when text is written."""
    text_written = QtCore.Signal(str)

    def __init__(self, original_stream):
        super().__init__()
        self._original_stream = original_stream
        self._buffer = ""

    def write(self, text):
        """Write text and emit signal for UI update."""
        if text:
            self._buffer += text
            # Emit signal for thread-safe UI update
            try:
                self.text_written.emit(text)
            except Exception:
                # If signal emission fails, fallback to original stream
                if self._original_stream:
                    try:
                        self._original_stream.write(text)
                    except Exception:
                        pass
        return len(text) if text else 0

    def flush(self):
        """Flush the stream."""
        if self._original_stream:
            self._original_stream.flush()

    def isatty(self):
        """Check if this is a TTY."""
        return False

    def readable(self):
        """Check if stream is readable."""
        return False

    def writable(self):
        """Check if stream is writable."""
        return True

    def seekable(self):
        """Check if stream is seekable."""
        return False


class ConsoleOutputWidget(QtWidgets.QWidget):
    """Widget that displays stdout/stderr output in a scrollable text area."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr
        self._stdout_stream = None
        self._stderr_stream = None
        self._max_lines = 10000
        self._auto_scroll = True
        self._setup_ui()
        self._setup_streams()

    def _setup_ui(self):
        """Set up the user interface."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Toolbar with controls
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

        # Text display area
        self._text_edit = QtWidgets.QPlainTextEdit(self)
        self._text_edit.setReadOnly(True)
        self._text_edit.setFont(QtWidgets.QApplication.font())
        self._text_edit.setLineWrapMode(QtWidgets.QPlainTextEdit.WidgetWidth)
        layout.addWidget(self._text_edit)

    def _setup_streams(self):
        """Set up stdout/stderr redirection."""
        # Create stream wrappers
        self._stdout_stream = TextStream(self._original_stdout)
        self._stderr_stream = TextStream(self._original_stderr)

        # Connect signals to append method
        self._stdout_stream.text_written.connect(self._append_text)
        self._stderr_stream.text_written.connect(self._append_text)

        # Redirect stdout and stderr
        sys.stdout = self._stdout_stream
        sys.stderr = self._stderr_stream

    def _append_text(self, text):
        """Append text to the display (thread-safe)."""
        if not text:
            return

        # Safety check: ensure widget is ready
        if not hasattr(self, '_text_edit') or self._text_edit is None:
            # Fallback to original stream if widget not ready
            if self._original_stdout:
                self._original_stdout.write(text)
            return

        try:
            # Append text
            self._text_edit.moveCursor(QtWidgets.QTextCursor.End)
            self._text_edit.insertPlainText(text)

            # Limit buffer size
            document = self._text_edit.document()
            if document.blockCount() > self._max_lines:
                cursor = QtWidgets.QTextCursor(document)
                cursor.movePosition(QtWidgets.QTextCursor.Start)
                cursor.movePosition(QtWidgets.QTextCursor.Down, QtWidgets.QTextCursor.MoveAnchor, document.blockCount() - self._max_lines)
                cursor.movePosition(QtWidgets.QTextCursor.StartOfBlock)
                cursor.movePosition(QtWidgets.QTextCursor.End, QtWidgets.QTextCursor.KeepAnchor)
                cursor.removeSelectedText()

            # Auto-scroll if enabled
            if self._auto_scroll:
                scrollbar = self._text_edit.verticalScrollBar()
                scrollbar.setValue(scrollbar.maximum())
        except Exception:
            # If widget operations fail, fallback to original stream
            if self._original_stdout:
                try:
                    self._original_stdout.write(text)
                except Exception:
                    pass

    def _on_auto_scroll_toggled(self, checked):
        """Handle auto-scroll checkbox toggle."""
        self._auto_scroll = checked

    def clear(self):
        """Clear the text display."""
        self._text_edit.clear()

    def restore_streams(self):
        """Restore original stdout/stderr streams."""
        if sys.stdout is self._stdout_stream:
            sys.stdout = self._original_stdout
        if sys.stderr is self._stderr_stream:
            sys.stderr = self._original_stderr

    def closeEvent(self, event):
        """Handle widget close event."""
        self.restore_streams()
        super().closeEvent(event)
