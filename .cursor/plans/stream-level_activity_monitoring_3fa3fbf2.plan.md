---
name: Stream-Level Activity Monitoring
overview: Revert channel-level activity monitoring implementation and replace it with stream-level monitoring. Add activity indicators and no-data notifications to the LSL stream list (QML view), tracking when each stream last received data.
todos:
  - id: revert-channel-changes
    content: Revert all channel-level activity monitoring code from interface.py and base.py, restoring original channel tree widget
    status: completed
  - id: add-stream-tracking
    content: Add _stream_last_received tracking dictionary to LSLInfoItemModel and update it in handleRateUpdated() when streams receive data
    status: completed
  - id: add-activity-roles
    content: Add ActivityStateRole and NotifyEnabledRole to LSLInfoItemModel and implement data() method to return activity states
    status: completed
  - id: modify-qml-view
    content: Modify streamInfoListView.qml to add activity light indicators and notify checkboxes to each stream item
    status: completed
  - id: add-monitoring
    content: Add monitor timer and alert system to StreamStatusQMLWidget to check stream activity and show QMessageBox alerts
    status: completed
  - id: expose-to-qml
    content: Expose notify preferences and activity checking methods from StreamStatusQMLWidget to QML via context properties
    status: completed
---

# Stream-Level Activity Monitoring

## Overview

Revert the channel-level activity monitoring implementation and replace it with stream-level monitoring. Activity indicators and notifications will be added to the LSL stream list displayed in the QML view, helping users detect when streams disconnect or stop sending data.

## Implementation Plan

### 1. Revert Channel-Level Changes

**Files to revert:**

- `stream_viewer/widgets/interface.py`: Remove all channel activity monitoring code (activity lights, notify checkboxes, monitor timer, etc.)
- `stream_viewer/renderers/data/base.py`: Remove `_channel_last_received` tracking dictionary and related code in `fetch_data()`

**Key changes:**

- Remove `_channel_last_received` dictionary from `RendererBufferData.__init__()`
- Remove channel tracking code from `RendererBufferData.fetch_data()`
- Remove all activity light, notify checkbox, and monitoring timer code from `IControlPanel`
- Restore original channel tree widget to single column with just channel names and visibility checkboxes

### 2. Add Stream Activity Tracking

**File**: `stream_viewer/data/stream_info.py`

- Add `_stream_last_received` dictionary to `LSLInfoItemModel` to track when each stream last received data
- Track streams by their unique key: `(name, type, hostname, uid)` tuple
- Update tracking in `handleRateUpdated()` method - when effective_rate is updated, it means data was received
- Initialize tracking dictionary in `__init__()`

**Key changes:**

```python
# In LSLInfoItemModel.__init__()
self._stream_last_received = {}  # {(name, type, hostname, uid): timestamp}

# In handleRateUpdated()
stream_key = (stream_data['name'], stream_data['type'], stream_data['hostname'], stream_data['uid'])
self._stream_last_received[stream_key] = time.time()
```

### 3. Add Activity Tracking to LSLDataSource

**File**: `stream_viewer/data/stream_lsl.py`

- Track when data is actually fetched from the stream
- Update stream activity timestamp in `fetch_data()` method when data is successfully retrieved
- Store reference to stream info for tracking

**Key changes:**

- Add timestamp tracking when `fetch_data()` returns non-empty data
- Emit signal or update model when data is received (or use existing `rate_updated` signal)

### 4. Modify QML Stream List View

**File**: `stream_viewer/qml/streamInfoListView.qml`

- Add activity light indicator (colored circle) to each stream item
- Add "Notify" checkbox for each stream
- Update GridLayout to accommodate new elements
- Add properties to model for activity state and notify preferences

**Key changes:**

- Add activity light Rectangle/Item with color based on activity state
- Add CheckBox for notifications
- Add roles to model for `activityState` and `notifyEnabled`
- Use color coding: green (active <2s), yellow (2-10s), red (>10s), gray (never)

### 5. Add Monitoring and Alert System

**File**: `stream_viewer/widgets/stream_info.py`

- Add monitor timer to `StreamStatusQMLWidget` that checks stream activity every 1-2 seconds
- Track notify preferences per stream in `_stream_notify_enabled` dictionary
- Track alerted streams in `_alerted_streams` set to prevent spam
- Add method to check stream activity and show alerts
- Expose stream activity state to QML via context properties or model roles

**Key changes:**

- Add `_monitor_timer` in `__init__()`
- Add `_stream_notify_enabled` dictionary
- Add `_alerted_streams` set
- Create `_check_stream_activity()` method that:
  - Reads `_stream_last_received` from model
  - Updates activity states (expose to QML)
  - Checks for no-data conditions (>10 seconds)
  - Shows QMessageBox alerts for enabled streams
- Connect timer to monitoring method

### 6. Expose Activity State to QML

**File**: `stream_viewer/data/stream_info.py`

- Add new roles to `LSLInfoItemModel`:
  - `ActivityStateRole`: Returns activity state (active, warning, critical, none)
  - `NotifyEnabledRole`: Returns whether notifications are enabled for this stream
- Update `data()` method to return activity state based on `_stream_last_received`
- Add method to set notify preference per stream

**File**: `stream_viewer/widgets/stream_info.py`

- Add methods to `StreamStatusQMLWidget` to:
  - Get/set notify preference for a stream
  - Get activity state for a stream
- Expose these methods to QML via context properties

## Data Flow

```
LSLDataSource.fetch_data() 
  → Returns data
  → LSLDataSource.rate_updated signal emitted
  → LSLInfoItemModel.handleRateUpdated()
  → Updates _stream_last_received[stream_key] = time.time()

StreamStatusQMLWidget Monitor Timer (every 1-2s)
  → Reads model._stream_last_received
  → Calculates activity states
  → Updates QML model roles (ActivityStateRole)
  → Checks for no-data conditions
  → Shows alerts if needed
```

## UI Changes

The stream list in QML will show:

- Stream metadata (existing: Name, Type, Host, Channels, Rates)
- Activity light indicator (new: colored circle showing data reception status)
- Notify checkbox (new: enable/disable notifications for this stream)

## Considerations

- Streams are uniquely identified by (name, type, hostname, uid) tuple
- Activity tracking uses `effective_rate` updates as indicator of data reception
- Alerts only fire for streams that previously had data (to avoid false alerts on initial connection)
- Alert state is reset when data resumes
- Notify preferences persist per stream key