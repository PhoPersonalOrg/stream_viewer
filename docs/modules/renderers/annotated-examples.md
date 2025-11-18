# Annotated Examples from Existing Renderers

This guide provides detailed walkthroughs of real renderers from the StreamViewer codebase, highlighting key patterns, best practices, and implementation techniques. By studying these examples, you'll learn how to implement complex features in your own renderers.

## Overview

We'll examine three renderers that demonstrate different approaches and complexity levels:

1. **BarPG** - Simple snapshot visualization (beginner-friendly)
2. **LinePG** - Complex multi-plot time series renderer (advanced)
3. **LineVis** - High-performance GPU-accelerated renderer (vispy)

Each example is annotated with explanations of key decisions, patterns, and techniques.

---

## Example 1: BarPG - Simple Bar Chart Renderer

The BarPG renderer is an excellent starting point for understanding renderer development. It displays the most recent value from each channel as a bar chart.

### Key Characteristics

- **Data Parent**: `RendererMergeDataSources` - Merges all data sources into a single array
- **Display Parent**: `PGRenderer` - Uses pyqtgraph for visualization
- **Complexity**: Low - Simple snapshot visualization
- **Use Case**: Displaying current values, not historical data

### Complete Annotated Code

```python
from qtpy import QtCore
from stream_viewer.renderers.data.base import RendererMergeDataSources
from stream_viewer.renderers.display.pyqtgraph import PGRenderer
import pyqtgraph as pg
from pyqtgraph.widgets.PlotWidget import PlotWidget
import numpy as np


class BarPG(RendererMergeDataSources, PGRenderer):
    # ============================================================================
    # CLASS VARIABLES
    # ============================================================================
    
    # COMPAT_ICONTROL specifies which control panel widgets work with this renderer
    # This allows the application to show only compatible control panels
    COMPAT_ICONTROL = ['BarControlPanel']
    
    # gui_kwargs defines which parameters should be persisted to INI files
    # We inherit parameters from both parent classes and add our own
    gui_kwargs = dict(RendererMergeDataSources.gui_kwargs, **{'bar_width': float})
    
    # ============================================================================
    # INITIALIZATION
    # ============================================================================
    
    def __init__(self,
                 # Inherited parameters (only list if overriding defaults)
                 show_chan_labels=True,
                 color_set='viridis',
                 # New parameters specific to this renderer
                 bar_width: float = 6,
                 **kwargs):
        """
        Simple bar plot using pyqtgraph.
        
        Args:
            show_chan_labels: Whether to show channel names on x-axis
            color_set: Colormap name for bar colors
            bar_width: Width of bars (scaled by 0.1 internally)
            **kwargs: Additional parameters passed to parent classes
        """
        # Store instance variables
        self._bar = None  # Will hold the BarGraphItem
        self._bar_width = bar_width
        
        # CRITICAL: Create the widget BEFORE calling super().__init__()
        # The parent class expects self._widget to exist
        self._widget = PlotWidget()
        
        # Call parent constructors using cooperative inheritance
        # This initializes data buffers, timers, and other infrastructure
        super().__init__(color_set=color_set, show_chan_labels=show_chan_labels, **kwargs)
        
        # Build the initial visualization
        self.reset_renderer()

    # ============================================================================
    # CORE RENDERER METHODS
    # ============================================================================
    
    def reset_renderer(self, reset_channel_labels=True):
        """
        Rebuild the visualization from scratch.
        
        Called when:
        - Renderer is first initialized
        - Data sources are added/removed
        - Channel visibility changes
        - Display settings change
        
        Args:
            reset_channel_labels: If True, rebuild x-axis labels
        """
        # Clean up existing visualization elements
        if self._bar is not None:
            self._widget.removeItem(self._bar)
        
        # Set the y-axis range to match the configured limits
        # padding=0.05 adds 5% padding above/below for visual clarity
        self._widget.setYRange(self.lower_limit, self.upper_limit, padding=0.05)
        
        # Only create bars if we have channels to display
        if len(self.chan_states) > 0:
            # Count visible channels
            n_vis = self.chan_states['vis'].sum()
            
            # Create x positions (0, 1, 2, ...) for each bar
            x = np.arange(n_vis, dtype=int)
            
            # Initialize bar heights to zero
            y = np.zeros_like(x, dtype=float)
            
            # Get colors for each bar from the colormap
            color_map = self.get_colormap(self.color_set, len(self.chan_states))
            
            # Create the bar graph item
            # Note: bar_width is divided by 10 to scale it appropriately
            self._bar = pg.BarGraphItem(
                x=x, 
                height=y, 
                width=self.bar_width/10, 
                brushes=color_map
            )
            self._widget.addItem(self._bar)
            
            # Set up x-axis labels if requested
            if reset_channel_labels:
                xax = self._widget.getAxis('bottom')
                if self.show_chan_labels:
                    # Get channel names for visible channels
                    chan_labels = self.chan_states[self.chan_states['vis']]['name']
                    # Create ticks: [(position, label), ...]
                    ticks = [list(zip(range(len(chan_labels)), chan_labels))]
                else:
                    # Use numeric labels if not showing channel names
                    ticks = list(range(n_vis))
                    ticks = [[(_, str(_)) for _ in ticks]]
                xax.setTicks(ticks)
    
    def update_visualization(self, data: np.ndarray, timestamps: np.ndarray) -> None:
        """
        Update the bar heights with new data.
        
        This method is called automatically by the timer (typically 60 Hz).
        
        Args:
            data: Merged data array with shape (n_channels, n_samples)
                  Because we use RendererMergeDataSources, all data sources
                  are already combined into a single array
            timestamps: Timestamps for the data samples
        """
        # Check if we have any data
        if timestamps.size == 0:
            return
        
        # Extract the most recent sample from each channel
        # data shape: (n_channels, n_samples), so data[:, -1] gets last sample
        data = data[:, -1]
        
        # Handle case where chan_states was updated but data hasn't caught up yet
        # This can happen right after a new data source is added
        n_vis = self.chan_states['vis'].sum()
        if n_vis > data.size:
            # Pad with zeros for missing channels
            data = np.hstack((data, np.zeros((n_vis - data.size),)))
        
        # Update the bar heights
        # Note: We don't need to scale data because y-axis is set to lower_limit/upper_limit
        self._bar.setOpts(height=data)

    # ============================================================================
    # PROPERTIES AND SLOTS FOR SETTINGS PERSISTENCE
    # ============================================================================
    
    @property
    def bar_width(self):
        """Get the current bar width."""
        return self._bar_width
    
    @bar_width.setter
    def bar_width(self, value):
        """
        Set bar width and rebuild visualization.
        
        This setter is called when:
        - Settings are restored from INI file on startup
        - User changes the value through a control panel
        - Code sets the property directly
        """
        self._bar_width = value
        # Rebuild visualization with new width
        # reset_channel_labels=False because width doesn't affect labels
        self.reset_renderer(reset_channel_labels=False)
    
    @QtCore.Slot(int)
    def slider_widthChanged(self, new_width_val):
        """
        Qt slot for connecting to a slider widget.
        
        This method is automatically discovered and connected by the control panel
        if a slider named 'slider_width' exists in the control panel.
        
        Args:
            new_width_val: New width value from the slider
        """
        self.bar_width = new_width_val
```

