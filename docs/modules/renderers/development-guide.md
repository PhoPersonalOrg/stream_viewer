# Renderer Development Guide

This guide provides step-by-step instructions for creating custom visualization renderers for StreamViewer. Whether you want to create a simple line plot or a complex 3D visualization, this guide will walk you through the process.

## Prerequisites

Before creating a custom renderer, you should be familiar with:

- Python 3.8+
- PyQt5 basics (signals, slots, widgets)
- One visualization library (pyqtgraph, vispy, or matplotlib)
- Basic understanding of streaming data concepts

## Quick Start: Minimal Renderer Example

The fastest way to understand renderer development is to see a working example. Here's a complete, minimal renderer (< 50 lines) that you can use as a template:

```python
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
```

**What this example demonstrates:**

1. **Cooperative Inheritance**: Inherits from both a data class (`RendererDataTimeSeries`) and a display class (`PGRenderer`)
2. **Widget Creation**: Creates `self._widget` which is the Qt widget displayed in the application
3. **Required Methods**: Implements `__init__`, `reset_renderer`, and `update_visualization`
4. **Data Handling**: Receives formatted data and timestamps from parent classes
5. **Channel Management**: Uses `self.chan_states` to track visible channels

## Understanding Renderer Architecture

### Cooperative Inheritance Pattern

StreamViewer uses cooperative inheritance to separate concerns between data handling and visualization:

```
Your Renderer
    ├── Data Parent (e.g., RendererDataTimeSeries)
    │   ├── Manages data sources and buffers
    │   ├── Handles data formatting and auto-scaling
    │   └── Provides fetch_data() method
    └── Display Parent (e.g., PGRenderer)
        ├── Provides timer for periodic updates
        ├── Manages Qt widget lifecycle
        └── Provides utility methods (colormaps, etc.)
```

**Key principle**: Always call `super().__init__(**kwargs)` to ensure all parent classes are properly initialized.

### Available Base Classes

#### Data Parent Classes

Choose one based on your visualization needs:


| Class | Use Case | Buffer Type | Data Format |
|-------|----------|-------------|-------------|
| `RendererDataTimeSeries` | Time series plots (line, area) | Time series buffer | List of (data, markers) tuples per source |
| `RendererMergeDataSources` | Snapshot visualizations (bar, radar) | Last-sample buffer | Single merged array across all sources |
| `RendererBufferData` | Custom buffering needs | Custom | List of tuples per source |

#### Display Parent Classes

Choose based on your preferred visualization library:

| Class | Library | Performance | Use Case |
|-------|---------|-------------|----------|
| `PGRenderer` | pyqtgraph | Good | 2D plots, moderate channel counts |
| `VispyRenderer` | vispy | Excellent | High-performance, many channels, 3D |
| Custom | matplotlib, etc. | Varies | Special requirements |

## Step-by-Step Tutorial: Creating a Custom Renderer

### Step 1: Set Up Your File

Create a new Python file in `~/.stream_viewer/plugins/renderers/` with a descriptive name:

```bash
# File: ~/.stream_viewer/plugins/renderers/my_custom_renderer.py
```

**File naming conventions:**
- Use lowercase with underscores (snake_case)
- End with a descriptive suffix: `_pg` (pyqtgraph), `_vis` (vispy), `_mpl` (matplotlib)
- Example: `heatmap_pg.py`, `line_vis.py`, `scatter_mpl.py`

### Step 2: Import Required Modules

```python
import numpy as np
import pyqtgraph as pg  # or your chosen visualization library
from stream_viewer.renderers.data.base import RendererDataTimeSeries  # or other data class
from stream_viewer.renderers.display.pyqtgraph import PGRenderer  # or other display class
```

### Step 3: Define Your Renderer Class

```python
class MyCustomRenderer(RendererDataTimeSeries, PGRenderer):
    """
    Brief description of what your renderer does.
    
    Inherits from:
    - RendererDataTimeSeries: Handles time series data buffering
    - PGRenderer: Provides pyqtgraph display functionality
    """
    
    # Optional: Specify compatible control panels
    COMPAT_ICONTROL = ['TimeSeriesControl']
    
    # Define which parameters should be saved/restored from settings
    gui_kwargs = dict(
        RendererDataTimeSeries.gui_kwargs,
        **PGRenderer.gui_kwargs,
        my_custom_param=float,  # Add your custom parameters here
        another_param=bool
    )
```

**Important notes:**
- Class name should be descriptive and use CamelCase
- Always inherit from a data class first, then a display class
- `gui_kwargs` defines which parameters are persisted to INI files

### Step 4: Implement `__init__` Method

The `__init__` method initializes your renderer and sets up the visualization widget:

