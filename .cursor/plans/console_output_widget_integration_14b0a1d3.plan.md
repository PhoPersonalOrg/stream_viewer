---
name: Console Output Widget Integration
overview: Suppress the default console window on Windows and integrate console output (stdout/stderr) into a toggleable dock widget within the application. The widget will automatically close with the main window and work reliably across Windows/macOS/Linux.
todos:
  - id: create-console-widget
    content: Create ConsoleOutputWidget class in stream_viewer/widgets/console_output.py with QPlainTextEdit, custom stream redirection, and thread-safe updates
    status: completed
  - id: suppress-windows-console
    content: Add Windows-specific code in main() to suppress console window using ctypes or early stream redirection
    status: completed
  - id: integrate-dock-widget
    content: Add console dock widget to LSLViewer.__init__() and create setup_console_panel() method similar to setup_status_panel()
    status: completed
    dependencies:
      - create-console-widget
  - id: add-menu-action
    content: Add 'Show Console Output' toggle action to View menu in setup_menus() with keyboard shortcut
    status: completed
    dependencies:
      - integrate-dock-widget
  - id: settings-persistence
    content: Add console dock settings save/restore in saveSettings() and restoreOnStartup() methods
    status: completed
    dependencies:
      - integrate-dock-widget
  - id: test-cleanup
    content: Verify widget properly cleans up when main window closes and stdout/stderr are restored
    status: completed
    dependencies:
      - integrate-dock-widget
---

# Console Output Widget Integration

## Overview

Replace the default console window with an integrated console output widget that can be toggled via the View menu. The widget captures stdout/stderr and displays it in a scrollable text area within the application.

## Implementation Details

### 1. Create Console Output Widget

**File**: `stream_viewer/widgets/console_output.py` (new file)

Create a new widget class `ConsoleOutputWidget` that:

- Inherits from `QtWidgets.QWidget`
- Contains a `QTextEdit` or `QPlainTextEdit` for displaying output
- Implements a custom `TextStream` class that redirects stdout/stderr to the widget
- Uses thread-safe signal/slot mechanism to update the UI from background threads
- Limits buffer size to prevent memory issues (e.g., keep last 10,000 lines)
- Provides clear button and auto-scroll toggle

### 2. Suppress Console Window on Windows

**File**: `stream_viewer/applications/main.py`

In the `main()` function, before creating `QApplication`:

- On Windows: Use `ctypes` to call `FreeConsole()` or set console visibility to hidden
- Alternatively: Redirect stdout/stderr early to prevent console window creation
- Use platform detection (`sys.platform == 'win32'`) for Windows-specific code
- Ensure this works when launched via `python.exe` or `pythonw.exe`

### 3. Integrate Widget into Main Window

**File**: `stream_viewer/applications/main.py`

In `LSLViewer.__init__()`:

- Create `ConsoleOutputWidget` instance
- Create a `QDockWidget` to contain it (similar to `setup_status_panel()`)
- Set dock properties: closable, movable, default to bottom dock area
- Store reference in `self._console_dock` for menu access

In `setup_menus()`:

- Add "Show Console Output" action to View menu
- Connect to toggle method that shows/hides the dock
- Optionally add keyboard shortcut (e.g., Ctrl+Shift+C)

### 4. Handle Settings Persistence

**File**: `stream_viewer/applications/main.py`

In `restoreOnStartup()`:

- Add "ConsoleOutput" settings group
- Restore dock visibility state, size, and position
- Ensure dock is properly parented to main window

In `saveSettings()`:

- Save console dock geometry (size, position, visibility)
- Save to "ConsoleOutput" settings group

### 5. Ensure Proper Cleanup

**File**: `stream_viewer/applications/main.py`

In `closeEvent()`:

- The dock widget will automatically be destroyed when parent closes
- Ensure stdout/stderr are restored to original streams if needed
- Widget cleanup handled by Qt parent-child relationship

### 6. Cross-Platform Considerations

- **Windows**: Suppress console window using `ctypes.windll.kernel32.FreeConsole()` or hide console
- **macOS/Linux**: Console typically doesn't appear for GUI apps, but widget should still work
- Use `sys.platform` checks for platform-specific code
- Test that stdout/stderr redirection works on all platforms

### 7. Performance Optimizations

- Use `QPlainTextEdit` instead of `QTextEdit` for better performance with large text
- Implement line limit (e.g., remove oldest lines when exceeding 10,000)
- Use `QTimer` to batch updates if needed (append multiple lines at once)
- Ensure thread-safe updates using `QtCore.QMetaObject.invokeMethod()` or signals

## Technical Approach

### Stream Redirection

Create a custom stream class that:

- Inherits from `io.TextIOBase` or uses a queue-based approach
- Emits Qt signals when text is written
- Connects to widget's append method via signal/slot

### Thread Safety

- Use `QtCore.QObject` for the stream wrapper to enable signals
- Emit signals from any thread, connect to widget's slot
- Widget updates happen on main thread via Qt's event loop

## Files to Modify

1. **New file**: `stream_viewer/widgets/console_output.py` - Console output widget implementation
2. **Modify**: `stream_viewer/applications/main.py` - Integrate widget, suppress console, add menu action
3. **Modify**: `stream_viewer/widgets/__init__.py` - Export new widget if needed

## Testing Considerations

- Verify console window doesn't appear on Windows
- Test widget shows stdout/stderr output correctly
- Verify widget closes with main window
- Test toggle functionality
- Verify settings persistence (visibility, size, position)
- Test with high-volume output (performance)
- Test on Windows, macOS, and Linux if possible