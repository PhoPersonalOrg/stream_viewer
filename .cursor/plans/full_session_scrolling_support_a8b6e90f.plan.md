---
name: Full Session Scrolling Support
overview: Modify HeatmapPG to accumulate spectrogram columns for the entire session instead of rolling/shifting, enabling users to scroll back through all observed data.
todos: []
---

# Full

Session Scrolling Support for HeatmapPG

## Overview

Currently, the heatmap uses a fixed-size array that rolls/shifts data in Scroll mode, limiting history to the `duration` window. This plan modifies the renderer to accumulate all spectrogram columns for the entire session, enabling unlimited scrolling through historical data.

## Architecture Changes

### Current Behavior

- Heatmap initialized with fixed `n_time_cols` based on `duration`
- In Scroll mode: `heat[:, :-new_cols] = heat[:, new_cols:]` (rolls left)
- X-axis range limited to current `duration` window
- Old data is discarded when rolling

### Target Behavior

- Heatmap grows dynamically as new columns are computed
- All columns are preserved (no rolling/shifting)
- X-axis allows scrolling through full session time range
- Display extracts appropriate time window from full history

## Implementation Plan

### 1. Modify SourceState to Track Session History

**File**: `stream_viewer/stream_viewer/renderers/heatmap_pg.py`

- Add `session_start_time: Optional[float]` to track when session began
- Add `session_time_range: Optional[Tuple[float, float]]` to track full time span
- Modify `reset()` method to clear session tracking

### 2. Update Heatmap Initialization

**File**: `stream_viewer/stream_viewer/renderers/heatmap_pg.py`**Method**: `_ensure_source_state()`

- Change from fixed-size initialization to dynamic growth
- Start with small initial size (e.g., `n_time_cols` based on `duration`)
- Remove fixed-size constraint - allow heatmap to grow beyond `duration`

### 3. Modify Column Update Logic

**File**: `stream_viewer/stream_viewer/renderers/heatmap_pg.py`**Method**: `_update_heatmap_columns()`

- **Current**: Rolls left and overwrites: `heat[:, :-new_cols] = heat[:, new_cols:]`
- **New**: Append new columns using `np.concatenate()` or `np.append()`
- Grow heatmap array dynamically instead of circular buffer behavior
- Track total columns accumulated: `state.n_time_cols` becomes running total

### 4. Update Display Preparation

**File**: `stream_viewer/stream_viewer/renderers/heatmap_pg.py`**Method**: `_prepare_display_heatmap()`

- Extract appropriate time window from full history based on current x-axis range
- Map time range to column indices in the accumulated heatmap
- Return subset of columns corresponding to visible time window
- Handle edge cases (session start, current time, empty history)

### 5. Update X-Axis Range Management

**File**: `stream_viewer/stream_viewer/renderers/heatmap_pg.py`**Method**: `update_visualization()`

- Calculate full session time range: `[session_start_time, current_time]`
- Allow x-axis to scroll through full range, not just `duration` window
- Update `setXRange()` to use full session range when not manually scrolled
- Update `sync_to_present()` to use current time window within full range

### 6. Track Session Start Time

**File**: `stream_viewer/stream_viewer/renderers/heatmap_pg.py`**Method**: `update_visualization()`

- On first data update, record `session_start_time` from buffer timestamps
- Update `session_time_range` as new data arrives
- Use this for x-axis limits and display window calculation

### 7. Update Column Calculation

**File**: `stream_viewer/stream_viewer/renderers/heatmap_pg.py`**Method**: `_calculate_new_columns()`

- Logic remains similar (timestamp-based in Scroll mode)
- No changes needed - already calculates new columns correctly
- The difference is in how columns are stored (append vs roll)

### 8. Handle Reset Behavior

**File**: `stream_viewer/stream_viewer/renderers/heatmap_pg.py`**Method**: `reset_renderer()`

- Clear session tracking when reset is called
- Reset heatmap to initial small size
- Preserve session history only if reset is for channel labels (not full reset)

## Key Code Locations

1. **SourceState dataclass** (lines 32-56): Add session tracking fields
2. **`_ensure_source_state()`** (lines 373-422): Change to dynamic initialization
3. **`_update_heatmap_columns()`** (lines 763-801): Replace roll with append
4. **`_prepare_display_heatmap()`** (lines 803-831): Extract time window from full history
5. **`update_visualization()`** (lines 970-1126): Track session time and update x-axis range

## Memory Considerations

- Memory grows linearly with session duration
- For typical EEG (256 samples/sec, 128 hop): ~2 columns/second
- 1 hour session ≈ 7,200 columns × frequency bins × 8 bytes ≈ manageable
- No memory limit implemented per user request (unlimited storage)

## Testing Considerations

- Verify heatmap grows correctly as session progresses
- Test scrolling backward through full history
- Test `sync_to_present()` returns to most recent data
- Test `disconnect_from_realtime()` allows scrolling through history
- Verify x-axis range updates correctly with full session span
- Test with multiple data sources (each tracks independently)

## Edge Cases

- Empty buffer at start: Initialize with small default size
- Session restart: Reset clears history (expected behavior)