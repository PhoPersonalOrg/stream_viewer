from qtpy import QtWidgets

from stream_viewer.widgets.time_series import TimeSeriesControl


class LinePowerControlPanel(TimeSeriesControl):
    """
    Control panel for the LinePowerVis renderer.

    This subclasses TimeSeriesControl but hides controls that are not meaningful
    for the power-band visualization (e.g., per-channel marker scale, font size,
    and the generic "Show Names" channel-label toggle).
    """

    def __init__(self, renderer, name: str = "LinePowerControlPanelWidget", **kwargs):
        super().__init__(renderer, name=name, **kwargs)

    def reset_widgets(self, renderer):
        # Run the standard time-series wiring first
        super().reset_widgets(renderer)

        # Disable/hide unused default controls for this renderer
        disabled_widgets = {
            "ShowNames_CheckBox",
            "MarkerScale_SpinBox",
            "FontSize_SpinBox",
            "Colors_ComboBox",
            "HP_SpinBox",
        }

        layout = self.layout()
        for object_name in disabled_widgets:
            widget = self.findChild(QtWidgets.QWidget, object_name)
            if widget is None:
                continue

            # Hide the control itself
            widget.setVisible(False)

            # Also hide the label in the same row (column 0 in the grid)
            try:
                idx = layout.indexOf(widget)
                if idx != -1:
                    row, col, row_span, col_span = layout.getItemPosition(idx)
                    label_item = layout.itemAtPosition(row, 0)
                    if label_item is not None and label_item.widget() is not None:
                        label_item.widget().setVisible(False)
            except Exception:
                # Best-effort; if layout lookup fails, just leave the hidden control.
                pass