### Key Takeaways from BarPG

1. **Simple Data Model**: Uses `RendererMergeDataSources` because it only needs the latest value, not historical data
2. **Clean Separation**: Widget creation, initialization, and visualization are clearly separated
3. **Defensive Programming**: Handles edge cases like missing data or channels being added
4. **Settings Persistence**: Property + slot pattern enables both programmatic and UI control
5. **Efficient Updates**: Only updates bar heights, doesn't rebuild entire visualization

---

## Example 2: LinePG - Advanced Multi-Plot Time Series Renderer

LinePG is a sophisticated renderer that demonstrates advanced patterns for handling multiple data sources, complex layouts, and rich configuration options.

### Key Characteristics

- **Data Parent**: `RendererDataTimeSeries` - Maintains time series buffers
- **Display Parent**: `PGRenderer` - Uses pyqtgraph
- **Complexity**: High - Multiple plots, markers, auto-scaling, channel offsetting
- **Use Case**: Professional time series visualization with many configuration options

### Architecture Overview

LinePG creates a separate plot for each data source, stacked vertically. Each plot can display multiple channels either overlapping or offset vertically.

### Annotated Key Sections

#### 1. Class Definition and Configuration

```python
class LinePG(RendererDataTimeSeries, PGRenderer):
    # Define available plot modes
    plot_modes = ["Sweep", "Scroll"]
    
    # Extensive gui_kwargs for rich configuration
    gui_kwargs = dict(
        RendererDataTimeSeries.gui_kwargs,  # Inherit parent parameters
        **PGRenderer.gui_kwargs,
        # Add renderer-specific parameters
        offset_channels=bool,      # Separate channels vertically
        reset_colormap=bool,       # Reset colors per data source
        line_width=float,          # Line thickness
        antialias=bool,            # Anti-aliasing toggle
        ylabel_as_title=bool,      # Use title instead of y-label
        ylabel_width=int           # Force minimum y-axis width
    )
```

**Pattern**: Extensive configuration options make the renderer flexible for different use cases.

#### 2. Initialization with Complex State

```python
def __init__(self,
             auto_scale: str = 'none',
             show_chan_labels: bool = True,
             color_set: str = 'viridis',
             offset_channels: bool = True,
             reset_colormap: bool = False,
             line_width: float = 2.0,
             antialias: bool = True,
             ylabel_as_title: bool = False,
             ylabel_width: int = None,
             ylabel: str = None,
             **kwargs):
    # Store all configuration
    self._offset_channels = offset_channels
    self._reset_colormap = reset_colormap
    self._line_width = line_width
    self._antialias = antialias
    self._ylabel_as_title = ylabel_as_title
    self._ylabel_width = ylabel_width
    self._ylabel = ylabel
    self._requested_auto_scale = auto_scale.lower()
    
    # Use GraphicsLayoutWidget for multi-plot layout
    self._widget = pg.GraphicsLayoutWidget()
    
    # Initialize marker tracking
    self._do_yaxis_sync = False
    self._src_last_marker_time = []
    self.marker_texts_pool = deque()  # Reuse marker text objects
    self._marker_info = deque()
    self._t_expired = -np.inf
    
    super().__init__(show_chan_labels=show_chan_labels, color_set=color_set, **kwargs)
    self.reset_renderer()
```

**Patterns**:
- **Object Pooling**: `marker_texts_pool` reuses text objects for performance
- **State Tracking**: Multiple flags track complex state (y-axis sync, marker times)
- **GraphicsLayoutWidget**: Enables multi-plot layouts


#### 3. Complex reset_renderer Logic

```python
def reset_renderer(self, reset_channel_labels=True):
    # Clear all existing plots
    self._widget.clear()
    self._widget.setBackground(self.parse_color_str(self.bg_color))
    self._src_last_marker_time = [-np.inf for _ in range(len(self._data_sources))]
    
    # Early return if no channels
    if len(self.chan_states) == 0:
        return
    
    # Calculate colormap size based on reset_colormap setting
    chans_per_src = self.chan_states.loc[self.chan_states['vis']].groupby('src')['name'].nunique().values
    n_chans_colormap = np.max(chans_per_src) if self.reset_colormap else np.sum(chans_per_src)
    color_map = self.get_colormap(self.color_set, n_chans_colormap)
    
    # Configure label styling
    labelStyle = {'color': '#FFF', 'font-size': str(self.font_size) + 'pt'}
    
    # Intelligent auto-scale decision
    if self._requested_auto_scale == 'all' and (not self.offset_channels or np.all(chans_per_src <= 1)):
        # Can rely on pyqtgraph's auto-scaling in this case
        self._auto_scale = 'none'
    else:
        self._auto_scale = self._requested_auto_scale
```

**Patterns**:
- **Smart Defaults**: Automatically chooses optimal auto-scale mode
- **Colormap Strategy**: Can reset colors per source or use continuous colormap
- **Early Returns**: Handles edge cases gracefully

#### 4. Per-Source Plot Creation

```python
    row_offset = -1
    ch_offset_color = -1
    last_row = 0
    
    for src_ix, src in enumerate(self._data_sources):
        # Get channels for this source
        ch_states = self.chan_states[self.chan_states['src'] == src.identifier]
        n_vis_src = ch_states['vis'].sum()
        
        if n_vis_src == 0:
            continue  # Skip sources with no visible channels
        
        offset_chans = self.offset_channels and n_vis_src > 1
        
        # Get buffer info for time vector
        buff = self._buffers[src_ix]
        n_samples = buff._data.shape[-1]
        t_vec = np.arange(n_samples, dtype=float)
        if src.data_stats['srate'] > 0:
            t_vec /= src.data_stats['srate']  # Convert to seconds
        
        # Create plot for this source
        row_offset += 1
        pw = self._widget.addPlot(row=row_offset, col=0, antialias=self._antialias)
        last_row = row_offset
```

**Patterns**:
- **Per-Source Plots**: Each data source gets its own plot
- **Flexible Layout**: Uses row/column grid system
- **Time Vector Calculation**: Converts sample indices to time in seconds


#### 5. Legend and Label Management

