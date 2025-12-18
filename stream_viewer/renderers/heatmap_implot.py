from collections import deque, namedtuple
from dataclasses import dataclass
import json
import logging
import warnings
import numpy as np
from qtpy import QtGui, QtWidgets, QtCore
from scipy import signal
from typing import Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from stream_viewer.buffers.stream_data_buffers import TimeSeriesBuffer

from stream_viewer.renderers.data.base import RendererDataTimeSeries
from stream_viewer.renderers.display.implot import ImPlotRenderer, ImPlotOpenGLWidget, SLIMGUI_AVAILABLE

if SLIMGUI_AVAILABLE:
    from slimgui import imgui
    from slimgui import implot

logger = logging.getLogger(__name__)

# Constants (same as HeatmapPG)
DEFAULT_DB_FLOOR = -120.0  # Default dB value for NaN/invalid data
DEFAULT_DB_CEILING = 0.0    # Default dB ceiling for auto-scale fallback
EPSILON_DB = 1e-12          # Small epsilon to prevent log(0) in dB conversion
MIN_NPERSEG = 8              # Minimum segment size for spectrogram
MIN_SRATE = 0.001            # Minimum valid sampling rate (Hz)

MarkerMap = namedtuple('MarkerMap', ['source_id', 'timestamp', 'item'])


@dataclass
class SourceState:
    """Per-source state for spectrogram rendering."""
    heatmap: Optional[np.ndarray] = None
    freq_mask: Optional[np.ndarray] = None
    n_time_cols: Optional[int] = None
    hop_size: Optional[int] = None
    write_index: int = 0
    locked_levels: Optional[Tuple[float, float]] = None
    last_write_index: Optional[int] = None
    sample_carry: int = 0
    last_processed_write_idx: Optional[int] = None  # Track last processed write index
    
    def reset(self):
        """Reset all state to initial values."""
        self.heatmap = None
        self.freq_mask = None
        self.n_time_cols = None
        self.hop_size = None
        self.write_index = 0
        self.locked_levels = None
        self.last_write_index = None
        self.sample_carry = 0
        self.last_processed_write_idx = None


