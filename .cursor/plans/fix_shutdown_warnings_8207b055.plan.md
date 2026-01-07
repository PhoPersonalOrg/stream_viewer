---
name: Fix shutdown warnings
overview: Fix QML parent.width null access warnings and QGuiApplication::font() warnings that occur during application shutdown by adding null checks in QML and ensuring QFont creation doesn't require QApplication during cleanup.
todos:
  - id: fix_qml_parent
    content: Fix QML parent.width null access by adding conditional check in streamInfoListView.qml line 18
    status: completed
  - id: fix_line_pg_fonts
    content: Replace QtGui.QFont() with explicit font parameters in line_pg.py (lines 125 and 288)
    status: completed
  - id: fix_line_power_vis_font
    content: Replace QtGui.QFont() with explicit font parameters in line_power_vis.py (line 150)
    status: completed
  - id: verify_stream_info_font
    content: Verify stream_info.py font creation is safe during shutdown
    status: completed
---

# Fix Shutdown Warnings

## Problem Analysis

Two types of warnings occur during application shutdown:

1. **QML Warning**: `TypeError: Cannot read property 'width' of null` at line 18 of `streamInfoListView.qml`

- The delegate tries to access `parent.width` during destruction when the parent ListView is already null

2. **QGuiApplication::font() Warnings**: Three warnings about no QGuiApplication instance

- Occurs when `QtGui.QFont()` is called during widget destruction after QApplication is destroyed
- Affects: `line_pg.py` (lines 125, 288), `line_power_vis.py` (line 150), and `stream_info.py` (line 24)

## Solution

### 1. Fix QML Parent Access ([stream_viewer/qml/streamInfoListView.qml](stream_viewer/stream_viewer/qml/streamInfoListView.qml))

**Line 18**: Replace direct `parent.width` access with a conditional binding that handles null parent:

```qml
width: parent ? parent.width : 0
```

This prevents the error when the delegate is destroyed and parent becomes null.

### 2. Fix QFont Creation During Shutdown

**Option A (Preferred)**: Provide explicit font parameters so QFont doesn't need to query QApplication:

- `line_pg.py` lines 125, 288: Change `QtGui.QFont()` to `QtGui.QFont("Arial", 10)` or similar
- `line_power_vis.py` line 150: Same change
- `stream_info.py` line 24: Already has explicit font, but may need a guard

**Option B**: Add guards to check if QApplication exists before creating fonts (more defensive but less clean)**Implementation**: Use Option A - provide explicit font family and size. This avoids QApplication dependency entirely.

### Files to Modify

1. `stream_viewer/stream_viewer/qml/streamInfoListView.qml` - Add null check for parent.width
2. `stream_viewer/stream_viewer/renderers/line_pg.py` - Provide explicit font parameters (2 locations)
3. `stream_viewer/stream_viewer/renderers/line_power_vis.py` - Provide explicit font parameters
4. `stream_viewer/stream_viewer/widgets/stream_info.py` - Verify font creation is safe (may already be OK, but check)

## Implementation Details