```python
        # Create legend if showing labels and channels aren't offset
        if self.show_chan_labels and not offset_chans:
            legend_bg = QtGui.QColor(self.bg_color)
            legend_bg.setAlphaF(0.5)  # Semi-transparent background
            legend = pg.LegendItem(offset=(0, 1), brush=legend_bg)
            legend.setParentItem(pw)
        else:
            legend = None
        
        # Configure plot appearance
        pw.showGrid(x=True, y=True, alpha=0.3)
        font = QtGui.QFont()
        font.setPointSize(self.font_size - 2)
        pw.setXRange(0, self.duration)
        pw.getAxis("bottom").setTickFont(font)
        pw.getAxis("bottom").setStyle(showValues=self.ylabel_as_title)
        
        # Set y-axis label with unit if available
        yax = pw.getAxis('left')
        yax.setTickFont(font)
        stream_ylabel = json.loads(src.identifier)['name']
        if 'unit' in ch_states and ch_states['unit'].nunique() == 1:
            stream_ylabel = stream_ylabel + ' (%s)' % ch_states['unit'].iloc[0]
        pw.setLabel('top' if self.ylabel_as_title else 'left', self._ylabel or stream_ylabel, **labelStyle)
```

**Patterns**:
- **Conditional Legend**: Only shows legend when appropriate
- **Unit Handling**: Automatically includes units in labels when available
- **Flexible Label Placement**: Can use title or y-axis label

#### 6. Advanced Y-Axis Configuration

```python
        # Configure y-range based on auto-scale and offset settings
        if (n_vis_src <= 1 and self._requested_auto_scale != 'none') \
                or (self._requested_auto_scale == 'all' and not offset_chans):
            # Rely on pyqtgraph's auto-range
            pw.enableAutoRange(axis='y')
        elif self._auto_scale == 'none' and not offset_chans:
            # Fixed range
            pw.setYRange(self.lower_limit, self.upper_limit)
        else:
            # Custom range with channel offsets
            major_ticks = []
            minor_ticks = []
            if offset_chans:
                pw.setYRange(-0.5, n_vis_src - 0.5)
                chan_ticks = list(zip(range(n_vis_src), ch_states['name']))
                if self._auto_scale == 'none':
                    # Show both channel names and data range
                    data_ticks = [(-0.5, str(self.lower_limit)), (0.5, self.upper_limit)]
                    data_ticks += [(_ + 0.5, '') for _ in range(1, n_vis_src)]
                else:
                    data_ticks = []
                if self.show_chan_labels:
                    major_ticks = chan_ticks
                    minor_ticks = data_ticks
                else:
                    major_ticks = data_ticks
            else:
                pw.setYRange(-0.5, 0.5)
            yax.setTicks([major_ticks, minor_ticks])
```

**Patterns**:
- **Multiple Y-Axis Modes**: Handles auto-range, fixed range, and offset modes
- **Custom Tick Labels**: Shows channel names as y-axis ticks when offsetting
- **Dual Tick Levels**: Uses major and minor ticks for different information


#### 7. Curve Creation with Positioning

```python
        ch_offset_row = -1
        for ch_ix, ch_state in ch_states.iterrows():
            if ch_state['vis']:
                ch_offset_row += 1
                ch_offset_color = ch_offset_row if self.reset_colormap else (ch_offset_color + 1)
                
                # Create pen with color and width
                pen = pg.mkPen(color_map[ch_offset_color], width=self.line_width)
                
                # Create curve with initial data
                curve = pg.PlotCurveItem(
                    t_vec, 
                    buff._data[0], 
                    connect='finite',  # Don't connect NaN values
                    pen=pen, 
                    name=ch_state['name']
                )
                
                # Position curve vertically if offsetting channels
                curve.setPos(0, ch_offset_row if offset_chans else 0)
                pw.addItem(curve)
                
                # Add to legend if applicable
                if self.show_chan_labels and not offset_chans:
                    legend.addItem(curve, name=ch_state['name'])
```

**Patterns**:
- **Vertical Positioning**: Uses `setPos()` to offset channels
- **Color Management**: Handles both continuous and per-source color schemes
- **NaN Handling**: `connect='finite'` prevents lines through gaps

#### 8. Plot Linking and Synchronization

```python
    # Link all plots to bottom plot for synchronized zooming
    bottom_pw = self._widget.getItem(last_row, 0)
    bottom_pw.setLabel('bottom', 'Time', units='s', **labelStyle)
    bottom_pw.getAxis("bottom").setStyle(showValues=True)
    
    for row_ix in range(last_row):
        pw = self._widget.getItem(row_ix, 0)
        pw.setXLink(bottom_pw)  # Link x-axis for synchronized zoom/pan
    
    self._widget.ci.setSpacing(10. if self.ylabel_as_title else 0.)
    self._do_yaxis_sync = True  # Flag to sync y-axis widths on first update
```

**Patterns**:
- **X-Axis Linking**: All plots zoom/pan together
- **Deferred Synchronization**: Y-axis widths synced after first render
- **Conditional Spacing**: Adjusts spacing based on label placement

#### 9. Y-Axis Width Synchronization

```python
def sync_y_axes(self):
    """Ensure all y-axes have the same width for alignment."""
    # Find maximum width needed
    max_width = self._ylabel_width or 0.
    for src_ix in range(len(self._data_sources)):
        pw = self._widget.getItem(src_ix, 0)
        if pw is None:
            break
        yax = pw.getAxis('left')
        max_width = max(max_width, yax.minimumWidth())
    
    # Apply to all plots
    for src_ix in range(len(self._data_sources)):
        pw = self._widget.getItem(src_ix, 0)
        if pw is None:
            break
        pw.getAxis('left').setWidth(max_width)
    
    self._do_yaxis_sync = False
```

**Pattern**: Deferred synchronization ensures proper alignment after labels are rendered.


#### 10. Update Visualization with Data Scaling

```python
def update_visualization(self, data: np.ndarray, timestamps: np.ndarray) -> None:
    # Check if we have any data
    if not any([np.any(_) for _ in timestamps[0]]):
        return
    
    for src_ix in range(len(data)):
        pw = self._widget.getItem(src_ix, 0)
        if pw is None:
            return  # Can happen during slow reset_renderer
        
        dat, mrk = data[src_ix]
        ts, mrk_ts = timestamps[src_ix]
        
        if dat.size:
            # Sync y-axes on first update
            if self._do_yaxis_sync:
                self.sync_y_axes()
            
            per_chan_range = (-0.5, 0.5)
            offset_chans = self.offset_channels and dat.shape[0] > 1
            
            # Scale data based on auto-scale setting
            if self.auto_scale != 'none':
                # Data already auto-scaled to [0, 1], shift to [-0.5, 0.5]
                dat -= 0.5
            elif offset_chans:
                # Manual scaling for offset channels
                coef = (per_chan_range[1] - per_chan_range[0]) / (self.upper_limit - self.lower_limit)
                dat = dat - self.lower_limit
                np.multiply(dat, coef, out=dat)
                np.add(dat, per_chan_range[0], out=dat)
            
            # Update each curve
            for ch_ix, _d in enumerate(dat):
                curve = pw.curves[ch_ix + (1 if self._antialias else 0)]
                curve.setData(ts % self.duration, _d)  # Modulo for sweep mode
```