```python
def __init__(self,
             # Override inherited parameters if changing defaults
             auto_scale: str = 'none',
             show_chan_labels: bool = True,
             # Add your custom parameters
             my_custom_param: float = 1.0,
             another_param: bool = False,
             **kwargs):
    """
    Initialize the renderer.
    
    Args:
        auto_scale: Auto-scaling mode ('none', 'by-channel', 'by-stream')
        show_chan_labels: Whether to display channel labels
        my_custom_param: Description of your custom parameter
        another_param: Description of another parameter
        **kwargs: Additional parameters passed to parent classes
    """
    # Store custom parameters as instance variables
    self._my_custom_param = my_custom_param
    self._another_param = another_param
    
    # Create the Qt widget that will be displayed
    self._widget = pg.PlotWidget()  # or pg.GraphicsLayoutWidget(), etc.
    
    # Initialize any internal state
    self._curves = []
    self._plot_items = []
    
    # Call parent constructors (CRITICAL - don't forget this!)
    super().__init__(
        auto_scale=auto_scale,
        show_chan_labels=show_chan_labels,
        **kwargs
    )
    
    # Perform initial setup
    self.reset_renderer()
```

**Key points:**
- Store all parameters as instance variables (prefix with `_`)
- Create `self._widget` before calling `super().__init__()`
- Always call `super().__init__(**kwargs)` for cooperative inheritance
- Call `self.reset_renderer()` at the end to build the initial visualization


### Step 5: Implement `reset_renderer` Method

This method rebuilds your visualization when settings change or data sources are added/removed:

```python
def reset_renderer(self, reset_channel_labels=True):
    """
    Rebuild the visualization from scratch.
    
    Called when:
    - Data sources are added or removed
    - Channel visibility changes
    - Display settings change (colors, limits, etc.)
    
    Args:
        reset_channel_labels: If True, rebuild channel labels/legends
    """
    # Clear existing visualization elements
    self._widget.clear()
    self._curves = []
    
    # Check if we have any data to visualize
    if len(self.chan_states) == 0:
        return
    
    # Configure plot appearance
    self._widget.setBackground(self.parse_color_str(self.bg_color))
    self._widget.setYRange(self.lower_limit, self.upper_limit)
    self._widget.setLabel('bottom', 'Time', units='s')
    self._widget.setLabel('left', 'Amplitude')
    
    # Get colormap for channels
    n_visible = self.chan_states['vis'].sum()
    color_map = self.get_colormap(self.color_set, n_visible)
    
    # Create visualization elements for each visible channel
    ch_idx = 0
    for _, ch_state in self.chan_states.iterrows():
        if ch_state.get('vis', True):
            # Create a curve for this channel
            pen = pg.mkPen(color_map[ch_idx], width=2)
            curve = self._widget.plot(pen=pen, name=ch_state['name'])
            self._curves.append(curve)
            ch_idx += 1
    
    # Add legend if showing channel labels
    if self.show_chan_labels and reset_channel_labels:
        self._widget.addLegend()
```

**Key points:**
- Always clear existing elements first
- Check `len(self.chan_states)` before creating visualization elements
- Use `self.chan_states['vis']` to filter visible channels
- Use inherited properties: `self.lower_limit`, `self.upper_limit`, `self.color_set`, `self.bg_color`
- Use inherited methods: `self.get_colormap()`, `self.parse_color_str()`

### Step 6: Implement `update_visualization` Method

This method is called periodically by the timer to update the display with new data:

```python
def update_visualization(self, data: np.ndarray, timestamps: np.ndarray) -> None:
    """
    Update the visualization with new data.
    
    Called automatically by the timer (typically 60 Hz for pyqtgraph).
    
    Args:
        data: List of (data_array, markers_array) tuples, one per data source
        timestamps: List of (data_timestamps, marker_timestamps) tuples
    """
    # Check if we have any data
    if not any([np.any(_) for _ in timestamps[0]]):
        return
    
    # Iterate through each data source
    for src_idx, (src_data, src_ts) in enumerate(zip(data, timestamps)):
        # Unpack data and timestamps
        dat, markers = src_data  # dat: (n_channels, n_samples)
        ts, marker_ts = src_ts
        
        # Skip if no data
        if dat.size == 0:
            continue
        
        # Update each channel's visualization
        for ch_idx, curve in enumerate(self._curves):
            if ch_idx < dat.shape[0]:
                # Update the curve with new data
                curve.setData(ts, dat[ch_idx])
```

**Key points:**
- Data format depends on your data parent class:
  - `RendererDataTimeSeries`: List of `(data, markers)` tuples per source
  - `RendererMergeDataSources`: Single merged array `(n_channels, n_samples)`
- Data is already formatted and optionally auto-scaled by parent classes
- Always check for empty data before processing
- Handle multiple data sources if your renderer supports them

### Step 7: Implement `reset_buffers` Method (Optional)

If you're using `RendererBufferData` or need custom buffering:

```python
def reset_buffers(self):
    """
    Configure data buffers for each data source.
    
    Called by reset() before reset_renderer().
    """
    self._buffers = []
    for src_ix, src in enumerate(self._data_sources):
        src_stats = src.data_stats
        
        # Create a time series buffer
        buffer = TimeSeriesBuffer(
            mode=self.plot_mode,
            srate=src_stats['srate'],
            duration=self._duration,
            indicate_write_index=True
        )
        
        # Get channel count for this source
        this_chans = self.chan_states.loc[self.chan_states['src'] == src.identifier]
        n_chans = this_chans['vis'].sum()
        
        buffer.reset(n_chans)
        self._buffers.append(buffer)
```

**Note**: Most renderers don't need to override this - the parent class handles it.


