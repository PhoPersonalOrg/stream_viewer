---
name: Config and Info buttons
overview: Add two small icon-style buttons under the activity LED in the stream list delegate, wire them to new Python slots on `StreamStatusQMLWidget` for a Qt options dialog (Config) and console `print` output (Info). Reserve the right strip of the row from the background `MouseArea` so buttons remain clickable.
todos:
  - id: qml-column-buttons
    content: "QML: Column under LED, icon buttons, rowSpan, delegate height, MouseArea rightMargin"
    status: completed
  - id: py-slots-dialog-print
    content: "StreamStatusQMLWidget: printStreamInfo + openStreamConfig (QDialog + exec_)"
    status: completed
isProject: false
---

# Config and Info buttons below activity LED

## Context

- List delegate lives in [`stream_viewer/qml/streamInfoListView.qml`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\stream_viewer\stream_viewer\qml\streamInfoListView.qml): a 3-column `GridLayout` with the LED in column 2, row 0 only.
- A **full-rect** `MouseArea` on the delegate handles row selection and sits **on top of** the grid, so any new controls inside the grid would not receive clicks unless that `MouseArea` leaves a gap (e.g. `anchors.rightMargin`) on the right.

## 1. QML layout ([`streamInfoListView.qml`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\stream_viewer\stream_viewer\qml\streamInfoListView.qml))

- Bump delegate `height` slightly (e.g. **88–96**) so a vertical stack (LED + button row) fits without crowding the three text rows.
- Replace the current `Row` `statusRow` with a **`Column`** in column 2:
  - `Layout.row: 0`, `Layout.column: 2`, `Layout.rowSpan: 3`, `Layout.alignment: Qt.AlignRight | Qt.AlignTop`, small `spacing`.
  - Top: keep the existing **`activityLed`** `Rectangle` (same id so the LED tooltip `MouseArea` and flash logic stay valid).
  - Bottom: **`Row`** of two compact controls (e.g. flat `ToolButton` or small `Button`): **Config** (Unicode gear `\u2699` or similar) and **Info** (`i`-style `\u2139` / `ℹ`), with `ToolTip.text` set to `"Config"` / `"Info"`.
  - `onClicked`: call `OuterWidget.openStreamConfig(index)` and `OuterWidget.printStreamInfo(index)` respectively (`index` is the ListView delegate index).
- On the **background** row-selection `MouseArea` (`anchors.fill: parent`), set **`anchors.rightMargin`** to a fixed width (e.g. **56–64**) so the LED + buttons column is outside the area and remains interactive.

No changes to [`stream_viewer/data/stream_info.py`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\stream_viewer\stream_viewer\data\stream_info.py) unless you later want model-backed settings.

## 2. Python bridge ([`stream_viewer/widgets/stream_info.py`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\stream_viewer\stream_viewer\widgets\stream_info.py))

Add two `@QtCore.Slot(int)` methods on `StreamStatusQMLWidget` (same pattern as `activated` / `added`):

- **`printStreamInfo(self, index)`** — bounds-check `index`, build `strm = self.model._data.iloc[index].to_dict()`, then `print` a short header and each key/value (or a small number of `print(...)` lines) so the terminal shows full stream/channel discovery info.
- **`openStreamConfig(self, index)`** — bounds-check, same `strm` dict, open a **`QtWidgets.QDialog`** parented to `self` with `setWindowTitle` including stream name, **`QFormLayout`** with one read-only **`QLabel`** per field (iterate `strm.items()` in a stable order, e.g. model `col_names` first then any extras), and **`QDialogButtonBox`** with Ok connected to `accept`; use **`dlg.exec_()`** to match the rest of this package.

This satisfies “options panel” with real UI; fields are read-only for now (LSL discovery rows are not inherently editable). You can extend the dialog later with `QCheckBox` / `QSpinBox` if you add persisted per-stream settings.

## 3. Verification

- Run `lsl_status` (or main app dock): LED tooltip still works; row click selects when clicking left/middle; **Config** opens dialog; **Info** prints to the process stdout; buttons are not “dead” under the big `MouseArea`.

## Files to touch

- [`stream_viewer/qml/streamInfoListView.qml`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\stream_viewer\stream_viewer\qml\streamInfoListView.qml)
- [`stream_viewer/widgets/stream_info.py`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\stream_viewer\stream_viewer\widgets\stream_info.py)