**Patterns**:
- **Conditional Scaling**: Different scaling logic based on auto-scale and offset settings
- **In-Place Operations**: Uses `np.multiply` and `np.add` with `out=` for efficiency
- **Sweep Mode**: Uses modulo operator for wrapping time display

#### 11. Marker Handling with Object Pooling

```python
        # Track oldest valid time for marker cleanup
        if not self._buffers[src_ix]._tvec.size:
            continue
        lead_t = self._buffers[src_ix]._tvec[self._buffers[src_ix]._write_idx]
        self._t_expired = max(lead_t - self._duration, self._t_expired)
        
        # Remove expired markers
        if isinstance(pw.items[-1], pg.TextItem):
            while (len(self._marker_info) > 0) and (self._marker_info[0].timestamp < self._t_expired):
                pop_info = self._marker_info.popleft()
                pw.removeItem(pop_info[2])
                self.marker_texts_pool.append(pop_info[2])  # Return to pool for reuse
        
        # Add new markers
        if mrk.size:
            b_new = mrk_ts > self._src_last_marker_time[src_ix]
            for _t, _m in zip(mrk_ts[b_new], mrk[b_new]):
                # Try to reuse existing text object
                if len(self.marker_texts_pool) > 0:
                    text = self.marker_texts_pool.popleft()
                    text.setText(_m)
                else:
                    # Create new text object
                    text = pg.TextItem(text=_m, angle=90)
                    font = QtGui.QFont()
                    font.setPointSize(self.font_size + 2.0)
                    text.setFont(font)
                
                text.setPos(_t % self.duration, -1)
                pw.addItem(text)
                self._marker_info.append(MarkerMap(src_ix, _t, text))
            
            if np.any(b_new):
                self._src_last_marker_time[src_ix] = mrk_ts[b_new][-1]
```

**Patterns**:
- **Object Pooling**: Reuses TextItem objects to avoid repeated allocation
- **Incremental Updates**: Only processes new markers, not all markers
- **Timestamp Tracking**: Remembers last marker time to identify new markers
- **Automatic Cleanup**: Removes markers that have scrolled off screen

### Key Takeaways from LinePG

1. **Complexity Management**: Breaks down complex visualization into manageable pieces
2. **Performance Optimization**: Object pooling, in-place operations, deferred synchronization
3. **Flexibility**: Many configuration options for different use cases
4. **Robustness**: Handles edge cases (no data, slow resets, missing channels)
5. **Multi-Source Support**: Elegant handling of multiple data sources with separate plots
6. **Smart Defaults**: Automatically chooses optimal settings based on configuration

---

## Example 3: LineVis - High-Performance GPU Renderer

LineVis demonstrates how to create a high-performance renderer using vispy and OpenGL. This renderer can handle hundreds of channels with minimal performance impact.

### Key Characteristics

- **Data Parent**: `RendererDataTimeSeries` - Time series buffering
- **Display Parent**: `VispyRenderer` - GPU-accelerated rendering
- **Complexity**: High - Custom shaders, GPU programming
- **Use Case**: High channel counts, real-time performance critical applications

### Architecture Overview

LineVis uses custom GLSL shaders to render all channels in a single draw call, achieving exceptional performance through GPU parallelization.

### Annotated Key Sections

#### 1. Custom GLSL Shaders

```python
# Vertex shader - runs once per vertex (sample point)
VERT_SHADER = """
#version 130

// Input attributes per vertex
attribute float a_position;      // Y-coordinate (data value)
attribute vec3 a_index;          // (column, row, sample_index)
attribute vec3 a_color;          // RGB color for this channel

// Uniforms (constant for all vertices in a draw call)
uniform vec2 u_scale;            // Zoom factors (x, y)
uniform vec2 u_offset;           // Plot area offset
uniform vec2 u_size;             // Plot area size
uniform vec2 u_dims;             // (n_rows, n_cols)
uniform float u_n;               // Samples per channel

// Outputs to fragment shader
varying vec4 v_color;
varying vec3 v_index;
varying vec2 v_position;
varying vec4 v_ab;

void main() {
    float nrows = u_dims.x;
    float ncols = u_dims.y;
    
    // Convert sample index to x-coordinate in [-1, 1]
    float x = -1 + 2*a_index.z / (u_n-1);
    vec2 position = vec2(x - (1 - 1 / u_scale.x), a_position);
    
    // Calculate subplot transformation
    vec2 a = vec2(u_size.x/ncols, u_size.y/nrows);
    vec2 b = vec2(-1 + u_offset.x + 2*(a_index.x+.5) / ncols,
                  -1 + u_offset.y + 2*(a_index.y+.5) / nrows);
    
    // Apply transformation and scaling
    gl_Position = vec4(a*u_scale*position+b, 0.0, 1.0);
    
    v_color = vec4(a_color, 1.);
    v_index = a_index;
    v_position = gl_Position.xy;
    v_ab = vec4(a, b);
}
"""

# Fragment shader - runs once per pixel
FRAG_SHADER = """
#version 120

varying vec4 v_color;
varying vec3 v_index;

void main() {
    gl_FragColor = v_color;
    
    // Discard fragments between channels (emulate separate draw calls)
    if ((fract(v_index.x) > 0.) || (fract(v_index.y) > 0.))
        discard;
}
"""
```

**Pattern**: Custom shaders enable rendering all channels in a single GPU call, dramatically improving performance.


#### 2. Initialization with Vispy Canvas

```python
class LineVis(RendererDataTimeSeries, VispyRenderer):
    # Vispy supports many colormaps
    import matplotlib.pyplot as plt
    color_sets = set(["random"] + list(vispy.color.get_colormaps().keys()) + plt.colormaps())
    
    gui_kwargs = dict(
        RendererDataTimeSeries.gui_kwargs,
        **VispyRenderer.gui_kwargs,
        columns=int,              # Multi-column layout
        vertical_markers=bool,    # Marker text orientation
        stagger_markers=bool,     # Offset sequential markers
        x_offset=float,           # Plot area positioning
        y_offset=float,
        width=float,              # Plot area size
        height=float
    )
    
    def __init__(self,
                 color_set: str = 'husl',
                 columns: int = 1,
                 vertical_markers: bool = True,
                 stagger_markers: bool = False,
                 x_offset: float = 0.06,
                 y_offset: float = 0.0,
                 width: float = 0.94,
                 height: float = 1.0,
                 **kwargs):
        self._columns = columns
        self._vertical_markers = vertical_markers
        self._stagger_markers = stagger_markers
        self._plot_offset = (x_offset, y_offset)
        self._plot_size = (width, height)
        
        # Marker management
        self._marker_texts_pool = deque()
        self._marker_info = deque()
        self._visuals = deque()
        self._src_top_row = []
        self._src_last_marker_time = []
        self._mrk_offset = []
        
        # CRITICAL: Must set draw_mode for vispy
        kwargs['draw_mode'] = 'line_strip'
        
        super().__init__(color_set=color_set, **kwargs)
        self.reset_renderer()
```