## Parameter Handling and Settings Persistence

### Defining Parameters with `gui_kwargs`

The `gui_kwargs` class variable defines which parameters should be saved to INI files and restored when the application restarts:

```python
class MyRenderer(RendererDataTimeSeries, PGRenderer):
    gui_kwargs = dict(
        RendererDataTimeSeries.gui_kwargs,  # Inherit parent parameters
        **PGRenderer.gui_kwargs,
        # Add your custom parameters with their types
        line_width=float,
        show_grid=bool,
        plot_style=str,
        point_size=int
    )
```

**Supported types:**
- `float`: Floating-point numbers
- `int`: Integers
- `bool`: Boolean values
- `str`: Strings

### Creating Property Decorators

To make parameters dynamically adjustable through control panels, create properties with getters and setters:

```python
@property
def line_width(self):
    """Get the current line width."""
    return self._line_width

@line_width.setter
def line_width(self, value):
    """Set line width and rebuild visualization."""
    self._line_width = value
    self.reset_renderer(reset_channel_labels=False)
```

**When to call `reset_renderer`:**
- Call with `reset_channel_labels=True` if the change affects channel labels or layout
- Call with `reset_channel_labels=False` for visual changes only (colors, line width, etc.)
- Don't call it if the change only affects future updates (e.g., marker scale)

### Qt Slot Connections

To connect your renderer to control panel widgets, define Qt slots:

```python
from qtpy import QtCore

@QtCore.Slot(float)
def line_width_valueChanged(self, value):
    """Slot for line width slider/spinbox changes."""
    self.line_width = value

@QtCore.Slot(bool)
def show_grid_stateChanged(self, checked):
    """Slot for grid checkbox changes."""
    self.show_grid = checked

@QtCore.Slot(str)
def plot_style_currentTextChanged(self, text):
    """Slot for plot style combo box changes."""
    self.plot_style = text
```

**Naming convention for slots:**
- Format: `{parameter_name}_{signal_name}`
- Common signals: `valueChanged`, `stateChanged`, `currentTextChanged`, `clicked`
- The control panel will automatically connect to these slots if they exist

### Example: Complete Parameter Implementation

```python
class MyRenderer(RendererDataTimeSeries, PGRenderer):
    gui_kwargs = dict(
        RendererDataTimeSeries.gui_kwargs,
        **PGRenderer.gui_kwargs,
        line_width=float,
        show_markers=bool
    )
    
    def __init__(self, line_width: float = 2.0, show_markers: bool = True, **kwargs):
        self._line_width = line_width
        self._show_markers = show_markers
        self._widget = pg.PlotWidget()
        super().__init__(**kwargs)
        self.reset_renderer()
    
    @property
    def line_width(self):
        return self._line_width
    
    @line_width.setter
    def line_width(self, value):
        self._line_width = value
        self.reset_renderer(reset_channel_labels=False)
    
    @QtCore.Slot(float)
    def line_width_valueChanged(self, value):
        self.line_width = value
    
    @property
    def show_markers(self):
        return self._show_markers
    
    @show_markers.setter
    def show_markers(self, value):
        self._show_markers = value
        # No reset needed - only affects future marker rendering
    
    @QtCore.Slot(bool)
    def show_markers_stateChanged(self, checked):
        self.show_markers = checked
```

## File Naming and Directory Structure

### Plugin Directory Structure

```
~/.stream_viewer/
└── plugins/
    ├── renderers/
    │   ├── my_custom_renderer.py
    │   ├── another_renderer.py
    │   └── __init__.py (optional)
    └── widgets/
        ├── my_custom_control.py
        └── __init__.py (optional)
```

### File Naming Conventions

**Renderer files:**
- Use descriptive names: `heatmap_pg.py`, `spectrogram_vis.py`, `polar_mpl.py`
- Suffix indicates library: `_pg` (pyqtgraph), `_vis` (vispy), `_mpl` (matplotlib)
- One renderer class per file (recommended)

**Class naming:**
- Use CamelCase: `HeatmapPG`, `SpectrogramVis`, `PolarMPL`
- Class name should match filename (without suffix): `heatmap_pg.py` → `HeatmapPG`

### Making Renderers Discoverable

The plugin system automatically discovers renderers in:
1. Built-in location: `stream_viewer/renderers/`
2. User plugins: `~/.stream_viewer/plugins/renderers/`
3. Additional directories configured in application settings

**Requirements for discovery:**
- File must be in a discoverable directory
- File must contain a class inheriting from a renderer base class
- Class must implement required methods (`reset_renderer`, `update_visualization`)


## Working with Channel States

The `self.chan_states` DataFrame contains information about all channels from all data sources:

```python
# Example chan_states DataFrame:
#     name        src                          unit  type  pos  vis
# 0   Ch1   {"name":"EEG","type":"EEG"}      µV    EEG   []   True
# 1   Ch2   {"name":"EEG","type":"EEG"}      µV    EEG   []   True
# 2   Acc_X {"name":"IMU","type":"Accel"}   m/s²  Accel []   False
```

### Accessing Channel Information

