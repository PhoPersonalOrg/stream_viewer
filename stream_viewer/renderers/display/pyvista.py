import numpy as np
from qtpy import QtCore, QtWidgets
from typing import Optional
from stream_viewer.renderers.display.base import RendererBaseDisplay

try:
    import pyvista as pv
    import pyvistaqt as pvqt
    PYVISTA_AVAILABLE = True
except ImportError:
    PYVISTA_AVAILABLE = False
    pv = None
    pvqt = None


class PyVistaRenderer(RendererBaseDisplay):
    """
    PyVista-backed display mixin with Qt integration and timer support,
    consistent with other renderer display classes.
    """

    gui_kwargs = dict(RendererBaseDisplay.gui_kwargs)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not PYVISTA_AVAILABLE:
            raise RuntimeError("pyvista and pyvistaqt are required for PyVistaRenderer")
        
        self._timer = QtCore.QTimer()
        self._timer.timeout.connect(self.on_timer)
        self._container = QtWidgets.QWidget()
        self._layout = QtWidgets.QVBoxLayout(self._container)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._plotter: Optional[pvqt.BackgroundPlotter] = None

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

    @RendererBaseDisplay.bg_color.setter
    def bg_color(self, value):
        self._bg_color = value
        # Update existing plotter if present
        if self._plotter is not None:
            try:
                # Convert color string to RGB tuple for PyVista
                bg_rgb = self._pyvista_color_from_str(value)
                self._plotter.set_background(bg_rgb)
            except Exception:
                pass

    @staticmethod
    def _pyvista_color_from_str(color_str: str):
        """Convert color string to RGB tuple for PyVista."""
        try:
            import matplotlib.colors
            rgba = matplotlib.colors.to_rgba(color_str)
            return rgba[:3]  # Return RGB only, PyVista uses 0-1 range
        except Exception:
            return (0.0, 0.0, 0.0)  # Default to black

