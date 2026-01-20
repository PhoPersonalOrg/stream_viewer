---
name: PhoPyQtHelper Package Creation
overview: Create a new standalone Qt widgets package `phopyqthelper` in ACTIVE_DEV, containing a generalized ConsoleOutputWidget with optional stdout/stderr capture and callback support, then update stream_viewer to use it as a dependency.
todos:
  - id: create-package
    content: Create phopyqthelper package structure with pyproject.toml and src layout
    status: completed
  - id: generalize-widget
    content: Port and generalize ConsoleOutputWidget with optional capture and callbacks
    status: completed
  - id: update-stream-viewer
    content: Add phopyqthelper dependency to stream_viewer and update imports
    status: completed
  - id: cleanup
    content: Remove original console_output.py from stream_viewer
    status: completed
---

# PhoPyQtHelper Package Creation

## Package Structure

Create new package at `C:\Users\pho\repos\ACTIVE_DEV\phopyqthelper\`:

```
phopyqthelper/
├── pyproject.toml
├── README.md
├── src/
│   └── phopyqthelper/
│       ├── __init__.py
│       ├── py.typed
│       └── widgets/
│           ├── __init__.py
│           └── console_output.py
└── uv.lock
```

## Key Changes to ConsoleOutputWidget

### 1. Optional Stream Capture

- Add `capture_stdout: bool = True` and `capture_stderr: bool = True` constructor params
- Allow widget to function as pure log viewer without capturing system streams
- Restore streams properly when capture is disabled mid-session

### 2. Callback Support

- Add `text_callback: Optional[Callable[[str, str], None]]` param (receives text and source: "stdout"/"stderr"/"manual")
- Fire callback on every write, enabling external logging/processing
- Keep existing UI behavior intact

### 3. Enhanced TextStream

- Track source stream type for callback routing
- Add `source` property to distinguish stdout vs stderr writes

## Implementation Summary

```python
class ConsoleOutputWidget(QtWidgets.QWidget):
    def __init__(self, parent=None, capture_stdout: bool = True, capture_stderr: bool = True, text_callback: Optional[Callable[[str, str], None]] = None):
        ...
    
    def append_text(self, text: str, source: str = "manual"):
        """Public method to append text programmatically."""
        ...
    
    def set_capture(self, stdout: bool, stderr: bool):
        """Enable/disable capture at runtime."""
        ...
```

## Integration with stream_viewer

1. Add `phopyqthelper` as editable dependency in [`stream_viewer/pyproject.toml`](stream_viewer/pyproject.toml)
2. Update import in stream_viewer to use `from phopyqthelper.widgets import ConsoleOutputWidget`
3. Delete original [`stream_viewer/widgets/console_output.py`](stream_viewer/stream_viewer/widgets/console_output.py)

## Dependencies for phopyqthelper

```toml
dependencies = [
    "qtpy>=2.0.0",
]
```

Minimal Qt dependency (qtpy) allows users to bring their own Qt binding (PyQt5, PyQt6, PySide2, PySide6).