```python
# Get number of visible channels
n_visible = self.chan_states['vis'].sum()

# Iterate through visible channels only
for idx, ch_state in self.chan_states.iterrows():
    if ch_state.get('vis', True):
        name = ch_state['name']
        unit = ch_state.get('unit', '')
        # ... use channel info

# Filter channels by data source
src_id = self._data_sources[0].identifier
src_channels = self.chan_states[self.chan_states['src'] == src_id]

# Get channel names as list
channel_names = self.chan_states[self.chan_states['vis']]['name'].tolist()
```

### Channel State Columns

- `name`: Channel name (string)
- `src`: Data source identifier (JSON string)
- `unit`: Physical unit (string, optional)
- `type`: Channel type (e.g., 'EEG', 'Accel', 'Markers')
- `pos`: 3D position for spatial channels (list, optional)
- `vis`: Visibility flag (boolean)

## Working with Multiple Data Sources

### Handling Multiple Streams

```python
def update_visualization(self, data, timestamps):
    """Handle data from multiple sources."""
    # Iterate through each data source
    for src_idx, src in enumerate(self._data_sources):
        src_data, src_ts = data[src_idx], timestamps[src_idx]
        dat, markers = src_data
        ts, marker_ts = src_ts
        
        # Get channels for this source
        src_id = src.identifier
        src_channels = self.chan_states[self.chan_states['src'] == src_id]
        
        # Process data for this source
        # ...
```

### Merging Data Sources

If using `RendererMergeDataSources`, data from all sources is automatically merged:

```python
class MyMergedRenderer(RendererMergeDataSources, PGRenderer):
    def update_visualization(self, data, timestamps):
        """Data is already merged across all sources."""
        # data shape: (n_total_channels, n_samples)
        # No need to iterate through sources
        if data.size == 0:
            return
        
        # Use the last sample from each channel
        latest_values = data[:, -1]
        
        # Update visualization with merged data
        # ...
```

## Advanced Topics

### Custom Colormaps

```python
# Use built-in colormap
color_map = self.get_colormap('viridis', n_channels)

# Use solid color
color_map = self.get_colormap('red', n_channels)

# Available colormaps:
# - pyqtgraph gradients: 'thermal', 'flame', 'bipolar', etc.
# - matplotlib colormaps: 'viridis', 'plasma', 'coolwarm', etc.
# - solid colors: 'red', 'green', 'blue', 'cyan', 'magenta', 'yellow'
# - 'random': generates random colors
```

### Auto-Scaling Data

The parent class can automatically scale data:

```python
class MyRenderer(RendererDataTimeSeries, PGRenderer):
    def __init__(self, auto_scale: str = 'by-channel', **kwargs):
        # auto_scale options:
        # - 'none': No scaling (use lower_limit/upper_limit)
        # - 'by-channel': Scale each channel independently to [0, 1]
        # - 'by-stream': Scale all channels in a stream together
        super().__init__(auto_scale=auto_scale, **kwargs)
```

When auto-scaling is enabled, data is automatically scaled to [0, 1] range before reaching `update_visualization`.

### Handling Markers

Marker streams contain event labels instead of numeric data:

```python
def update_visualization(self, data, timestamps):
    for src_idx, (src_data, src_ts) in enumerate(zip(data, timestamps)):
        dat, markers = src_data
        ts, marker_ts = src_ts
        
        # Check if we have markers
        if markers.size > 0:
            # markers: array of strings
            # marker_ts: array of timestamps
            for marker, marker_time in zip(markers, marker_ts):
                # Display marker at the appropriate time
                text = pg.TextItem(text=marker, angle=90)
                text.setPos(marker_time % self.duration, 0)
                self._widget.addItem(text)
```

### Performance Optimization

For high-performance rendering:

1. **Minimize redraws**: Only update changed elements
2. **Use efficient data structures**: Pre-allocate arrays when possible
3. **Batch updates**: Update all curves before triggering a redraw
4. **Consider vispy**: For many channels or high sample rates, use `VispyRenderer`
5. **Limit buffer size**: Use appropriate `duration` parameter

```python
# Example: Efficient curve updates
def update_visualization(self, data, timestamps):
    # Disable auto-range during updates
    self._widget.setAutoVisible(y=False)
    
    # Update all curves
    for ch_idx, curve in enumerate(self._curves):
        curve.setData(timestamps[ch_idx], data[ch_idx])
    
    # Re-enable auto-range
    self._widget.setAutoVisible(y=True)
```


## Testing and Debugging

### Testing Your Renderer

1. **Copy to plugin directory:**
   ```bash
   cp my_custom_renderer.py ~/.stream_viewer/plugins/renderers/
   ```

2. **Start the application:**
   ```bash
   lsl_viewer
   ```

3. **Add your renderer:**
   - Start an LSL stream (or use a test stream)
   - In the application, select your renderer from the available renderers
   - Verify it appears and displays data correctly

### Debugging Techniques

#### Enable Logging

```python
import logging

logger = logging.getLogger(__name__)

class MyRenderer(RendererDataTimeSeries, PGRenderer):
    def reset_renderer(self, reset_channel_labels=True):
        logger.info(f"Resetting renderer with {len(self.chan_states)} channels")
        # ... rest of implementation
    
    def update_visualization(self, data, timestamps):
        logger.debug(f"Received data shape: {data[0][0].shape if data else 'empty'}")
        # ... rest of implementation
```

