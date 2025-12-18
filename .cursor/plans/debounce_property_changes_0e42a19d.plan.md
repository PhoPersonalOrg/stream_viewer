---
name: Debounce Property Changes
overview: Add debouncing to property setters to prevent expensive reset_renderer() calls from blocking the UI during configuration changes. Some properties will update in-place, while others will use a deferred reset mechanism.
todos: []
---

# Imp

rove UI Responsiveness for Spectrogram Configuration Changes

## Problem

Every property change in `HeatmapPG` calls `reset_renderer()` synchronously, which:

- Clears the entire widget and rebuilds all plots
- Resets all accumulated heatmap state
- Blocks the UI thread during slider/dropdown interactions
- Makes dropdowns take seconds to appear

## Solution

### 1. Add Debounced Reset Mechanism

Add a `QTimer` to defer expensive `reset_renderer()` calls. Rapid property changes will only trigger one reset after the user stops adjusting.**File**: `stream_viewer/stream_viewer/renderers/heatmap_pg.py`

- Add `_reset_timer` and `_pending_reset` flag in `__init__`
- Create `_schedule_reset()` method that starts/stops the debounce timer
- Timer fires after 300ms of inactivity to batch rapid changes

### 2. Update Simple Properties In-Place

Some properties can update existing plot items without a full reset:**Properties that can update in-place:**

- `fmin_hz` / `fmax_hz`: Update Y-axis range and frequency mask (invalidate state for next update)
- `nperseg` / `noverlap`: Invalidate state, let next update recompute with new parameters
- `color_set`: Update LUT cache and refresh image items

**Properties requiring full reset:**

- `ylabel_as_title`, `ylabel`, `ylabel_width`: Require layout changes
- `auto_scale`: Requires full reset

### 3. Stop Update Timer During Resets

Prevent conflicts between the update loop and property changes:

- Stop timer before `reset_renderer()`
- Restart timer after reset completes
- Add flag to prevent concurrent resets

### 4. Preserve State When Possible

For properties that only affect display (not structure), preserve accumulated heatmap data:

- Don't reset `_source_states` for frequency range changes
- Only invalidate frequency mask, let next update recompute

## Implementation Details

### Debounce Timer Pattern

```python
# In __init__:
self._reset_timer = pg.QtCore.QTimer()
self._reset_timer.setSingleShot(True)
self._reset_timer.timeout.connect(self._do_pending_reset)
self._pending_reset = {'reset_channel_labels': False}

# New method:
def _schedule_reset(self, reset_channel_labels: bool = False):
    """Schedule a debounced reset_renderer call."""
    self._pending_reset['reset_channel_labels'] = (
        self._pending_reset.get('reset_channel_labels', False) or reset_channel_labels
    )
    self._reset_timer.stop()
    self._reset_timer.start(300)  # 300ms debounce

def _do_pending_reset(self):
    """Execute the pending reset (called by timer)."""
    if self._timer.isActive():
        self._timer.stop()
    try:
        self.reset_renderer(reset_channel_labels=self._pending_reset['reset_channel_labels'])
    finally:
        if not self._timer.isActive():
            self.restart_timer()
    self._pending_reset = {'reset_channel_labels': False}
```



### In-Place Updates for Frequency Properties

```python
@fmin_hz.setter
def fmin_hz(self, value):
    self._fmin_hz = float(value)
    # Update Y-axis range in-place if plots exist
    if self._image_items:
        for src_ix in range(len(self._image_items)):
            pw = self._widget.getItem(src_ix, 0)
            if pw:
                pw.setYRange(self._fmin_hz, self._fmax_hz)
        # Invalidate frequency mask - will recompute on next update
        for state in self._source_states:
            state.freq_mask = None
    else:
        # No plots yet, need full reset
        self._schedule_reset(reset_channel_labels=False)
```



## Files to Modify

1. **stream_viewer/stream_viewer/renderers/heatmap_pg.py**

- Add debounce timer in `__init__`
- Add `_schedule_reset()` and `_do_pending_reset()` methods
- Update property setters to use debouncing or in-place updates
- Modify `reset_renderer()` to stop/restart timer safely

## Testing Considerations

- Verify dropdowns appear instantly during property changes
- Ensure sliders are responsive without lag