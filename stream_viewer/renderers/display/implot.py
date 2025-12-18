#  Copyright (C) 2014-2021 Syntrogi Inc dba Intheon. All rights reserved.

import logging
import numpy as np
from qtpy import QtCore, QtWidgets, QtOpenGL
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    pass

from stream_viewer.renderers.display.base import RendererBaseDisplay

logger = logging.getLogger(__name__)

# Try to import slimgui, handle gracefully if unavailable
try:
    import slimgui
    from slimgui import ImGui, ImPlot
    SLIMGUI_AVAILABLE = True
except ImportError:
    SLIMGUI_AVAILABLE = False
    logger.warning("slimgui not available. HeatmapImPlot renderer will not work.")


class ImPlotOpenGLWidget(QtOpenGL.QOpenGLWidget):
    """Custom QOpenGLWidget for embedding ImPlot rendering."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._implot_context = None
        self._imgui_context = None
        self._render_callback = None
        self._width = 0
        self._height = 0
        
    def set_render_callback(self, callback):
        """Set the callback function to render ImPlot content."""
        self._render_callback = callback
        
    def initializeGL(self):
        """Initialize OpenGL and ImPlot context."""
        if not SLIMGUI_AVAILABLE:
            logger.error("slimgui not available, cannot initialize ImPlot")
            return
            
        try:
            # Initialize ImGui context
            if self._imgui_context is None:
                self._imgui_context = ImGui.CreateContext()
                ImGui.SetCurrentContext(self._imgui_context)
            
            # Initialize ImPlot context
            if self._implot_context is None:
                self._implot_context = ImPlot.CreateContext()
                ImPlot.SetCurrentContext(self._implot_context)
            
            # Set up ImGui IO
            io = ImGui.GetIO()
            io.ConfigFlags |= ImGui.ConfigFlags_ViewportsEnable
            
            logger.debug("ImPlot context initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize ImPlot context: {e}", exc_info=True)
    
    def resizeGL(self, width, height):
        """Handle widget resize."""
        self._width = width
        self._height = height
        if SLIMGUI_AVAILABLE and self._imgui_context is not None:
            try:
                ImGui.SetCurrentContext(self._imgui_context)
                io = ImGui.GetIO()
                io.DisplaySize = (width, height)
            except Exception as e:
                logger.warning(f"Error updating ImGui display size: {e}")
    
    def paintGL(self):
        """Render ImPlot content."""
        if not SLIMGUI_AVAILABLE or self._implot_context is None:
            return
            
        try:
            from OpenGL import GL
            
            # Make sure we're using the correct OpenGL context
            ImGui.SetCurrentContext(self._imgui_context)
            ImPlot.SetCurrentContext(self._implot_context)
            
            # Start new frame
            io = ImGui.GetIO()
            io.DisplaySize = (self.width(), self.height())
            io.DeltaTime = 1.0 / 60.0  # Approximate delta time
            
            ImGui.NewFrame()
            
            # Call render callback if set
            if self._render_callback is not None:
                self._render_callback()
            
            # Render
            ImGui.Render()
            
            # Get draw data and render using OpenGL
            draw_data = ImGui.GetDrawData()
            if draw_data:
                # Clear and set up viewport
                GL.glViewport(0, 0, int(io.DisplaySize[0]), int(io.DisplaySize[1]))
                GL.glClearColor(0.0, 0.0, 0.0, 1.0)
                GL.glClear(GL.GL_COLOR_BUFFER_BIT)
                
                # Render ImGui draw data
                # Note: This is a simplified rendering - slimgui may provide a renderer
                # For now, we'll rely on slimgui's backend to handle this
                # If slimgui has a renderer, use it here instead
                
        except Exception as e:
            logger.error(f"Error in ImPlot rendering: {e}", exc_info=True)
    
    def cleanup(self):
        """Clean up ImPlot and ImGui contexts."""
        if SLIMGUI_AVAILABLE:
            try:
                if self._implot_context is not None:
                    ImPlot.SetCurrentContext(self._implot_context)
                    ImPlot.DestroyContext(self._implot_context)
                    self._implot_context = None
                
                if self._imgui_context is not None:
                    ImGui.SetCurrentContext(self._imgui_context)
                    ImGui.DestroyContext(self._imgui_context)
                    self._imgui_context = None
            except Exception as e:
                logger.warning(f"Error cleaning up ImPlot context: {e}")


class ImPlotRenderer(RendererBaseDisplay):
    """
    Base class for ImPlot-based renderers.
    
    Provides GPU-accelerated rendering using ImPlot embedded in Qt widgets.
    """
    
    # Basic colormap names that ImPlot supports
    # Note: ImPlot has different colormaps than PyQtGraph, so we'll need translation
    color_sets = [
        'Deep', 'Dark', 'Pastel', 'Paired', 'Viridis', 'Plasma', 'Hot', 'Cool',
        'Pink', 'Jet', 'Rainbow', 'Turbo', 'Cividis', 'Inferno', 'Magma'
    ]
    TIMER_INTERVAL = int(1000/60)  # 60 FPS
    
    def __init__(self, **kwargs):
        """
        Mix-in for ImPlot-based renderers.
        
        Mixed-in target must also inherit from a stream_viewer.renderers.data class
        or implement its own `on_timer` method.
        
        Args:
            **kwargs: Passed to parent class
        """
        if not SLIMGUI_AVAILABLE:
            raise ImportError(
                "slimgui is required for ImPlot renderers. "
                "Install it with: pip install slimgui"
            )
        
        super().__init__(**kwargs)
        self._timer = QtCore.QTimer()
        self._timer.timeout.connect(self.on_timer)
        self._widget = None  # Will be set by subclass
    
    @property
    def native_widget(self):
        """Return the native widget for embedding."""
        return self._widget
    
    def stop_timer(self):
        """Stop the update timer."""
        self._timer.stop()
    
    def restart_timer(self):
        """Restart the update timer."""
        if self._timer.isActive():
            self._timer.stop()
        self._timer.start(self.TIMER_INTERVAL)
    
    @staticmethod
    def parse_color_str(color_str: str) -> str:
        """Parse color string to a standard format."""
        _col = color_str.replace("'", "")
        if len(color_str) > 1:
            if color_str == 'black':
                _col = 'k'
            elif color_str[0] in ['r', 'g', 'b', 'c', 'm', 'y', 'k', 'w']:
                _col = color_str[0]
        return _col
    
    @staticmethod
    def get_colormap_name(color_set: str) -> str:
        """
        Translate PyQtGraph colormap names to ImPlot colormap names.
        
        Args:
            color_set: PyQtGraph colormap name
            
        Returns:
            ImPlot colormap name (or 'Viridis' as default)
        """
        # Map common colormap names
        colormap_map = {
            'viridis': 'Viridis',
            'plasma': 'Plasma',
            'inferno': 'Inferno',
            'magma': 'Magma',
            'hot': 'Hot',
            'cool': 'Cool',
            'jet': 'Jet',
            'rainbow': 'Rainbow',
            'turbo': 'Turbo',
            'cividis': 'Cividis',
            'deep': 'Deep',
            'dark': 'Dark',
            'pastel': 'Pastel',
            'paired': 'Paired',
            'pink': 'Pink',
        }
        
        # Try direct match (case-insensitive)
        color_lower = color_set.lower()
        if color_lower in colormap_map:
            return colormap_map[color_lower]
        
        # Default to Viridis
        return 'Viridis'
    
    def cleanup(self):
        """Clean up resources. Should be called when renderer is destroyed."""
        self.stop_timer()
        if isinstance(self._widget, ImPlotOpenGLWidget):
            self._widget.cleanup()