Run the application with debug logging:
```bash
python -m stream_viewer.applications.main --log-level DEBUG
```

#### Common Issues and Solutions

**Issue: Renderer doesn't appear in the application**
- Check file is in `~/.stream_viewer/plugins/renderers/`
- Verify class inherits from renderer base classes
- Check for syntax errors in your file
- Look for errors in application console output

**Issue: `AttributeError: 'MyRenderer' object has no attribute '_widget'`**
- Ensure you create `self._widget` before calling `super().__init__()`
- Check that `_widget` is assigned in `__init__`

**Issue: Visualization doesn't update**
- Verify `update_visualization` is implemented
- Check that timer is started (parent class handles this)
- Ensure data is not empty: add logging to check data shape
- Verify you're not blocking the Qt event loop

**Issue: Application crashes when changing settings**
- Check property setters call `reset_renderer` correctly
- Ensure `reset_renderer` handles empty `chan_states`
- Verify all Qt objects are properly cleaned up in `reset_renderer`

**Issue: Settings not persisted**
- Verify parameters are in `gui_kwargs`
- Check parameter names match between `__init__`, properties, and `gui_kwargs`
- Ensure types in `gui_kwargs` match actual parameter types

#### Interactive Testing

Use IPython or Jupyter for interactive testing:

```python
from stream_viewer.renderers.my_custom_renderer import MyRenderer
from stream_viewer.data.stream_lsl import LSLDataSource
from qtpy import QtWidgets
import sys

# Create Qt application
app = QtWidgets.QApplication(sys.argv)

# Create renderer
renderer = MyRenderer()

# Add a data source (requires running LSL stream)
source = LSLDataSource(stream_name="TestStream")
renderer.add_source(source)

# Show the widget
renderer.native_widget.show()

# Start Qt event loop
app.exec_()
```

### Unit Testing

Create tests for your renderer logic:

```python
import unittest
import numpy as np
from my_custom_renderer import MyRenderer

class TestMyRenderer(unittest.TestCase):
    def setUp(self):
        self.renderer = MyRenderer()
    
    def test_initialization(self):
        """Test renderer initializes correctly."""
        self.assertIsNotNone(self.renderer._widget)
        self.assertEqual(len(self.renderer._curves), 0)
    
    def test_reset_with_channels(self):
        """Test reset_renderer creates curves for channels."""
        # Mock channel states
        self.renderer._chan_states = pd.DataFrame([
            {'name': 'Ch1', 'src': '{}', 'vis': True},
            {'name': 'Ch2', 'src': '{}', 'vis': True}
        ])
        
        self.renderer.reset_renderer()
        self.assertEqual(len(self.renderer._curves), 2)
    
    def test_parameter_persistence(self):
        """Test parameters are in gui_kwargs."""
        self.assertIn('line_width', MyRenderer.gui_kwargs)
        self.assertEqual(MyRenderer.gui_kwargs['line_width'], float)

if __name__ == '__main__':
    unittest.main()
```

## Real-World Examples

For detailed, annotated walkthroughs of production renderers, see the [Annotated Examples](annotated-examples.md) guide, which covers:

- **BarPG**: Simple bar chart renderer (beginner-friendly)
- **LinePG**: Advanced multi-plot time series renderer
- **LineVis**: High-performance GPU-accelerated renderer
- **PyQtGraph vs. Vispy**: Detailed comparison and when to use each
- **Performance optimization**: Real-time rendering techniques
- **Settings persistence**: Complete configuration patterns

## Complete Example: Bar Chart Renderer

Here's a complete, annotated example of a simple bar chart renderer:

