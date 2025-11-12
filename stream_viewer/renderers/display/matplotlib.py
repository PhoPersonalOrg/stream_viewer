import numpy as np
# Matplotlib embedding
import matplotlib
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from qtpy import QtCore, QtWidgets
from typing import Optional
from stream_viewer.renderers.display.base import RendererBaseDisplay


class MPLRenderer(RendererBaseDisplay):
    """
    Minimal Matplotlib-backed display mixin with a Qt timer,
    consistent with other renderer display classes.
    """

    gui_kwargs = dict(RendererBaseDisplay.gui_kwargs)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._timer = QtCore.QTimer()
        self._timer.timeout.connect(self.on_timer)
        self._container = QtWidgets.QWidget()
        self._layout = QtWidgets.QVBoxLayout(self._container)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._canvas: Optional[FigureCanvas] = None

    @property
    def native_widget(self):
        return self._container

    def stop_timer(self):
        self._timer.stop()

    def restart_timer(self):
        if self._timer.isActive():
            self._timer.stop()
        # Match other renderers' ~60 FPS timer cadence
        self._timer.start(int(1000 / 60))

    # Background color mapping to figure face color
    @RendererBaseDisplay.bg_color.setter
    def bg_color(self, value):
        self._bg_color = value
        # Update existing figure if present
        if self._canvas is not None:
            try:
                face = self._mpl_facecolor_from_str(value)
                self._canvas.figure.set_facecolor(face)
                self._canvas.draw_idle()
            except Exception:
                pass

    @staticmethod
    def _mpl_facecolor_from_str(color_str: str):
        try:
            return matplotlib.colors.to_rgba(color_str)
        except Exception:
            return matplotlib.colors.to_rgba("black")