**Patterns**:
- **Draw Mode**: Vispy requires explicit draw mode specification
- **Layout Control**: Flexible positioning and sizing of plot area
- **Marker Pooling**: Same object pooling pattern as LinePG

#### 3. GPU Program Configuration

```python
def configure_programs(self):
    """Create and configure GPU programs for each data source."""
    if len(self._data_sources) == 0:
        return
    
    n_vis_total = self.chan_states['vis'].sum()
    self._chan_colors = self.get_channel_colors(self.color_set, n_vis_total)
    
    self._programs = []
    self._src_top_row = []
    self._src_chan_offset = []
    self._mrk_offset = []
    chan_offset = 0
    
    for src_ix, src in enumerate(self._data_sources):
        ch_states = self.chan_states[self.chan_states['src'] == src.identifier]
        n_vis_src = ch_states['vis'].sum()
        
        if n_vis_src == 0:
            self._programs.append(None)
            continue
        
        buff = self._buffers[src_ix]
        n_samples = buff._data.shape[-1]
        row_offset = int(np.ceil(chan_offset / self.columns))
        nrows = int(np.ceil(n_vis_src / self.columns))
        
        # Create GPU program with shaders
        prog = gloo.Program(VERT_SHADER, FRAG_SHADER)
```

**Pattern**: One GPU program per data source, configured with appropriate vertex attributes and uniforms.


#### 4. Vertex Attribute Setup

```python
        # Build a_index: 3-column matrix (col, row, sample) for each vertex
        # Total vertices = n_visible_channels * n_samples
        
        # Column indices (for multi-column layout)
        col_idx = np.repeat(np.repeat(np.arange(self.columns), nrows), n_samples)
        
        # Row indices (from bottom to top)
        top_row = n_vis_total - row_offset - 1
        self._src_top_row.append(top_row)
        row_idx = np.repeat(np.tile(np.arange(top_row, top_row - nrows, -1), self.columns), n_samples)
        
        # Sample indices (within each channel)
        samp_idx = np.tile(np.arange(n_samples), n_vis_src)
        
        # Combine into 3-column matrix
        prog['a_index'] = np.c_[col_idx, row_idx, samp_idx].astype(np.float32)
        
        # Y-coordinates (data values) - flattened across all channels
        prog['a_position'] = buff._data.reshape(-1, 1)
        
        # Colors - repeat each channel's color for all its samples
        prog['a_color'] = np.repeat(
            self._chan_colors[chan_offset:chan_offset+n_vis_src, :3],
            n_samples, 
            axis=0
        ).astype(np.float32)
        
        # Set uniforms
        prog['u_scale'] = (1.0, 1.0)  # Initial zoom
        prog['u_dims'] = (n_vis_total, self.columns)
        prog['u_offset'] = self._plot_offset
        prog['u_size'] = self._plot_size
        prog['u_n'] = n_samples
        
        self._programs.append(prog)
        self._src_chan_offset.append(chan_offset)
        chan_offset += n_vis_src
        self._mrk_offset.append(0.5)
```

**Patterns**:
- **Vertex Attributes**: Each sample point is a vertex with position, index, and color
- **Batch Processing**: All channels rendered in single draw call
- **Index Encoding**: Clever use of indices to position channels in grid layout

#### 5. Efficient Data Updates

```python
def update_visualization(self,
                         data: List[Tuple[np.ndarray, np.ndarray]],
                         timestamps: List[Tuple[np.ndarray, np.ndarray]]) -> None:
    if not any([np.any(_) for _ in timestamps[0]]):
        return
    
    for src_ix in range(len(data)):
        dat, mrk = data[src_ix]
        ts, mrk_ts = timestamps[src_ix]
        
        if dat.size:
            # Scale data to [-1, 1] range for GPU
            per_chan_range = (-1, 1)
            coef = (per_chan_range[1] - per_chan_range[0]) / (self.upper_limit - self.lower_limit)
            dat = dat - self.lower_limit
            np.multiply(dat, coef, out=dat)
            np.add(dat, per_chan_range[0], out=dat)
            
            # Update GPU buffer with new data
            self._programs[src_ix]['a_position'].set_data(dat.reshape(-1, 1))
```

**Patterns**:
- **GPU Buffer Updates**: Direct updates to GPU memory
- **Minimal CPU Work**: Data scaling is the only CPU operation
- **In-Place Operations**: Efficient memory usage with `out=` parameter

#### 6. Marker Rendering with Vispy Visuals

```python
        if mrk.size:
            b_new = mrk_ts > self._src_last_marker_time[src_ix]
            for _t, _m in zip(mrk_ts[b_new], mrk[b_new]):
                # Try to reuse existing visual
                if len(self._marker_texts_pool) > 0:
                    tvis = self._marker_texts_pool.popleft()
                    tvis._text = _m
                    tvis._vertices = None  # Force regeneration
                    tvis._color = vispy.color.ColorArray(self._chan_colors[self._src_chan_offset[src_ix]])
                    tvis._color_changed = True
                else:
                    # Create new text visual
                    tvis = visuals.TextVisual(
                        text=_m,
                        color=self._chan_colors[self._src_chan_offset[src_ix]],
                        rotation=270 if self._vertical_markers else 0,
                        font_size=self.font_size,
                        anchor_x='left' if self._vertical_markers else 'right',
                        anchor_y='top' if self._vertical_markers else 'center',
                        method='gpu'  # GPU-accelerated text rendering
                    )
                    tvis.transform = transforms.STTransform()
                    tvis.transforms.configure(canvas=self, viewport=(0, 0, self.size[0], self.size[1]))
                
                # Position marker
                tvis._pos[0, :2] = self._get_marker_pos(_t, src_ix)
                tvis._pos_changed = True
                tvis.update()
                
                self._visuals.append(tvis)
                self._marker_info.append(MarkerMap(src_ix, _t))
                
                # Stagger markers if enabled
                if self._stagger_markers:
                    self._mrk_offset[src_ix] = ((10 * self._mrk_offset[src_ix] + 1) % 10) / 10
```

**Patterns**:
- **GPU Text Rendering**: Uses vispy's GPU-accelerated text
- **Visual Pooling**: Reuses TextVisual objects for performance
- **Transform System**: Vispy's transform system for positioning
- **Marker Staggering**: Vertical offset to prevent overlap

### Key Takeaways from LineVis