```python
"""
Bar Chart Renderer - Displays the most recent value from each channel as a bar.

File: bar_chart_simple.py
Location: ~/.stream_viewer/plugins/renderers/
"""

import numpy as np
import pyqtgraph as pg
from qtpy import QtCore
from stream_viewer.renderers.data.base import RendererMergeDataSources
from stream_viewer.renderers.display.pyqtgraph import PGRenderer


class BarChartSimple(RendererMergeDataSources, PGRenderer):
    """
    Simple bar chart showing the latest value from each channel.
    
    Uses RendererMergeDataSources to combine all data sources into a single array.
    """
    
    # Compatible control panels
    COMPAT_ICONTROL = ['BarControlPanel']
    
    # Parameters to save/restore
    gui_kwargs = dict(
        RendererMergeDataSources.gui_kwargs,
        **PGRenderer.gui_kwargs,
        bar_width=float
    )
    
    def __init__(self, bar_width: float = 0.6, **kwargs):
        """
        Initialize bar chart renderer.
        
        Args:
            bar_width: Width of bars (0.0 to 1.0)
            **kwargs: Additional parameters for parent classes
        """
        self._bar_width = bar_width
        self._bar_item = None
        
        # Create the plot widget
        self._widget = pg.PlotWidget()
        
        # Call parent constructors
        super().__init__(**kwargs)
        
        # Build initial visualization
        self.reset_renderer()
    
    def reset_renderer(self, reset_channel_labels=True):
        """Rebuild the bar chart."""
        # Remove existing bar item
        if self._bar_item is not None:
            self._widget.removeItem(self._bar_item)
            self._bar_item = None
        
        # Check if we have channels
        if len(self.chan_states) == 0:
            return
        
        # Configure plot
        self._widget.setYRange(self.lower_limit, self.upper_limit, padding=0.05)
        self._widget.setLabel('left', 'Amplitude')
        self._widget.setLabel('bottom', 'Channel')
        
        # Get visible channels
        n_visible = self.chan_states['vis'].sum()
        x_positions = np.arange(n_visible)
        y_values = np.zeros(n_visible)
        
        # Get colors for bars
        color_map = self.get_colormap(self.color_set, n_visible)
        
        # Create bar graph item
        self._bar_item = pg.BarGraphItem(
            x=x_positions,
            height=y_values,
            width=self.bar_width,
            brushes=color_map
        )
        self._widget.addItem(self._bar_item)
        
        # Set channel labels on x-axis
        if reset_channel_labels:
            channel_names = self.chan_states[self.chan_states['vis']]['name'].tolist()
            ticks = [list(enumerate(channel_names))]
            self._widget.getAxis('bottom').setTicks(ticks)
    
    def update_visualization(self, data: np.ndarray, timestamps: np.ndarray) -> None:
        """Update bar heights with latest data."""
        if data.size == 0:
            return
        
        # Get the last sample from each channel
        latest_values = data[:, -1]
        
        # Update bar heights
        if self._bar_item is not None:
            self._bar_item.setOpts(height=latest_values)
    
    # Property for bar_width with persistence
    @property
    def bar_width(self):
        return self._bar_width
    
    @bar_width.setter
    def bar_width(self, value):
        self._bar_width = np.clip(value, 0.1, 1.0)
        self.reset_renderer(reset_channel_labels=False)
    
    @QtCore.Slot(float)
    def bar_width_valueChanged(self, value):
        self.bar_width = value
```


## Common Patterns from Existing Renderers

### Pattern 1: Multi-Plot Layout (LinePG)

When you need multiple plots stacked vertically (one per data source):

```python
def reset_renderer(self, reset_channel_labels=True):
    # Use GraphicsLayoutWidget for multiple plots
    self._widget = pg.GraphicsLayoutWidget()
    self._widget.clear()
    
    # Create one plot per data source
    for src_idx, src in enumerate(self._data_sources):
        # Add plot to layout
        plot_widget = self._widget.addPlot(row=src_idx, col=0)
        
        # Configure plot
        plot_widget.setLabel('bottom', 'Time', units='s')
        plot_widget.showGrid(x=True, y=True, alpha=0.3)
        
        # Add curves for each channel in this source
        src_channels = self.chan_states[self.chan_states['src'] == src.identifier]
        for ch_idx, ch_state in src_channels.iterrows():
            if ch_state['vis']:
                curve = plot_widget.plot(pen=pg.mkPen(width=2))
                # Store curve with source index for later updates
```

### Pattern 2: Sweep vs. Scroll Mode

Implementing different plotting modes:

```python
def update_visualization(self, data, timestamps):
    for src_idx, (src_data, src_ts) in enumerate(zip(data, timestamps)):
        dat, _ = src_data
        ts, _ = src_ts
        
        if self.plot_mode.lower() == 'sweep':
            # Wrap time to create sweep effect
            x_data = ts % self.duration
        else:  # scroll mode
            # Shift x-axis to keep latest data on right
            x_data = ts - ts[-1] + self.duration
        
        # Update curves
        for ch_idx, curve in enumerate(self._curves):
            curve.setData(x_data, dat[ch_idx])
```

### Pattern 3: Channel Offsetting

Displaying multiple channels without overlap:

```python
def reset_renderer(self, reset_channel_labels=True):
    n_visible = self.chan_states['vis'].sum()
    
    if self.offset_channels and n_visible > 1:
        # Set y-range to accommodate all channels
        self._widget.setYRange(-0.5, n_visible - 0.5)
        
        # Create curves with vertical offsets
        for ch_idx, ch_state in enumerate(visible_channels):
            curve = self._widget.plot(pen=pg.mkPen(width=2))
            curve.setPos(0, ch_idx)  # Vertical offset
            self._curves.append(curve)
    else:
        # Overlapping mode
        self._widget.setYRange(self.lower_limit, self.upper_limit)
        for ch_state in visible_channels:
            curve = self._widget.plot(pen=pg.mkPen(width=2))
            self._curves.append(curve)
```

### Pattern 4: Legends and Labels

Adding informative legends:

```python
def reset_renderer(self, reset_channel_labels=True):
    # Create legend with semi-transparent background
    if self.show_chan_labels:
        legend_bg = QtGui.QColor(self.bg_color)
        legend_bg.setAlphaF(0.5)
        legend = pg.LegendItem(offset=(0, 1), brush=legend_bg)
        legend.setParentItem(self._widget.plotItem)
        
        # Add items to legend
        for curve, ch_name in zip(self._curves, channel_names):
            legend.addItem(curve, name=ch_name)
```

### Pattern 5: Dynamic Y-Axis Synchronization

Ensuring consistent axis widths across multiple plots:

