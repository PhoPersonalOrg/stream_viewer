# Channel Activity Monitoring Feature

## Overview

Add visual activity indicators and optional no-data notifications to the channel list in the control panel. This helps users detect when a headset disconnects or data acquisition stops.

## Implementation Details

### 1. Track Last Received Timestamp Per Channel

**File**: `stream_viewer/renderers/data/base.py`

- Add a dictionary `_channel_last_received` to `RendererBufferData` to track the last timestamp when each channel received data
- Initialize in `__init__` or `reset_buffers`
- Update in `fetch_data()` when data is received:
  - For each channel that has new data, record the current timestamp (use `time.time()` or the latest timestamp from the data)
  - Track at the channel level (by channel name/index)

**Key changes**:

- Add `self._channel_last_received = {}` to track `{channel_name: last_timestamp}`
- In `fetch_data()`, after buffer update, iterate through channels and update timestamps for channels with new data
- Use the latest timestamp from the received data or `time.time()` for wall-clock time

### 2. Add Activity Light Indicator to Channel Items

**File**: `stream_viewer/widgets/interface.py`

- Modify `reset_widgets()` to add an activity light widget to each channel item
- Use `QTreeWidget.setItemWidget()` to add a custom widget in a second column
- Create a small colored indicator (QLabel with fixed size, colored background):
  - Green when data received recently (within last 1-2 seconds)
  - Gray/Red when no data received recently (more than 2 seconds)
- Update the indicator periodically (via timer or in `reset_widgets` refresh)

**Key changes**:

- In `reset_widgets()`, after creating channel items, add a second column or use `setItemWidget()` to add activity light
- Store references to activity light widgets in a dictionary keyed by channel name
- Add a method to update activity lights based on `renderer._channel_last_received`

### 3. Add "Notify No Data" Toggle

**File**: `stream_viewer/widgets/interface.py`

- Add a checkbox widget next to each channel item (or in a third column)
- Store the notify preference per channel (dictionary in `IControlPanel`)
- Persist preferences when channels are recreated

**Key changes**:

- Add `self._channel_notify_enabled = {}` to track which channels have notifications enabled
- Add checkbox widget using `setItemWidget()` for each channel
- Connect checkbox state changes to update the dictionary

### 4. Monitor and Alert System

**File**: `stream_viewer/widgets/interface.py`

- Add a QTimer that runs every 1-2 seconds to check channel activity
- For each channel with notifications enabled:
  - Check if `last_received_time` exists and is more than 10 seconds ago
  - If so, and the channel previously had data (to avoid alerting on initial connection), show a QMessageBox alert
  - Track which channels have already been alerted to avoid spam (reset when data resumes)

**Key changes**:

- Add `self._monitor_timer = QtCore.QTimer()` in `_init_widgets()`
- Add `self._alerted_channels = set()` to track channels that have been alerted
- Create `_check_channel_activity()` method that:
  - Gets `renderer._channel_last_received` 
  - Checks each enabled channel
  - Shows alert if > 10 seconds since last data
  - Resets alert flag when data resumes
- Connect timer to this method

### 5. Update Activity Indicators Periodically

**File**: `stream_viewer/widgets/interface.py`

- Connect the monitor timer to also update activity light colors
- Or add a separate method `_update_activity_lights()` that reads from renderer and updates widget colors

## Data Flow

```
Renderer.fetch_data() 
  → Updates buffer with new data
  → Updates _channel_last_received timestamps
  
Control Panel Monitor Timer (every 1-2s)
  → Reads renderer._channel_last_received
  → Updates activity light colors
  → Checks for no-data conditions
  → Shows alerts if needed
```

## UI Layout

The channel tree widget will have:

- Column 0: Channel name (checkbox for visibility)
- Column 1: Activity light (small colored circle/indicator)
- Column 2: "Notify" checkbox (optional, or could be in a tooltip/context menu)

Alternatively, use `setItemWidget()` to embed widgets in the same column with custom layout.

## Considerations

- Activity tracking doesn't need to be perfectly accurate - approximate is fine
- Use wall-clock time (`time.time()`) for simplicity rather than stream timestamps
- Only alert if channel previously had data (to avoid false alerts on initial connection)
- Store alert state per channel to prevent spam
- Activity lights should update smoothly without flickering