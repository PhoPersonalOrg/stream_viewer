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
            # "LL_SpinBox", "UL_SpinBox",
            # "Background_ComboBox",

        }

        for object_name in disabled_widgets:
            widget = self.findChild(QtWidgets.QWidget, object_name)
            if widget is not None:
                widget.setVisible(False)