```python
def sync_y_axes(self):
    """Synchronize y-axis widths across all plots."""
    max_width = 0
    
    # Find maximum axis width
    for row_idx in range(len(self._data_sources)):
        plot_widget = self._widget.getItem(row_idx, 0)
        if plot_widget:
            y_axis = plot_widget.getAxis('left')
            max_width = max(max_width, y_axis.minimumWidth())
    
    # Apply to all plots
    for row_idx in range(len(self._data_sources)):
        plot_widget = self._widget.getItem(row_idx, 0)
        if plot_widget:
            plot_widget.getAxis('left').setWidth(max_width)

def update_visualization(self, data, timestamps):
    # Sync axes on first update
    if self._needs_sync:
        self.sync_y_axes()
        self._needs_sync = False
    
    # ... rest of update logic
```

## Differences Between Visualization Libraries

### PyQtGraph vs. Vispy

| Feature | PyQtGraph | Vispy |
|---------|-----------|-------|
| **Performance** | Good for <100 channels | Excellent for 100+ channels |
| **Ease of Use** | Simple, high-level API | More complex, lower-level |
| **2D Plotting** | Excellent | Good |
| **3D Rendering** | Limited | Excellent |
| **GPU Acceleration** | Minimal | Full OpenGL |
| **Learning Curve** | Gentle | Steep |

### When to Use Each

**Use PyQtGraph when:**
- Creating simple 2D plots (line, bar, scatter)
- Working with moderate channel counts (<50)
- You want rapid development
- You need interactive features (zoom, pan, legends)

**Use Vispy when:**
- Rendering many channels (>100)
- Creating 3D visualizations
- Performance is critical
- You need custom shaders or GPU effects

### Example: Vispy Renderer Structure

```python
from vispy import scene
from stream_viewer.renderers.data.base import RendererDataTimeSeries
from stream_viewer.renderers.display.vispy import VispyRenderer

class MyVispyRenderer(RendererDataTimeSeries, VispyRenderer):
    def __init__(self, **kwargs):
        # Create vispy canvas
        self._canvas = scene.SceneCanvas(keys='interactive')
        self._view = self._canvas.central_widget.add_view()
        
        # VispyRenderer expects _widget to be the canvas
        self._widget = self._canvas.native
        
        super().__init__(**kwargs)
        self.reset_renderer()
    
    def reset_renderer(self, reset_channel_labels=True):
        # Clear existing visuals
        self._view.scene.children.clear()
        
        # Create line visuals using vispy
        from vispy.scene import Line
        
        for ch_idx in range(n_visible):
            line = Line(parent=self._view.scene)
            # Configure line...
```


## Common Pitfalls and Troubleshooting

### Pitfall 1: Forgetting `super().__init__()`

**Problem:**
```python
class MyRenderer(RendererDataTimeSeries, PGRenderer):
    def __init__(self, **kwargs):
        self._widget = pg.PlotWidget()
        # Forgot to call super().__init__(**kwargs)
        self.reset_renderer()
```

**Symptoms:**
- Renderer doesn't receive data updates
- Timer doesn't start
- Properties from parent classes are missing

**Solution:**
Always call `super().__init__(**kwargs)` in cooperative inheritance:
```python
def __init__(self, **kwargs):
    self._widget = pg.PlotWidget()
    super().__init__(**kwargs)  # CRITICAL!
    self.reset_renderer()
```

### Pitfall 2: Creating `_widget` After `super().__init__()`

**Problem:**
```python
def __init__(self, **kwargs):
    super().__init__(**kwargs)
    self._widget = pg.PlotWidget()  # Too late!
```

**Symptoms:**
- `AttributeError: 'MyRenderer' object has no attribute '_widget'`
- Application crashes on startup

**Solution:**
Create `self._widget` BEFORE calling `super().__init__()`:
```python
def __init__(self, **kwargs):
    self._widget = pg.PlotWidget()  # Create first
    super().__init__(**kwargs)
```

### Pitfall 3: Not Checking for Empty `chan_states`

**Problem:**
```python
def reset_renderer(self, reset_channel_labels=True):
    self._widget.clear()
    # Assumes chan_states has data
    n_visible = self.chan_states['vis'].sum()
    color_map = self.get_colormap(self.color_set, n_visible)
```

**Symptoms:**
- Crashes when no data sources are connected
- Errors during initialization

**Solution:**
Always check if `chan_states` is empty:
```python
def reset_renderer(self, reset_channel_labels=True):
    self._widget.clear()
    
    if len(self.chan_states) == 0:
        return  # Nothing to render yet
    
    n_visible = self.chan_states['vis'].sum()
    # ... continue with setup
```

### Pitfall 4: Incorrect Buffer Type Selection

**Problem:**
Using `RendererDataTimeSeries` for a snapshot visualization (bar chart, radar plot):

**Symptoms:**
- Excessive memory usage
- Slow performance
- Unnecessary buffering of historical data

**Solution:**
Choose the appropriate data parent class:
- Time series plots → `RendererDataTimeSeries`
- Snapshot visualizations → `RendererMergeDataSources`
- Custom needs → `RendererBufferData`

### Pitfall 5: Blocking the Qt Event Loop