1. **GPU Acceleration**: Custom shaders enable rendering hundreds of channels efficiently
2. **Batch Rendering**: All channels rendered in single draw call
3. **Memory Efficiency**: Direct GPU buffer updates, minimal CPU-GPU transfers
4. **Vispy Patterns**: Proper use of visuals, transforms, and GPU programs
5. **Performance Focus**: Every design decision optimized for speed
6. **Complexity Trade-off**: More complex code for better performance

---

## PyQtGraph vs. Vispy: Detailed Comparison

### Performance Characteristics

| Aspect | PyQtGraph | Vispy |
|--------|-----------|-------|
| **Rendering Method** | CPU-based with some GPU acceleration | Full GPU/OpenGL rendering |
| **Channel Capacity** | ~50-100 channels at 60 Hz | 500+ channels at 60 Hz |
| **Startup Time** | Fast | Moderate (shader compilation) |
| **Memory Usage** | Moderate | Low (GPU memory) |
| **CPU Usage** | Moderate-High | Low |
| **Update Latency** | 5-20ms | 1-5ms |

### Code Complexity Comparison

#### PyQtGraph: Simple and Intuitive

```python
# Creating a plot is straightforward
self._widget = pg.PlotWidget()
self._widget.setYRange(0, 100)
curve = self._widget.plot(pen=pg.mkPen('r', width=2))

# Updating is simple
curve.setData(x_data, y_data)
```

#### Vispy: More Complex but Powerful

```python
# Requires understanding of OpenGL concepts
prog = gloo.Program(VERT_SHADER, FRAG_SHADER)
prog['a_position'] = data.reshape(-1, 1)
prog['a_index'] = indices.astype(np.float32)
prog['u_scale'] = (1.0, 1.0)

# Updates require GPU buffer operations
prog['a_position'].set_data(new_data.reshape(-1, 1))
```

### Feature Comparison

| Feature | PyQtGraph | Vispy |
|---------|-----------|-------|
| **Legends** | Built-in, easy | Manual implementation |
| **Axes/Grids** | Automatic | Manual implementation |
| **Zoom/Pan** | Built-in | Manual implementation |
| **Tooltips** | Easy to add | Complex |
| **3D Support** | Limited | Excellent |
| **Custom Shaders** | Not available | Full control |
| **Interactive Tools** | Rich ecosystem | Basic |

### When to Choose Each

#### Choose PyQtGraph When:

1. **Rapid Development**: Need to create visualizations quickly
2. **Standard Plots**: Line plots, bar charts, scatter plots
3. **Interactive Features**: Need legends, tooltips, crosshairs
4. **Moderate Data**: <100 channels, <1000 samples visible
5. **Learning Curve**: Team is new to graphics programming
6. **Maintenance**: Want simple, readable code

**Example Use Cases**:
- Dashboard visualizations
- Data exploration tools
- Scientific plotting applications
- Prototyping and demos

#### Choose Vispy When:

1. **High Performance**: Need to render 100+ channels smoothly
2. **Real-Time Critical**: Latency must be minimal (<5ms)
3. **Custom Rendering**: Need special visual effects or shaders
4. **3D Visualization**: Working with 3D data or spatial layouts
5. **Resource Constrained**: Limited CPU but have GPU
6. **Scalability**: Data volume will grow significantly

**Example Use Cases**:
- High-density EEG visualization (128+ channels)
- Real-time signal processing displays
- 3D brain activity visualization
- Large-scale sensor networks
- Performance-critical applications

### Hybrid Approach

You can use both in the same application:

```python
# Use PyQtGraph for control panels and simple plots
control_widget = pg.PlotWidget()

# Use Vispy for high-performance main visualization
from vispy import scene
main_canvas = scene.SceneCanvas()

# Combine in Qt layout
layout = QtWidgets.QVBoxLayout()
layout.addWidget(control_widget)
layout.addWidget(main_canvas.native)
```

---

## Performance Considerations for Real-Time Rendering

### Understanding the Rendering Pipeline

Real-time rendering in StreamViewer involves several stages:

1. **Data Acquisition** (LSL) → 2. **Buffering** → 3. **Data Formatting** → 4. **Rendering** → 5. **Display**

Each stage has performance implications.

### Critical Performance Factors

#### 1. Update Frequency

```python
# PyQtGraph: 60 Hz is typical
class MyPGRenderer(RendererDataTimeSeries, PGRenderer):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Timer runs at 60 Hz by default (inherited from PGRenderer)

# Vispy: Can handle higher rates
class MyVisRenderer(RendererDataTimeSeries, VispyRenderer):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Can run at 120+ Hz if needed
```

**Guideline**: Match update frequency to display refresh rate (typically 60 Hz). Higher rates waste CPU/GPU.

#### 2. Data Buffer Size

```python
# Smaller buffers = less memory, faster updates
def __init__(self, duration: float = 5.0, **kwargs):  # 5 seconds of data
    super().__init__(duration=duration, **kwargs)

# Larger buffers = more history, slower updates
def __init__(self, duration: float = 60.0, **kwargs):  # 60 seconds
    super().__init__(duration=duration, **kwargs)
```

**Guideline**: Use the minimum duration needed for your visualization. Typical range: 5-30 seconds.

#### 3. Number of Channels

```python
# Performance degrades with channel count
# PyQtGraph: Comfortable up to ~50 channels
# Vispy: Can handle 500+ channels

# Optimize by hiding unused channels
def reset_renderer(self, reset_channel_labels=True):
    # Only create visuals for visible channels
    visible_channels = self.chan_states[self.chan_states['vis']]
    for ch in visible_channels.iterrows():
        # Create visual for this channel
        pass
```

**Guideline**: 
- PyQtGraph: <50 channels for smooth 60 Hz
- Vispy: <500 channels for smooth 60 Hz

#### 4. Drawing Operations

```python
# SLOW: Recreating objects every update
def update_visualization(self, data, timestamps):
    self._widget.clear()  # DON'T DO THIS
    for ch_data in data:
        self._widget.plot(ch_data)  # Creates new objects

# FAST: Updating existing objects
def update_visualization(self, data, timestamps):
    for curve, ch_data in zip(self._curves, data):
        curve.setData(timestamps, ch_data)  # Updates existing object
```

**Guideline**: Create objects once in `reset_renderer`, update them in `update_visualization`.

### Optimization Techniques

#### Technique 1: Object Pooling

Reuse objects instead of creating/destroying them:

```python
class OptimizedRenderer(RendererDataTimeSeries, PGRenderer):
    def __init__(self, **kwargs):
        self._marker_pool = deque()  # Pool of reusable marker objects
        super().__init__(**kwargs)
    
    def update_visualization(self, data, timestamps):
        for marker_text in new_markers:
            if self._marker_pool:
                # Reuse existing object
                text_item = self._marker_pool.popleft()
                text_item.setText(marker_text)
            else:
                # Create new object only if pool is empty
                text_item = pg.TextItem(text=marker_text)
            
            self._widget.addItem(text_item)
    
    def remove_old_markers(self, old_markers):
        for marker in old_markers:
            self._widget.removeItem(marker)
            self._marker_pool.append(marker)  # Return to pool
```

