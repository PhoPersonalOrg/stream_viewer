---
name: Convert HeatmapPG to RemoteGraphicsView
overview: Convert the HeatmapPG renderer to use pyqtgraph's RemoteGraphicsView for background thread rendering. Replace GraphicsLayoutWidget with separate RemoteGraphicsView instances (one per data source) contained in a QVBoxLayout, and route all pyqtgraph operations through the remote process proxy.
todos:
  - id: import_remote
    content: Add RemoteGraphicsView import to heatmap_pg.py
    status: pending
  - id: update_init
    content: Replace GraphicsLayoutWidget with QWidget container and initialize RemoteGraphicsView storage lists
    status: pending
    dependencies:
      - import_remote
  - id: update_reset
    content: Refactor reset_renderer() to create RemoteGraphicsView instances and remote plot items, implement manual x-axis linking
    status: pending
    dependencies:
      - update_init
  - id: update_visualization
    content: Update update_visualization() to use remote plot items and remote pyqtgraph operations
    status: pending
    dependencies:
      - update_reset
  - id: update_sync_axes
    content: Update sync_y_axes() to work with remote plot items
    status: pending
    dependencies:
      - update_reset
  - id: update_markers
    content: Update _update_markers() to create remote TextItem instances
    status: pending
    dependencies:
      - update_reset
  - id: update_properties
    content: Update property setters (fmin_hz, fmax_hz) to use remote plot items
    status: pending
    dependencies:
      - update_reset
---

# Convert HeatmapPG to Use RemoteGraphicsView

## Overview

Convert `HeatmapPG` renderer from `GraphicsLayoutWidget` to `RemoteGraphicsView` to enable background thread rendering. Each data source will have its own `RemoteGraphicsView` instance, contained in a vertical layout widget.

## Architecture Changes

### Widget Structure

- **Current**: Single `GraphicsLayoutWidget` with multiple plots via `addPlot(row, col)`
- **New**: Container `QWidget` with `QVBoxLayout` containing multiple `RemoteGraphicsView` instances (one per data source)

### Remote Process Operations

All pyqtgraph operations must go through the `.pg` proxy:

- `pg.PlotItem()` → `remote_view.pg.PlotItem()`
- `pg.ImageItem()` → `remote_view.pg.ImageItem()`
- `pg.TextItem()` → `remote_view.pg.TextItem()`
- Plot operations (setXRange, setYRange, etc.) via proxy

### Data Flow

- Numpy arrays are automatically serialized when passed to remote process
- Qt objects (fonts, timers) remain in main process
- Plot items and graphics items created in remote process

## Implementation Details

### 1. Widget Initialization (`__init__`)

**File**: `stream_viewer/stream_viewer/renderers/heatmap_pg.py`

- Replace `self._widget = pg.GraphicsLayoutWidget()` with:
- `self._widget = QtWidgets.QWidget()` (container)
- `self._widget.setLayout(QtWidgets.QVBoxLayout())`
- `self._remote_views: list[RemoteGraphicsView] = []` (store RemoteGraphicsView instances)
- `self._plot_items: list[PlotItem] = []` (store remote plot items for x-axis linking)

### 2. Reset Renderer (`reset_renderer`)

**File**: `stream_viewer/stream_viewer/renderers/heatmap_pg.py`Changes:

- Clear container layout instead of `GraphicsLayoutWidget.clear()`
- For each data source:
- Create `RemoteGraphicsView(debug=False)`
- Add to container layout
- Create plot via `remote_view.pg.PlotItem()`
- **Performance**: Apply `plot_item._setProxyOptions(deferGetattr=True)` to speed up access
- Set as central item: `remote_view.setCentralItem(plot_item)`
- Store references in `self._remote_views` and `self._plot_items`
- Replace `self._widget.getItem(row, col)` with direct access to `self._plot_items[src_ix]`
- Replace `self._widget.addPlot()` with remote plot creation
- Manual x-axis linking: Link all plots to bottom plot using `setXLink()` on remote plot items
- **Performance**: Enable antialiasing in remote process: `remote_view.pg.setConfigOptions(antialias=True)` (doesn't affect main process performance)

### 3. Update Visualization (`update_visualization`)

**File**: `stream_viewer/stream_viewer/renderers/heatmap_pg.py`Changes:

- Replace `pw = self._widget.getItem(src_ix, 0)` with `pw = self._plot_items[src_ix]`
- All plot operations (setXRange, setYRange, etc.) work on remote plot items via proxy
- Image items created via `remote_view.pg.ImageItem()` and added to remote plot
- Markers created via `remote_view.pg.TextItem()`
- **Performance**: Use `_callSync='off'` for operations that don't need return values:
- `img.setImage(display, levels=levels, autoLevels=False, _callSync='off')`
- `img.setLookupTable(lut, _callSync='off')`
- `img.setRect(..., _callSync='off')`
- This tells the proxy not to wait for replies, improving performance for frequent updates

### 4. Sync Y Axes (`sync_y_axes`)

**File**: `stream_viewer/stream_viewer/renderers/heatmap_pg.py`Changes:

- Access plot items from `self._plot_items` instead of `self._widget.getItem()`
- Get axis via `plot_item.getAxis('left')` on remote plot items

### 5. Update Markers (`_update_markers`)

**File**: `stream_viewer/stream_viewer/renderers/heatmap_pg.py`Changes:

- Text items created via `remote_view.pg.TextItem()` instead of `pg.TextItem()`
- Access plot via `self._plot_items[src_ix]` instead of parameter

### 6. Property Setters

**File**: `stream_viewer/stream_viewer/renderers/heatmap_pg.py`Changes in `fmin_hz`, `fmax_hz` setters:

- Access plots via `self._plot_items` instead of `self._widget.getItem()`
- Operations on remote plot items work via proxy

### 7. Import Statement

**File**: `stream_viewer/stream_viewer/renderers/heatmap_pg.py`Add import:

```python
from pyqtgraph.widgets.RemoteGraphicsView import RemoteGraphicsView
```



## Key Considerations

1. **X-Axis Linking**: Since we lose automatic linking from `GraphicsLayoutWidget`, manually link all plots to the bottom plot using `plot_item.setXLink(bottom_plot_item)` on remote plot items.
2. **Layout Spacing**: Use `layout.setSpacing()` on the container layout instead of `self._widget.ci.setSpacing()`.
3. **Background Color**: Set background on each `RemoteGraphicsView` instead of the container widget.
4. **Font Objects**: Qt font objects are created in main process and passed to remote process (automatic serialization).
5. **Timer Objects**: Debounce timer remains in main process (not affected by remote rendering).
6. **Performance Optimizations** (from RemoteSpeedTest example):

- Use `_setProxyOptions(deferGetattr=True)` on plot items to speed up attribute access
- Use `_callSync='off'` for operations that don't need return values (setImage, setLookupTable, setRect)
- Enable antialiasing in remote process without affecting main process performance
- These optimizations are critical for real-time updates at 60fps

## Testing Considerations

- Verify all plots render correctly in remote process
- Confirm x-axis linking works across remote plots
- Test marker rendering in remote process
- Validate performance improvement from background rendering
- Ensure proper cleanup when renderer is destroyed