**Problem:**
```python
def update_visualization(self, data, timestamps):
    # Heavy computation in update method
    for i in range(1000000):
        result = complex_calculation(data)
    # Update visualization
```

**Symptoms:**
- UI becomes unresponsive
- Visualization stutters or freezes
- Application appears to hang

**Solution:**
Keep `update_visualization` fast:
```python
def update_visualization(self, data, timestamps):
    # Do minimal work here
    if data.size > 0:
        # Quick update only
        for ch_idx, curve in enumerate(self._curves):
            curve.setData(timestamps, data[ch_idx])
    
    # For heavy computation, use a separate thread or process
```

### Pitfall 6: Mismatched Parameter Names

**Problem:**
```python
gui_kwargs = {'line_width': float}

def __init__(self, lineWidth: float = 2.0, **kwargs):  # Different name!
    self._line_width = lineWidth
```

**Symptoms:**
- Settings not saved/restored correctly
- Control panel connections fail
- Parameters reset to defaults on restart

**Solution:**
Use consistent naming everywhere:
```python
gui_kwargs = {'line_width': float}

def __init__(self, line_width: float = 2.0, **kwargs):  # Matches!
    self._line_width = line_width

@property
def line_width(self):  # Matches!
    return self._line_width
```

### Pitfall 7: Not Handling Multiple Data Sources

**Problem:**
```python
def update_visualization(self, data, timestamps):
    # Assumes single data source
    dat, markers = data
    ts, marker_ts = timestamps
```

**Symptoms:**
- Crashes when multiple streams are added
- `ValueError: too many values to unpack`

**Solution:**
Always iterate through data sources:
```python
def update_visualization(self, data, timestamps):
    # data and timestamps are lists
    for src_idx, (src_data, src_ts) in enumerate(zip(data, timestamps)):
        dat, markers = src_data
        ts, marker_ts = src_ts
        # Process each source
```

### Pitfall 8: Incorrect Property Setter Behavior

**Problem:**
```python
@property
def line_width(self):
    return self._line_width

@line_width.setter
def line_width(self, value):
    self._line_width = value
    # Forgot to call reset_renderer()
```

**Symptoms:**
- Changes don't take effect until manual refresh
- UI controls don't update visualization

**Solution:**
Call `reset_renderer()` when visual changes are needed:
```python
@line_width.setter
def line_width(self, value):
    self._line_width = value
    self.reset_renderer(reset_channel_labels=False)
```

### Troubleshooting Checklist

When your renderer isn't working:

- [ ] Is `self._widget` created before `super().__init__()`?
- [ ] Did you call `super().__init__(**kwargs)`?
- [ ] Does `reset_renderer` check for empty `chan_states`?
- [ ] Are parameter names consistent in `gui_kwargs`, `__init__`, and properties?
- [ ] Is the file in the correct plugin directory?
- [ ] Does the class inherit from both a data and display parent?
- [ ] Are all required methods implemented (`reset_renderer`, `update_visualization`)?
- [ ] Is `update_visualization` fast and non-blocking?
- [ ] Are you handling multiple data sources correctly?
- [ ] Check the console for error messages and stack traces

## Next Steps

### Creating a Control Panel Widget

Once you have a working renderer, you may want to create a custom control panel to expose parameters to users. See the [Widget Development Guide](../widgets/development-guide.md) for details.

### Distributing Your Renderer

To share your renderer with others:

1. **As a standalone file:**
   - Share the `.py` file
   - Users copy it to `~/.stream_viewer/plugins/renderers/`

2. **As a Python package:**
   ```python
   # setup.py
   from setuptools import setup
   
   setup(
       name='streamviewer-custom-renderers',
       version='1.0.0',
       packages=['streamviewer_custom_renderers'],
       install_requires=['stream_viewer>=1.0.0'],
       entry_points={
           'stream_viewer.renderers': [
               'my_renderer = streamviewer_custom_renderers.my_renderer:MyRenderer',
           ]
       }
   )
   ```

3. **Contributing to StreamViewer:**
   - Fork the repository
   - Add your renderer to `stream_viewer/renderers/`
   - Submit a pull request

### Additional Resources

- [Architecture Documentation](architecture.md) - Detailed system architecture
- [Widget Development Guide](../widgets/development-guide.md) - Creating control panels
- [StreamViewer API Reference](../../README.md) - Complete API documentation
- [PyQtGraph Documentation](https://pyqtgraph.readthedocs.io/) - PyQtGraph reference
- [Vispy Documentation](https://vispy.org/) - Vispy reference

## Summary

Creating a custom renderer involves:

1. **Choose base classes**: Select appropriate data and display parent classes
2. **Implement `__init__`**: Create widget, call `super().__init__()`, initialize
3. **Implement `reset_renderer`**: Build/rebuild visualization structure
4. **Implement `update_visualization`**: Update display with new data
5. **Add parameters**: Define in `gui_kwargs`, create properties and slots
6. **Test thoroughly**: Use logging, handle edge cases, test with real streams
7. **Deploy**: Copy to plugin directory or package for distribution

With these fundamentals, you can create powerful custom visualizations tailored to your specific data analysis needs. Happy coding!