class HeatmapImPlot(RendererDataTimeSeries, ImPlotRenderer):
    """
    Experimental GPU-accelerated spectrogram renderer using ImPlot.
    
    This renderer uses ImPlot for GPU-accelerated rendering while maintaining
    compatibility with the existing renderer architecture. It reuses the same
    spectrogram computation logic as HeatmapPG but renders using ImPlot's
    PlotHeatmap function for improved performance.
    
    Features:
    - Real-time spectrogram computation with configurable frequency ranges
    - GPU-accelerated rendering via ImPlot
    - Efficient column-wise updates to minimize computational overhead
    - Robust validation and error handling to prevent crashes
    - Automatic level locking for stable color scaling
    - Support for markers and time-based expiration
    
    Args:
        auto_scale: Auto-scaling mode ('none', 'by-channel', 'by-stream')
        show_chan_labels: Whether to show channel labels
        color_set: Colormap name for the heatmap
        ylabel_as_title: Display ylabel as title instead of axis label
        ylabel_width: Minimum width for y-axis label
        ylabel: Custom y-axis label text
        fmin_hz: Minimum frequency for spectrogram (Hz)
        fmax_hz: Maximum frequency for spectrogram (Hz)
        nperseg: Number of samples per segment for FFT
        noverlap: Number of overlapping samples between segments
    """
    COMPAT_ICONTROL = ['HeatmapControlPanel']
    plot_modes = ["Sweep", "Scroll"]
    gui_kwargs = dict(
        RendererDataTimeSeries.gui_kwargs,
        **ImPlotRenderer.gui_kwargs,
        ylabel_as_title=bool,
        ylabel_width=int,
        ylabel=str,
        fmin_hz=float,
        fmax_hz=float,
        nperseg=int,
        noverlap=int,
    )

    def __init__(self,
                 # inherited/overrides
                 auto_scale: str = 'none',
                 show_chan_labels: bool = True,
                 color_set: str = 'viridis',
                 # new
                 ylabel_as_title: bool = False,
                 ylabel_width: Optional[int] = None,
                 ylabel: Optional[str] = None,
                 fmin_hz: float = 1.0,
                 fmax_hz: float = 42.0,
                 nperseg: int = 256,
                 noverlap: int = 128,
                 **kwargs):
        if not SLIMGUI_AVAILABLE:
            raise ImportError(
                "slimgui is required for HeatmapImPlot. "
                "Install it with: pip install slimgui"
            )
        
        self._ylabel_as_title = ylabel_as_title
        self._ylabel_width = ylabel_width
        self._ylabel = ylabel
        self._requested_auto_scale = auto_scale.lower()

        # spectrogram parameters
        self._fmin_hz = float(fmin_hz)
        self._fmax_hz = float(fmax_hz)
        self._nperseg = int(nperseg)
        self._noverlap = int(noverlap)

        # Container widget with vertical layout for ImPlot widgets
        self._widget = QtWidgets.QWidget()
        self._widget.setLayout(QtWidgets.QVBoxLayout())
        self._implot_widgets: list[Optional[ImPlotOpenGLWidget]] = []  # Store ImPlot widgets (None for skipped sources)
        self._do_yaxis_sync = False
        self._src_last_marker_time = []
        self._marker_texts_pool = deque()
        self._marker_info = deque()
        self._t_expired = -np.inf
        # Per-source state using SourceState dataclass
        self._source_states: list[SourceState] = []
        # Cached colormap name
        self._cached_colormap_name = None
        
        # Debounce timer for property changes
        self._reset_timer = QtCore.QTimer()
        self._reset_timer.setSingleShot(True)
        self._reset_timer.timeout.connect(self._do_pending_reset)
        self._pending_reset = {'reset_channel_labels': False}

        super().__init__(show_chan_labels=show_chan_labels, color_set=color_set, **kwargs)
        self.reset_renderer()

    # ------------------------------ #
    # Lifecycle / layout
    # ------------------------------ #
    def reset_renderer(self, reset_channel_labels: bool = True) -> None:
        """
        Reset the renderer to initial state.
        
        Args:
            reset_channel_labels: Whether to reset channel labels
        """
        # Cancel any pending debounced resets to avoid double resets
        self._reset_timer.stop()
        self._pending_reset = {'reset_channel_labels': False}
        
        # Clear container layout - remove all ImPlot widgets
        layout = self._widget.layout()
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                widget = child.widget()
                if isinstance(widget, ImPlotOpenGLWidget):
                    widget.cleanup()
                widget.deleteLater()
        
        # Clear storage - will be reinitialized below to match data_sources indices
        self._src_last_marker_time = [-np.inf for _ in range(len(self._data_sources))]
        n_sources = len(self._data_sources)
        # Initialize source states
        while len(self._source_states) < n_sources:
            self._source_states.append(SourceState())
        # Reset all source states
        for state in self._source_states:
            state.reset()
        # Trim if we have too many
        self._source_states = self._source_states[:n_sources]

        if len(self.chan_states) == 0:
            return

        # Requested auto-scale maps to actual behavior; for heatmaps, ImPlot levels handle scaling
        if self._requested_auto_scale == 'all':
            self._auto_scale = 'none'
        else:
            self._auto_scale = self._requested_auto_scale

        row_offset = -1
        last_row = 0
        
        # Initialize implot_widgets list to match data_sources indices (None for skipped sources)
        n_sources = len(self._data_sources)
        self._implot_widgets = [None] * n_sources
        
        for src_ix, src in enumerate(self._data_sources):
            ch_states = self.chan_states[self.chan_states['src'] == src.identifier]
            n_vis_src = ch_states['vis'].sum()
            if n_vis_src == 0:
                continue

            row_offset += 1
            last_row = row_offset
            
            # Create ImPlot widget for this data source
            implot_widget = ImPlotOpenGLWidget()
            implot_widget.setMinimumHeight(200)  # Minimum height for visibility
            
            # Set render callback
            def make_render_callback(src_idx):
                def render_callback():
                    self._render_implot_plot(src_idx)
                return render_callback
            
            implot_widget.set_render_callback(make_render_callback(src_ix))
            
            # Store reference at source index (not row_offset)
            self._implot_widgets[src_ix] = implot_widget
            
            # Add to container layout
            layout.addWidget(implot_widget)

        # Set layout spacing
        layout.setSpacing(int(10. if self.ylabel_as_title else 0.))
        self._do_yaxis_sync = True
        
        # Update cached colormap
        self._cached_colormap_name = self.get_colormap_name(self.color_set)

    def _schedule_reset(self, reset_channel_labels: bool = False) -> None:
        """
        Schedule a debounced reset_renderer call.
        
        This prevents expensive reset operations from blocking the UI during rapid
        property changes. The reset will execute after 300ms of inactivity.
        
        Args:
            reset_channel_labels: Whether to reset channel labels when reset executes
        """
        self._pending_reset['reset_channel_labels'] = (
            self._pending_reset.get('reset_channel_labels', False) or reset_channel_labels
        )
        self._reset_timer.stop()
        self._reset_timer.start(300)  # 300ms debounce

    def _do_pending_reset(self) -> None:
        """
        Execute the pending reset (called by debounce timer).
        
        Stops the update timer during reset to prevent conflicts, then restarts it.
        """
        if self._timer.isActive():
            self._timer.stop()
        try:
            self.reset_renderer(reset_channel_labels=self._pending_reset['reset_channel_labels'])
        finally:
            if not self._timer.isActive():
                self.restart_timer()
        self._pending_reset = {'reset_channel_labels': False}

    def _ensure_source_state(self, src_ix: int, srate: float, f: np.ndarray, Pxx: np.ndarray) -> bool:
        """
        Ensure source state is initialized. Returns True if state is ready, False otherwise.
        
        Args:
            src_ix: Source index
            srate: Sampling rate
            f: Frequency array from spectrogram
            Pxx: Power spectral density array
            
        Returns:
            True if state is fully initialized and ready, False otherwise
        """
        if src_ix >= len(self._source_states):
            logger.warning(f"Source index {src_ix} out of range")
            return False
            
        state = self._source_states[src_ix]
        
        # Initialize frequency mask
        if state.freq_mask is None and f is not None and f.size > 0:
            f_mask = (f >= float(self._fmin_hz)) & (f <= float(self._fmax_hz))
            if not np.any(f_mask):
                logger.warning(f"Source {src_ix}: No frequencies in range [{self._fmin_hz}, {self._fmax_hz}] Hz, using all frequencies")
                f_mask = np.ones_like(f, dtype=bool)
            state.freq_mask = f_mask

        # Initialize hop and column count
        if state.hop_size is None and srate >= MIN_SRATE:
            hop = max(1, int(self._nperseg - self._noverlap))
            N = max(0, int(srate * self.duration))
            n_cols = 1 + max(0, (N - int(self._nperseg)) // hop) if N >= int(self._nperseg) else 1
            state.hop_size = hop
            state.n_time_cols = n_cols

        # Initialize heatmap with NaNs sized to freq mask and columns
        if (state.heatmap is None and state.freq_mask is not None and 
            state.n_time_cols is not None):
            n_freq = int(np.sum(state.freq_mask))
            n_cols = int(state.n_time_cols)
            if n_freq > 0 and n_cols > 0:
                state.heatmap = np.full((n_freq, n_cols), np.nan, dtype=float)
                state.write_index = 0
                state.locked_levels = None
                return True
            else:
                logger.warning(f"Source {src_ix}: Invalid heatmap dimensions ({n_freq}, {n_cols})")
                return False
        
        return state.heatmap is not None

    # ------------------------------ #
    # Update loop
    # ------------------------------ #
    def _validate_buffer_data(self, buff_data: np.ndarray) -> bool:
        """
        Validate buffer data before processing.
        
        Args:
            buff_data: Buffer data array
            
        Returns:
            True if data is valid for processing, False otherwise
        """
        if buff_data.size == 0:
            return False
        if buff_data.ndim != 2:
            return False
        if buff_data.shape[0] == 0 or buff_data.shape[1] == 0:
            return False
        # Check if at least one channel has finite data
        if not np.isfinite(buff_data).any():
            return False
        return True
    
    def _compute_channel_average(self, buff_data: np.ndarray) -> Optional[np.ndarray]:
        """
        Compute mean across channels with proper validation.
        
        Args:
            buff_data: Buffer data array (channels x samples)
            
        Returns:
            Averaged signal or None if invalid
        """
        if not self._validate_buffer_data(buff_data):
            return None
        
        # Compute mean across channels while tolerating all-NaN columns
        # Suppress RuntimeWarning for "Mean of empty slice" when columns are all-NaN
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', category=RuntimeWarning, message='Mean of empty slice')
            with np.errstate(invalid='ignore', divide='ignore'):
                x = np.nanmean(buff_data, axis=0)
        
        # Validate result
        if not np.isfinite(x).any():
            return None
        
        # Replace NaN with zeros for spectrogram computation
        x = np.nan_to_num(x, nan=0.0)
        return x
    
    def _compute_spectrogram(self, x: np.ndarray, srate: float) -> Optional[Tuple[np.ndarray, np.ndarray, np.ndarray]]:
        """
        Compute spectrogram with validation and error handling.
        
        Args:
            x: Input signal
            srate: Sampling rate
            
        Returns:
            Tuple of (frequencies, times, power) or None if computation fails
        """
        if x.size == 0:
            return None
        if srate < MIN_SRATE:
            logger.debug(f"Invalid sampling rate: {srate} Hz")
            return None
        
        nperseg = max(MIN_NPERSEG, min(self._nperseg, x.size))
        noverlap = max(0, min(self._noverlap, nperseg - 1))
        
        try:
            f, t, Sxx = signal.spectrogram(
                x, fs=float(srate), nperseg=int(nperseg), noverlap=int(noverlap),
                scaling='density', mode='psd'
            )
        except Exception as e:
            logger.warning(f"Spectrogram computation failed: {e}", exc_info=True)
            return None
        
        if Sxx.size == 0:
            return None
        
        # Convert to dB with safe handling
        with np.errstate(invalid='ignore', divide='ignore'):
            Pxx = 10.0 * np.log10(Sxx + EPSILON_DB)
        
        return (f, t, Pxx)
    
    def _calculate_new_columns(self, src_ix: int, buf) -> int:
        """
        Calculate number of new columns to add based on buffer write index progression.
        
        Args:
            src_ix: Source index
            buf: Buffer object
            
        Returns:
            Number of new columns to add
        """
        state = self._source_states[src_ix]
        
        buf_len = int(buf._data.shape[1]) if buf._data.ndim == 2 else 0
        if buf_len == 0 or not hasattr(buf, "_write_idx"):
            return 0
        
        curr_wi = int(buf._write_idx)  # type: ignore
        prev_wi = state.last_write_index
        
        if prev_wi is None:
            state.last_write_index = curr_wi
            return 0
        
        delta = (curr_wi - prev_wi) % buf_len
        state.last_write_index = curr_wi
        state.sample_carry += delta
        
        hop = int(state.hop_size or max(1, self._nperseg - self._noverlap))
        new = int(state.sample_carry // hop)
        state.sample_carry %= hop
        
        return new
    
    def _update_heatmap_columns(self, src_ix: int, P_use: np.ndarray, new_cols: int) -> bool:
        """
        Update heatmap with new columns for either Sweep or Scroll mode.
        
        Args:
            src_ix: Source index
            P_use: Power spectral density array (filtered by frequency mask)
            new_cols: Number of new columns to add
            
        Returns:
            True if update was successful, False otherwise
        """
        if new_cols <= 0:
            return False
        
        state = self._source_states[src_ix]
        if state.heatmap is None:
            return False
        
        heat = state.heatmap
        n_cols = heat.shape[1]
        new_cols = min(new_cols, P_use.shape[1], n_cols)
        
        if self.plot_mode != "Sweep":
            # Scroll: roll left and append new columns on the right
            if new_cols >= n_cols:
                heat[:, :] = P_use[:, -n_cols:]
            else:
                heat[:, :-new_cols] = heat[:, new_cols:]
                heat[:, -new_cols:] = P_use[:, -new_cols:]
        else:
            # Sweep: circular write into columns
            widx = state.write_index
            for k in range(new_cols):
                col = (widx + k) % n_cols
                heat[:, col] = P_use[:, -new_cols + k]
            state.write_index = (widx + new_cols) % n_cols
        
        return True
    
    def _prepare_display_heatmap(self, src_ix: int) -> Optional[np.ndarray]:
        """
        Prepare display heatmap, handling Sweep mode wrap-around.
        
        Args:
            src_ix: Source index
            
        Returns:
            Display array or None if not available
        """
        state = self._source_states[src_ix]
        if state.heatmap is None:
            return None
        
        if self.plot_mode == "Sweep":
            widx = int(state.write_index)
            heat = state.heatmap
            if heat.shape[1] > 1:
                display = np.hstack([heat[:, (widx+1):], heat[:, :(widx+1)]])
            else:
                display = heat
        else:
            display = state.heatmap.copy()
        
        # Replace NaN values with default for rendering
        if not np.isfinite(display).all():
            display = np.nan_to_num(display, nan=DEFAULT_DB_FLOOR)
        
        return display
    
    def _update_color_levels(self, src_ix: int) -> Tuple[float, float]:
        """
        Update and return color levels for display.
        
        Args:
            src_ix: Source index
            
        Returns:
            Tuple of (min_level, max_level)
        """
        state = self._source_states[src_ix]
        
        if self._auto_scale == 'none':
            return (float(self.lower_limit), float(self.upper_limit))
        
        # Auto-scale: lock levels from current heatmap
        if state.locked_levels is None:
            if state.heatmap is not None and np.isfinite(state.heatmap).any():
                hmin = float(np.nanmin(state.heatmap))
                hmax = float(np.nanmax(state.heatmap))
                if np.isfinite(hmin) and np.isfinite(hmax) and (hmax > hmin):
                    state.locked_levels = (hmin, hmax)
                    return state.locked_levels
            # Fallback to defaults
            state.locked_levels = (DEFAULT_DB_FLOOR, DEFAULT_DB_CEILING)
        
        return state.locked_levels or (DEFAULT_DB_FLOOR, DEFAULT_DB_CEILING)
    
    def _render_implot_plot(self, src_ix: int) -> None:
        """
        Render ImPlot plot for a specific source.
        
        This is called from the ImPlotOpenGLWidget's render callback.
        
        Args:
            src_ix: Source index
        """
        if not SLIMGUI_AVAILABLE:
            return
        
        if src_ix >= len(self._source_states):
            return
        
        state = self._source_states[src_ix]
        
        # Prepare display heatmap
        display = self._prepare_display_heatmap(src_ix)
        if display is None or display.size == 0:
            return
        
        # Get color levels
        levels = self._update_color_levels(src_ix)
        min_level, max_level = levels
        
        # Get source info for labels
        if src_ix < len(self._data_sources):
            src = self._data_sources[src_ix]
            ch_states = self.chan_states[self.chan_states['src'] == src.identifier]
            stream_ylabel = json.loads(src.identifier)['name']
            if 'unit' in ch_states and ch_states['unit'].nunique() == 1:
                stream_ylabel = stream_ylabel + ' (%s)' % ch_states['unit'].iloc[0]
        else:
            stream_ylabel = "Spectrogram"
        
        # Determine time range for x-axis
        buf = self._buffers[src_ix]
        if self.plot_mode == "Scroll":
            if buf._tvec.size > 0:
                t_min = float(np.nanmin(buf._tvec))
                t_max = float(np.nanmax(buf._tvec))
                if np.isfinite(t_min) and np.isfinite(t_max) and t_max > t_min:
                    time_start = t_min
                    time_width = t_max - t_min
                else:
                    time_start = 0.0
                    time_width = float(self.duration)
            else:
                time_start = 0.0
                time_width = float(self.duration)
        else:
            time_start = 0.0
            time_width = float(self.duration)
        
        # Get colormap name
        colormap_name = self.get_colormap_name(self.color_set)
        
        # Begin ImPlot plot
        plot_title = self._ylabel or stream_ylabel if self.ylabel_as_title else ""
        if implot.begin_plot(plot_title, (-1, -1)):
            try:
                # Set axis labels
                implot.setup_axis(implot.Axis.X1, label="Time (s)")
                implot.setup_axis(implot.Axis.Y1, label="Frequency (Hz)")
                # Set axis ranges
                implot.setup_axes_limits(implot.Axis.X1, time_start, time_start + time_width, implot.Cond.ALWAYS)
                implot.setup_axes_limits(implot.Axis.Y1, float(self._fmin_hz), float(self._fmax_hz), implot.Cond.ALWAYS)
                
                # Set colormap
                try:
                    colormap = getattr(implot, f"colormap_{colormap_name.lower()}", implot.Colormap.VIRIDIS)
                except AttributeError:
                    colormap = implot.Colormap.VIRIDIS
                implot.push_colormap(colormap)
                
                try:
                    # Plot heatmap
                    # implot.plot_heatmap expects data in row-major order (frequencies x time)
                    # Our display array is already in this format
                    # Convert to contiguous array if needed
                    display_contiguous = np.ascontiguousarray(display, dtype=np.float32)
                    
                    # implot.plot_heatmap signature: (label_id, values, scale_min, scale_max, label_fmt, bounds_min, bounds_max, flags)
                    implot.plot_heatmap(
                        "Spectrogram",
                        display_contiguous,  # 2D array (rows x cols), dimensions inferred automatically
                        min_level,  # scale_min
                        max_level,  # scale_max
                        None,  # label_fmt (None for default)
                        (time_start, float(self._fmin_hz)),  # bounds_min (x, y)
                        (time_start + time_width, float(self._fmax_hz))  # bounds_max (x, y)
                    )
                except Exception as e:
                    logger.warning(f"Error plotting heatmap: {e}", exc_info=True)
                finally:
                    implot.pop_colormap()
                
            finally:
                implot.end_plot()
    
    def update_visualization(self, data: np.ndarray, timestamps: np.ndarray) -> None:
        """
        Update visualization with new data.
        
        Args:
            data: List of (data, markers) tuples per source
            timestamps: List of (timestamps, marker_timestamps) tuples per source
        """
        if not any([np.any(_) for _ in timestamps[0]]):
            return

        for src_ix in range(len(data)):
            # Get ImPlot widget
            if src_ix >= len(self._implot_widgets):
                continue
            implot_widget = self._implot_widgets[src_ix]
            if implot_widget is None:
                continue

            dat, mrk = data[src_ix]
            ts, mrk_ts = timestamps[src_ix]

            # Process spectrogram if buffer has data
            buff_data = self._buffers[src_ix]._data
            has_new_data = False
            if buff_data.size > 0:
                buf = self._buffers[src_ix]
                state = self._source_states[src_ix]
                
                # Check if there's new data to process
                if hasattr(buf, "_write_idx"):
                    curr_write_idx = int(buf._write_idx)  # type: ignore
                    has_new_data = (state.last_processed_write_idx is None or 
                                   curr_write_idx != state.last_processed_write_idx)
                
                if has_new_data:
                    # Compute channel average with validation
                    x = self._compute_channel_average(buff_data)
                    if x is not None:
                        # Get sampling rate
                        srate = self._data_sources[src_ix].data_stats.get('srate', 0.0) or 0.0
                        if srate >= MIN_SRATE:
                            # Compute spectrogram (only when we have new data)
                            spec_result = self._compute_spectrogram(x, srate)
                            if spec_result is not None:
                                f, t, Pxx = spec_result

                                # Ensure source state is initialized
                                if self._ensure_source_state(src_ix, srate, f, Pxx):
                                    if state.freq_mask is not None and state.heatmap is not None:
                                        # Apply frequency mask
                                        P_use = Pxx[state.freq_mask, :]

                                        # Calculate new columns to add
                                        new_cols = self._calculate_new_columns(src_ix, buf)
                                        
                                        # Update heatmap with new columns
                                        if new_cols > 0:
                                            self._update_heatmap_columns(src_ix, P_use, new_cols)
                                        
                                        # Mark this write index as processed
                                        if hasattr(buf, "_write_idx"):
                                            state.last_processed_write_idx = int(buf._write_idx)  # type: ignore

            # Trigger widget update (this will call _render_implot_plot)
            implot_widget.update()  # This triggers paintGL

    # ------------------------------ #
    # Properties
    # ------------------------------ #
    @property
    def ylabel_as_title(self):
        return self._ylabel_as_title

    @ylabel_as_title.setter
    def ylabel_as_title(self, value):
        self._ylabel_as_title = value
        self._schedule_reset(reset_channel_labels=True)

    @property
    def ylabel(self):
        return self._ylabel

    @ylabel.setter
    def ylabel(self, value):
        self._ylabel = value
        self._schedule_reset(reset_channel_labels=True)

    @property
    def ylabel_width(self):
        return self._ylabel_width

    @ylabel_width.setter
    def ylabel_width(self, value):
        self._ylabel_width = value
        self._schedule_reset(reset_channel_labels=True)

    @property
    def fmin_hz(self):
        return self._fmin_hz

    @fmin_hz.setter
    def fmin_hz(self, value):
        self._fmin_hz = float(value)
        # Reset source states to recalculate frequency mask
        for state in self._source_states:
            state.freq_mask = None
        self._schedule_reset(reset_channel_labels=False)

    @property
    def fmax_hz(self):
        return self._fmax_hz

    @fmax_hz.setter
    def fmax_hz(self, value):
        self._fmax_hz = float(value)
        # Reset source states to recalculate frequency mask
        for state in self._source_states:
            state.freq_mask = None
        self._schedule_reset(reset_channel_labels=False)

    @property
    def nperseg(self):
        return self._nperseg

    @nperseg.setter
    def nperseg(self, value):
        self._nperseg = int(value)
        # Reset source states to recalculate hop size and columns
        for state in self._source_states:
            state.hop_size = None
            state.n_time_cols = None
        self._schedule_reset(reset_channel_labels=False)

    @property
    def noverlap(self):
        return self._noverlap

    @noverlap.setter
    def noverlap(self, value):
        self._noverlap = int(value)
        # Reset source states to recalculate hop size and columns
        for state in self._source_states:
            state.hop_size = None
            state.n_time_cols = None
        self._schedule_reset(reset_channel_labels=False)

    def cleanup(self):
        """Clean up resources."""
        super().cleanup()
        # Additional cleanup if needed

