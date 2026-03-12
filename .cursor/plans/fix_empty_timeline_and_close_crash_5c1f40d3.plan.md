---
name: Fix empty timeline and close crash
overview: "Fix two issues: (1) timeline tracks show nothing because the initial stub interval does not overlap the viewport, so get_updated_data_window returns 0 intervals; (2) saveSettings() crashes on close because it assumes every dock widget has a .renderer attribute (timeline docks use SimpleTimelineWidget which does not)."
todos: []
isProject: false
---

# Fix empty timeline widgets and saveSettings crash

## Root cause 1: "found 0 intervals in viewport"

The TrackRenderer calls `get_updated_data_window(viewport_start, viewport_end)` to decide which intervals to draw. It only draws detail for intervals that overlap the viewport.

- **Viewport** is set in [_on_open_timeline](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\stream_viewer\stream_viewer\applications\main.py) with `plot_item.setXRange(now - window_seconds, now, padding=0)` → viewport is **(now - 10, now)**.
- **Initial stub interval** in [StreamViewerLSLTrackDatasource](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\stream_viewer\stream_viewer\timeline\stream_viewer_lsl_track_datasource.py) is built with `_make_stub_intervals_df(time.time())`, which creates a 1-second interval **(now, now+1)**.
- **(now, now+1)** does **not** overlap **(now-10, now)**, so `get_updated_data_window(now-10, now)` returns 0 rows. The ring buffer is empty at startup so `_update_intervals()` is never run and the interval stays as that initial stub.

So the adapter’s initial `intervals_df` must span a range that overlaps the default viewport. Once data arrives, `_update_intervals()` will replace it with the real buffer extent.

## Root cause 2: saveSettings AttributeError

In [saveSettings](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\stream_viewer\stream_viewer\applications\main.py) (around 486–491), the code does:

```python
for rend_key in self._open_renderers:
    dw = self.findChild(QtWidgets.QDockWidget, rend_key)
    stream_widget = dw.widget()  # ConfigAndRenderWidget or SimpleTimelineWidget
    renderer = stream_widget.renderer  # AttributeError for timeline docks
```

Timeline docks use `SimpleTimelineWidget` as the widget, which has no `.renderer` attribute. We must skip timeline docks in this loop.

---

## Plan

### 1. Make initial stub interval overlap the viewport

**File:** [stream_viewer/timeline/stream_viewer_lsl_track_datasource.py](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\stream_viewer\stream_viewer\timeline\stream_viewer_lsl_track_datasource.py)

In `StreamViewerLSLTrackDatasource.__init`__:

- Replace  
`stub = _make_stub_intervals_df(time.time())`  
with  
`now = time.time(); stub = _make_stub_intervals_df(now - buffer_seconds, now)`.

So the single initial interval spans **(now - buffer_seconds, now)**, which overlaps the viewport **(now - window_seconds, now)**. The base class will still add `t_start_dt`/`t_end_dt`/pen/brush in its `__init`__. When the ring buffer gets data, `_update_intervals()` will replace `self.intervals_df` with the real extent; until then, the track will show one interval in the viewport and detail fetch will return an empty DataFrame (empty plot) until data arrives.

### 2. Skip timeline docks in saveSettings

**File:** [stream_viewer/applications/main.py](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\stream_viewer\stream_viewer\applications\main.py)

In the loop that saves each renderer’s configuration (the `for rend_key in self._open_renderers:` block that calls `renderer.save_settings`):

- Before `stream_widget = dw.widget()`, add a check: if `rend_key.startswith("Timeline|")`, `continue` (skip saving renderer settings for timeline docks).
- Alternatively, after `stream_widget = dw.widget()`, use `if not hasattr(stream_widget, 'renderer'): continue`. Prefer the prefix check so timeline docks are explicitly recognized and not passed to any renderer logic.

### 3. (Optional) Skip timeline docks when restoring from settings

**File:** [stream_viewer/applications/main.py](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\stream_viewer\stream_viewer\applications\main.py)

In the "Restore renderer docks" loop (`for dock_name in dock_groups:`), at the start of the loop:

- If `dock_name.startswith("Timeline|")`, `continue`. That avoids calling `load_renderer("Timeline", ...)` (which would fail) and `on_stream_activated` for saved timeline docks. Timeline docks will not be re-created on startup; only their geometry is in settings. Users can open the timeline again after launch. This keeps restore logic simple and avoids a separate “restore timeline” path.

---

## Summary


| Issue              | Change                                                                                                                                     |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------ |
| Empty timeline     | In `StreamViewerLSLTrackDatasource.__init`__, set initial stub to `(now - buffer_seconds, now)` so it overlaps viewport `(now - 10, now)`. |
| saveSettings crash | In `saveSettings()`, skip `rend_key` when `rend_key.startswith("Timeline                                                                   |
| Restore (optional) | In restore loop, skip `dock_name.startswith("Timeline                                                                                      |