**Benefit**: Reduces garbage collection overhead, improves frame consistency.

#### Technique 2: Batch Updates

Update all elements before triggering a redraw:

```python
# SLOW: Multiple redraws
def update_visualization(self, data, timestamps):
    for curve, ch_data in zip(self._curves, data):
        curve.setData(timestamps, ch_data)  # Triggers redraw each time

# FAST: Single redraw
def update_visualization(self, data, timestamps):
    # Disable auto-range during updates
    self._widget.setAutoVisible(y=False)
    
    # Update all curves
    for curve, ch_data in zip(self._curves, data):
        curve.setData(timestamps, ch_data)
    
    # Re-enable and trigger single redraw
    self._widget.setAutoVisible(y=True)
```

**Benefit**: Reduces rendering overhead by 50-90%.

#### Technique 3: Downsampling

Reduce data points for distant views:

```python
def update_visualization(self, data, timestamps):
    # Get current view range
    view_range = self._widget.viewRange()
    visible_duration = view_range[0][1] - view_range[0][0]
    
    # Downsample if zoomed out
    if visible_duration > 10.0:  # More than 10 seconds visible
        # Show every Nth point
        downsample_factor = int(visible_duration / 10.0)
        data = data[:, ::downsample_factor]
        timestamps = timestamps[::downsample_factor]
    
    # Update with downsampled data
    for curve, ch_data in zip(self._curves, data):
        curve.setData(timestamps, ch_data)
```

**Benefit**: Maintains smooth rendering when zoomed out.

#### Technique 4: Lazy Evaluation

Defer expensive operations until necessary:

```python
class LazyRenderer(RendererDataTimeSeries, PGRenderer):
    def __init__(self, **kwargs):
        self._needs_colormap_update = False
        self._needs_axis_sync = False
        super().__init__(**kwargs)
    
    def reset_renderer(self, reset_channel_labels=True):
        # Mark operations as needed, don't do them yet
        self._needs_colormap_update = True
        self._needs_axis_sync = True
        # ... create visualization structure
    
    def update_visualization(self, data, timestamps):
        # Perform deferred operations on first update
        if self._needs_colormap_update:
            self._update_colormap()
            self._needs_colormap_update = False
        
        if self._needs_axis_sync:
            self._sync_axes()
            self._needs_axis_sync = False
        
        # ... update visualization
```

**Benefit**: Spreads expensive operations across frames, avoiding stutters.

#### Technique 5: In-Place Operations

Use NumPy's in-place operations to avoid memory allocation:

```python
# SLOW: Creates new arrays
def update_visualization(self, data, timestamps):
    scaled_data = (data - self.lower_limit) / (self.upper_limit - self.lower_limit)
    shifted_data = scaled_data - 0.5
    # Update with shifted_data

# FAST: In-place operations
def update_visualization(self, data, timestamps):
    # Modify data in-place
    data -= self.lower_limit
    data /= (self.upper_limit - self.lower_limit)
    data -= 0.5
    # Update with data (modified in-place)

# FASTEST: Use out parameter
def update_visualization(self, data, timestamps):
    np.subtract(data, self.lower_limit, out=data)
    np.divide(data, (self.upper_limit - self.lower_limit), out=data)
    np.subtract(data, 0.5, out=data)
```

**Benefit**: Reduces memory allocation and garbage collection.

### Profiling and Debugging Performance

#### Using Python's cProfile

```python
import cProfile
import pstats

# Profile your renderer
profiler = cProfile.Profile()
profiler.enable()

# Run your renderer for a while
# ... application runs ...

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)  # Top 20 functions by time
```

#### Using Qt's Performance Tools

```python
from qtpy import QtCore

class ProfiledRenderer(RendererDataTimeSeries, PGRenderer):
    def __init__(self, **kwargs):
        self._update_times = deque(maxlen=100)
        super().__init__(**kwargs)
    
    def update_visualization(self, data, timestamps):
        start_time = QtCore.QTime.currentTime()
        
        # Your update code here
        # ...
        
        elapsed = start_time.msecsTo(QtCore.QTime.currentTime())
        self._update_times.append(elapsed)
        
        # Log if update is slow
        if elapsed > 16:  # 16ms = 60 Hz threshold
            avg_time = sum(self._update_times) / len(self._update_times)
            print(f"Slow update: {elapsed}ms (avg: {avg_time:.1f}ms)")
```

### Performance Benchmarks

Typical performance on modern hardware (Intel i7, NVIDIA GTX 1060):

| Renderer Type | Channels | Sample Rate | Update Rate | CPU Usage | Notes |
|---------------|----------|-------------|-------------|-----------|-------|
| BarPG | 32 | N/A | 60 Hz | 5% | Snapshot only |
| LinePG | 32 | 250 Hz | 60 Hz | 15% | 10s buffer |
| LinePG | 64 | 250 Hz | 60 Hz | 30% | 10s buffer |
| LineVis | 128 | 250 Hz | 60 Hz | 8% | 10s buffer |
| LineVis | 256 | 250 Hz | 60 Hz | 12% | 10s buffer |

**Key Insight**: Vispy (LineVis) maintains low CPU usage even with many channels.

### Performance Checklist

When optimizing your renderer:

- [ ] Update frequency matches display refresh rate (typically 60 Hz)
- [ ] Objects created once in `reset_renderer`, not in `update_visualization`
- [ ] Using object pooling for frequently created/destroyed objects
- [ ] Batch updates to minimize redraws
- [ ] In-place NumPy operations where possible
- [ ] Downsampling when zoomed out
- [ ] Lazy evaluation for expensive operations
- [ ] Profiled to identify bottlenecks
- [ ] Tested with maximum expected channel count
- [ ] Tested with maximum expected sample rate

---

## Configuration and Settings Persistence

### Understanding gui_kwargs

The `gui_kwargs` dictionary is central to settings persistence in StreamViewer. It defines which parameters are saved to INI files and restored on application restart.

### Complete Settings Persistence Pattern

