"""
Minimal Renderer Example - A simple working renderer demonstrating core concepts.

This example creates a basic line plot renderer that visualizes streaming data.
Copy this file to ~/.stream_viewer/plugins/renderers/ to use it in the application.
"""

import numpy as np
import pyqtgraph as pg
from stream_viewer.renderers.data.base import RendererDataTimeSeries
from stream_viewer.renderers.display.pyqtgraph import PGRenderer


class MinimalRenderer(RendererDataTimeSeries, PGRenderer):
    """
    A minimal renderer that displays streaming data as simple line plots.
    
    Inherits from:
    - RendererDataTimeSeries: Handles data buffering and time series formatting
    - PGRenderer: Provides pyqtgraph widget and timer functionality
    """
    
    def __init__(self, **kwargs):
        # Create the pyqtgraph widget that will display our visualization
        self._widget = pg.PlotWidget()
        self._curves = []  # Store plot curve items for each channel
        
        # Call parent constructors (cooperative inheritance pattern)
        super().__init__(**kwargs)
        
        # Initialize the visualization
        self.reset_renderer()
    
    def reset_renderer(self, reset_channel_labels=True):
        """Rebuild the visualization when settings or data sources change."""
        # Clear existing plot items
        self._widget.clear()
        self._curves = []
        
        # Configure the plot appearance
        self._widget.setYRange(self.lower_limit, self.upper_limit)
        self._widget.setLabel('bottom', 'Time', units='s')
        
        # Create a curve for each visible channel
        for ch_idx, ch_state in self.chan_states.iterrows():
            if ch_state.get('vis', True):  # Check if channel is visible
                curve = self._widget.plot(pen=pg.mkPen(width=2))
                self._curves.append(curve)
    
    def update_visualization(self, data, timestamps):
        """Update the plot with new data (called automatically by timer)."""
        # data and timestamps are lists (one entry per data source)
        for src_idx, (src_data, src_ts) in enumerate(zip(data, timestamps)):
            dat, markers = src_data  # Separate time series data from markers
            ts, marker_ts = src_ts
            
            if dat.size > 0:  # Check if we have data to plot
                # Update each channel's curve with new data
                for ch_idx, curve in enumerate(self._curves):
                    if ch_idx < dat.shape[0]:  # Ensure channel exists
                        curve.setData(ts, dat[ch_idx])
