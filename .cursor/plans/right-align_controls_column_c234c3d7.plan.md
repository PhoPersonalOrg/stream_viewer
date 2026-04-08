---
name: Right-align controls column
overview: Adjust the stream row `GridLayout` in QML so column 0 grows with available width and the type/channels/rate text plus status LED stay grouped at the delegate’s right edge (with text right-aligned within the middle column for a clean edge).
todos:
  - id: fillwidth-col0
    content: "Add Layout.fillWidth: true to name, Host, and Nom.Rate items (column 0)"
    status: completed
  - id: align-col1-text
    content: "Add Layout.alignment + horizontalAlignment: Text.AlignRight to Type, Channels, Eff.Rate texts"
    status: completed
  - id: align-led-row
    content: Add Layout.alignment Qt.AlignRight to statusRow (column 2)
    status: completed
isProject: false
---

# Align right controls column to window edge

## Cause

The list delegate in [`stream_viewer/qml/streamInfoListView.qml`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\stream_viewer\stream_viewer\qml\streamInfoListView.qml) uses a `GridLayout` with three columns (left facts, middle “Type / Channels / Eff.Rate”, LED). Extra horizontal space is not assigned to column 0, so columns 1–2 stay near the content instead of hugging the right side of each row `Rectangle`.

## Approach (minimal QML change)

All edits stay in [`streamInfoListView.qml`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\stream_viewer\stream_viewer\qml\streamInfoListView.qml); no Python changes are required (`StreamStatusQMLWidget` already sizes the `QQuickView` to the container).

1. **Let column 0 absorb slack**  
   On the three items in `Layout.column: 0` (stream `name`, `Host`, `Nom.Rate`), set `Layout.fillWidth: true` so the first column expands and pushes columns 1 and 2 toward the right edge of the delegate.

2. **Right-align the middle column text**  
   On each `Text` in `Layout.column: 1` (`Type`, `Channels`, `Eff.Rate`), add:
   - `Layout.alignment: Qt.AlignRight | Qt.AlignVCenter` (keign the cell anchored to the right within the grid)
   - `horizontalAlignment: Text.AlignRight` so multi-line / varying label lengths share a common right edge inside the column (column width will follow the widest of the three rows).

3. **Align the LED row**  
   On the `Row` `statusRow` (`Layout.column: 2`), set `Layout.alignment: Qt.AlignRight | Qt.AlignVCenter` so the indicator stays tight to the right next to the type row.

## Verification

Resize the “LSL Stream Status” window horizontally: the left block should stay left, and the type/channels/rate block plus LED should remain flush to the right margin of each light-gray row (still inset by the existing `anchors.margins: 2` on the `GridLayout`).

## Files touched

- [`stream_viewer/qml/streamInfoListView.qml`](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\stream_viewer\stream_viewer\qml\streamInfoListView.qml) only.