```python
from qtpy import QtCore

class ConfigurableRenderer(RendererDataTimeSeries, PGRenderer):
    # ========================================================================
    # STEP 1: Define gui_kwargs
    # ========================================================================
    gui_kwargs = dict(
        RendererDataTimeSeries.gui_kwargs,  # Inherit parent parameters
        **PGRenderer.gui_kwargs,
        # Add your parameters with their types
        line_width=float,
        line_style=str,
        show_markers=bool,
        marker_size=int,
        alpha=float
    )
    
    # ========================================================================
    # STEP 2: Accept parameters in __init__
    # ========================================================================
    def __init__(self,
                 # Your parameters with defaults
                 line_width: float = 2.0,
                 line_style: str = 'solid',
                 show_markers: bool = True,
                 marker_size: int = 10,
                 alpha: float = 1.0,
                 **kwargs):
        # Store as instance variables
        self._line_width = line_width
        self._line_style = line_style
        self._show_markers = show_markers
        self._marker_size = marker_size
        self._alpha = alpha
        
        self._widget = pg.PlotWidget()
        super().__init__(**kwargs)
        self.reset_renderer()
    
    # ========================================================================
    # STEP 3: Create properties for each parameter
    # ========================================================================
    @property
    def line_width(self):
        """Get current line width."""
        return self._line_width
    
    @line_width.setter
    def line_width(self, value):
        """Set line width and update visualization."""
        self._line_width = value
        self.reset_renderer(reset_channel_labels=False)
    
    @property
    def line_style(self):
        return self._line_style
    
    @line_style.setter
    def line_style(self, value):
        self._line_style = value
        self.reset_renderer(reset_channel_labels=False)
    
    @property
    def show_markers(self):
        return self._show_markers
    
    @show_markers.setter
    def show_markers(self, value):
        self._show_markers = value
        # No reset needed - only affects future marker rendering
    
    # ========================================================================
    # STEP 4: Create Qt slots for control panel connections
    # ========================================================================
    @QtCore.Slot(float)
    def line_width_valueChanged(self, value):
        """Slot for line width spinbox/slider."""
        self.line_width = value
    
    @QtCore.Slot(str)
    def line_style_currentTextChanged(self, text):
        """Slot for line style combo box."""
        self.line_style = text
    
    @QtCore.Slot(bool)
    def show_markers_stateChanged(self, checked):
        """Slot for show markers checkbox."""
        self.show_markers = checked
    
    @QtCore.Slot(int)
    def marker_size_valueChanged(self, value):
        """Slot for marker size spinbox."""
        self.marker_size = value
```

### How Settings Persistence Works

1. **On Application Startup**:
   - Application reads INI file (e.g., `~/.stream_viewer/lsl_viewer.ini`)
   - Finds saved parameters for your renderer
   - Calls `__init__` with saved values

2. **During Runtime**:
   - User changes parameter through control panel
   - Control panel emits signal (e.g., `valueChanged`)
   - Signal connects to your slot (e.g., `line_width_valueChanged`)
   - Slot calls property setter
   - Property setter updates visualization

3. **On Application Exit**:
   - Application iterates through `gui_kwargs`
   - Reads current value from each property
   - Saves to INI file

### INI File Format

Settings are saved in standard INI format:

```ini
[Renderer_LinePG_0]
line_width=2.5
line_style=solid
show_markers=true
marker_size=12
alpha=0.8
auto_scale=by-channel
color_set=viridis
lower_limit=-100.0
upper_limit=100.0
```

### Advanced: Conditional Reset Logic

Sometimes you don't want to rebuild the entire visualization for every parameter change:

```python
@property
def line_width(self):
    return self._line_width

@line_width.setter
def line_width(self, value):
    self._line_width = value
    # Only update existing curves, don't rebuild everything
    if hasattr(self, '_curves'):
        for curve in self._curves:
            pen = curve.opts['pen']
            pen.setWidth(value)
            curve.setPen(pen)
    else:
        # First time, need full reset
        self.reset_renderer(reset_channel_labels=False)

@property
def color_set(self):
    return self._color_set

@color_set.setter
def color_set(self, value):
    self._color_set = value
    # Color change requires full rebuild
    self.reset_renderer(reset_channel_labels=False)
```

### Validation and Constraints

Add validation in property setters:

```python
@property
def line_width(self):
    return self._line_width

@line_width.setter
def line_width(self, value):
    # Validate and constrain value
    self._line_width = np.clip(value, 0.1, 10.0)
    self.reset_renderer(reset_channel_labels=False)

@property
def alpha(self):
    return self._alpha

@alpha.setter
def alpha(self, value):
    # Ensure alpha is in [0, 1]
    self._alpha = max(0.0, min(1.0, value))
    self.reset_renderer(reset_channel_labels=False)
```

### Inherited Parameters

You automatically inherit parameters from parent classes:

```python
# From RendererDataTimeSeries:
# - auto_scale: str
# - lower_limit: float
# - upper_limit: float
# - duration: float
# - plot_mode: str

# From PGRenderer:
# - color_set: str
# - bg_color: str
# - font_size: int
# - show_chan_labels: bool

# Access inherited parameters:
def reset_renderer(self, reset_channel_labels=True):
    # Use inherited properties
    self._widget.setYRange(self.lower_limit, self.upper_limit)
    self._widget.setBackground(self.parse_color_str(self.bg_color))
    
    # Get colormap using inherited method
    colors = self.get_colormap(self.color_set, n_channels)
```

### Best Practices for Settings

1. **Provide Sensible Defaults**: Choose defaults that work for most use cases
2. **Validate Input**: Constrain values to valid ranges
3. **Minimize Resets**: Only call `reset_renderer` when necessary
4. **Document Parameters**: Use docstrings to explain what each parameter does
5. **Group Related Parameters**: Use similar naming for related settings
6. **Consider Performance**: Some parameters may need performance warnings

```python
@property
def duration(self):
    return self._duration

@duration.setter
def duration(self, value):
    if value > 60.0:
        import warnings
        warnings.warn("Large duration values may impact performance")
    self._duration = value
    self.reset()  # Duration change requires full reset including buffers
```

---

## Summary

This guide has covered three real-world renderers demonstrating different complexity levels and approaches:

1. **BarPG**: Simple, beginner-friendly snapshot visualization
2. **LinePG**: Advanced multi-plot time series with rich features
3. **LineVis**: High-performance GPU-accelerated rendering

### Key Patterns Learned

- **Cooperative Inheritance**: Combining data and display parent classes
- **Object Pooling**: Reusing objects for performance
- **Lazy Evaluation**: Deferring expensive operations
- **Batch Updates**: Minimizing redraws
- **Settings Persistence**: Property + slot pattern
- **Performance Optimization**: In-place operations, downsampling, profiling

### Next Steps

- Review the [Development Guide](development-guide.md) for step-by-step instructions
- Study the [Architecture Documentation](architecture.md) for system design
- Explore the [Widget Development Guide](../widgets/development-guide.md) for control panels
- Examine other renderers in `stream_viewer/renderers/` for more examples

### Additional Resources

- [PyQtGraph Documentation](https://pyqtgraph.readthedocs.io/)
- [Vispy Documentation](https://vispy.org/)
- [Qt for Python Documentation](https://doc.qt.io/qtforpython/)
- [NumPy Performance Tips](https://numpy.org/doc/stable/user/performance.html)

Happy rendering!
