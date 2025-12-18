from collections import deque, namedtuple
from dataclasses import dataclass
import json
import logging
import warnings
import numpy as np
from qtpy import QtGui, QtWidgets
import pyqtgraph as pg
from pyqtgraph.widgets.RemoteGraphicsView import RemoteGraphicsView
from scipy import signal
from typing import Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from stream_viewer.buffers.stream_data_buffers import TimeSeriesBuffer

from stream_viewer.renderers.data.base import RendererDataTimeSeries
from stream_viewer.renderers.display.pyqtgraph import PGRenderer


logger = logging.getLogger(__name__)

# Constants
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


class HeatmapPG(RendererDataTimeSeries, PGRenderer):
    """
    Production-quality PyQtGraph-based 2D spectrogram (heatmap) renderer for live EEG data.
    
    Compatible with HeatmapControlPanel which provides Apply/Revert buttons
    for responsive configuration changes.
    
    This renderer computes and displays spectrograms by averaging across visible channels
    for each data source. It supports both Sweep and Scroll visualization modes with
    efficient column-wise updates and robust error handling.
    
    Features:
    - Real-time spectrogram computation with configurable frequency ranges
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
        **PGRenderer.gui_kwargs,
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
        self._ylabel_as_title = ylabel_as_title
        self._ylabel_width = ylabel_width
        self._ylabel = ylabel
        self._requested_auto_scale = auto_scale.lower()

        # spectrogram parameters
        self._fmin_hz = float(fmin_hz)
        self._fmax_hz = float(fmax_hz)
        self._nperseg = int(nperseg)
        self._noverlap = int(noverlap)

        # Container widget with vertical layout for RemoteGraphicsView instances
        self._widget = QtWidgets.QWidget()
        self._widget.setLayout(QtWidgets.QVBoxLayout())
        self._remote_views: list[Optional[RemoteGraphicsView]] = []  # Store RemoteGraphicsView instances (None for skipped sources)
        self._plot_items: list = []  # Store remote plot items for x-axis linking (None for skipped sources)
        self._do_yaxis_sync = False
        self._src_last_marker_time = []
        self._marker_texts_pool = deque()
        self._marker_info = deque()
        self._t_expired = -np.inf
        self._image_items = []
        # Per-source state using SourceState dataclass
        self._source_states: list[SourceState] = []
        # Cached LUT for performance
        self._cached_lut: Optional[np.ndarray] = None
        self._cached_color_set: Optional[str] = None
        
        # Debounce timer for property changes
        self._reset_timer = pg.QtCore.QTimer()
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
        
        # Clear container layout - remove all RemoteGraphicsView widgets
        layout = self._widget.layout()
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Clear storage - will be reinitialized below to match data_sources indices
        self._src_last_marker_time = [-np.inf for _ in range(len(self._data_sources))]
        n_sources = len(self._data_sources)
        self._image_items = [None] * n_sources
        # Initialize source states
        n_sources = len(self._data_sources)
        while len(self._source_states) < n_sources:
            self._source_states.append(SourceState())
        # Reset all source states
        for state in self._source_states:
            state.reset()
        # Trim if we have too many
        self._source_states = self._source_states[:n_sources]

        if len(self.chan_states) == 0:
            return

        labelStyle = {'color': '#FFF', 'font-size': str(self.font_size) + 'pt'}

        # Requested auto-scale maps to actual behavior; for heatmaps, pyqtgraph levels handle scaling
        if self._requested_auto_scale == 'all':
            self._auto_scale = 'none'
        else:
            self._auto_scale = self._requested_auto_scale

        row_offset = -1
        last_row = 0
        bottom_plot_item = None
        
        # Initialize plot_items list to match data_sources indices (None for skipped sources)
        n_sources = len(self._data_sources)
        self._plot_items = [None] * n_sources
        self._remote_views = [None] * n_sources
        
        for src_ix, src in enumerate(self._data_sources):
            ch_states = self.chan_states[self.chan_states['src'] == src.identifier]
            n_vis_src = ch_states['vis'].sum()
            if n_vis_src == 0:
                continue

            row_offset += 1
            last_row = row_offset
            
            # Create RemoteGraphicsView for this data source
            remote_view = RemoteGraphicsView(debug=False)
            # Enable antialiasing in remote process (doesn't affect main process performance)
            remote_view.pg.setConfigOptions(antialias=True)  # type: ignore
            
            # Create plot item in remote process
            pw = remote_view.pg.PlotItem()  # type: ignore
            # Performance: Apply deferGetattr to speed up access
            pw._setProxyOptions(deferGetattr=True)
            # Set background on the view widget using Qt palette (RemoteGraphicsView is in main process)
            bg_color_str = self.parse_color_str(self.bg_color)
            bg_qcolor = pg.mkColor(bg_color_str)
            palette = remote_view.palette()
            palette.setColor(remote_view.backgroundRole(), bg_qcolor)
            remote_view.setPalette(palette)
            remote_view.setAutoFillBackground(True)
            remote_view.setCentralItem(pw)
            
            # Store references at source index (not row_offset)
            self._remote_views[src_ix] = remote_view
            self._plot_items[src_ix] = pw
            
            # Add to container layout
            layout.addWidget(remote_view)
            
            pw.showGrid(x=True, y=True, alpha=0.3)

            # Create font in remote process to avoid QGuiApplication warnings
            font = remote_view.pg.QtGui.QFont()  # type: ignore
            font.setPointSize(self.font_size - 2)
            pw.setXRange(0, self.duration)
            pw.getAxis("bottom").setTickFont(font)
            pw.getAxis("bottom").setStyle(showValues=self.ylabel_as_title)

            yax = pw.getAxis('left')
            yax.setTickFont(font)
            stream_ylabel = json.loads(src.identifier)['name']
            if 'unit' in ch_states and ch_states['unit'].nunique() == 1:  # type: ignore
                stream_ylabel = stream_ylabel + ' (%s)' % ch_states['unit'].iloc[0]  # type: ignore
            pw.setLabel('top' if self.ylabel_as_title else 'left', self._ylabel or stream_ylabel, **labelStyle)
            if self.ylabel_as_title:
                pw.getAxis("top").setStyle(showValues=False)

            # Create the image item for spectrogram in remote process; attach color LUT later on first update
            img = remote_view.pg.ImageItem(axisOrder='row-major')  # type: ignore
            pw.addItem(img)
            self._image_items[src_ix] = img

            # Y axis range (frequency)
            pw.setYRange(self._fmin_hz, self._fmax_hz)

        # Bottom axis label and link x-axes manually
        # Find the last non-None plot item (bottom one)
        bottom_plot_item = None
        for plot_item in reversed(self._plot_items):
            if plot_item is not None:
                bottom_plot_item = plot_item
                break
        
        if bottom_plot_item is not None:
            bottom_plot_item.setLabel('bottom', 'Time', units='s', **labelStyle)
            bottom_plot_item.getAxis("bottom").setStyle(showValues=True)
            # Link all plots to bottom plot
            for plot_item in self._plot_items:
                if plot_item is not None and plot_item is not bottom_plot_item:
                    plot_item.setXLink(bottom_plot_item)

        # Set layout spacing
        layout.setSpacing(int(10. if self.ylabel_as_title else 0.))
        self._do_yaxis_sync = True

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

    def sync_y_axes(self) -> None:
        """Synchronize y-axis widths across all plots."""
        max_width = self._ylabel_width or 0.
        for pw in self._plot_items:
            if pw is None:
                continue
            yax = pw.getAxis('left')
            max_width = max(max_width, yax.minimumWidth())

        for pw in self._plot_items:
            if pw is None:
                continue
            pw.getAxis('left').setWidth(max_width)
        self._do_yaxis_sync = False

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
        
        curr_wi = int(buf._write_idx)
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
    
    def _get_colormap_lut(self) -> np.ndarray:
        """
        Get colormap lookup table with caching.
        
        Returns:
            Lookup table array
        """
        if self._cached_lut is None or self._cached_color_set != self.color_set:
            self._cached_lut = self.get_colormap(self.color_set, 256)
            self._cached_color_set = self.color_set
        return self._cached_lut
    
    def _update_markers(self, src_ix: int, pw, mrk: np.ndarray, mrk_ts: np.ndarray) -> None:
        """
        Update markers on the plot.
        
        Args:
            src_ix: Source index
            pw: Plot widget (unused, kept for compatibility)
            mrk: Marker array
            mrk_ts: Marker timestamps
        """
        # Get plot item and remote view for this source
        if src_ix >= len(self._plot_items) or src_ix >= len(self._remote_views):
            return
        pw = self._plot_items[src_ix]
        remote_view = self._remote_views[src_ix]
        
        # Update expiry threshold
        if not self._buffers[src_ix]._tvec.size:
            return
        
        buf = self._buffers[src_ix]
        if hasattr(buf, "_write_idx"):
            lead_t = float(buf._tvec[buf._write_idx])  # type: ignore
            self._t_expired = max(lead_t - self._duration, self._t_expired)

        # Remove expired markers
        # Note: pw.items works via proxy, but isinstance check may need to be done differently
        # We'll check if there are items and remove expired ones
        try:
            items = pw.items
            if items and len(items) > 0:
                while (len(self._marker_info) > 0) and (self._marker_info[0].timestamp < self._t_expired):
                    pop_info = self._marker_info.popleft()
                    pw.removeItem(pop_info[2])
                    self._marker_texts_pool.append(pop_info[2])
        except Exception:
            # If items access fails, try to remove based on marker_info
            while (len(self._marker_info) > 0) and (self._marker_info[0].timestamp < self._t_expired):
                pop_info = self._marker_info.popleft()
                try:
                    pw.removeItem(pop_info[2])
                except Exception:
                    pass
                self._marker_texts_pool.append(pop_info[2])

        # Add new markers
        if mrk.size:
            b_new = mrk_ts > self._src_last_marker_time[src_ix]
            for _t, _m in zip(mrk_ts[b_new], mrk[b_new]):
                if len(self._marker_texts_pool) > 0:
                    text = self._marker_texts_pool.popleft()
                    text.setText(_m)
                else:
                    # Create TextItem in remote process
                    text = remote_view.pg.TextItem(text=_m, angle=90)  # type: ignore
                    # Create font in remote process to avoid QGuiApplication warnings
                    font = remote_view.pg.QtGui.QFont()  # type: ignore
                    font.setPointSize(int(self.font_size + 2.0))
                    text.setFont(font)

                # Place at bottom of frequency range
                text.setPos((_t % self.duration), float(self._fmin_hz))
                pw.addItem(text)
                self._marker_info.append(MarkerMap(src_ix, _t, text))

            if np.any(b_new):
                self._src_last_marker_time[src_ix] = mrk_ts[b_new][-1]

    def update_visualization(self, data: np.ndarray, timestamps: np.ndarray) -> None:
        """
        Update visualization with new data.
        
        Args:
            data: List of (data, markers) tuples per source
            timestamps: List of (timestamps, marker_timestamps) tuples per source
        """
        if not any([np.any(_) for _ in timestamps[0]]):
            return

        # Get cached LUT
        lut = self._get_colormap_lut()

        for src_ix in range(len(data)):
            # Get plot item from remote plot items list
            if src_ix >= len(self._plot_items):
                continue
            pw = self._plot_items[src_ix]
            if pw is None:
                continue

            dat, mrk = data[src_ix]
            ts, mrk_ts = timestamps[src_ix]

            # Align axis label widths if needed
            if self._do_yaxis_sync:
                self.sync_y_axes()

            # Process spectrogram if buffer has data
            buff_data = self._buffers[src_ix]._data
            has_new_data = False
            if buff_data.size > 0:
                buf = self._buffers[src_ix]
                state = self._source_states[src_ix]
                
                # Check if there's new data to process (avoid expensive spectrogram computation if no new data)
                if hasattr(buf, "_write_idx"):
                    curr_write_idx = int(buf._write_idx)  # type: ignore
                    # Only compute spectrogram if we have new data or haven't processed this source yet
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

                # Prepare display heatmap (always update display, even if no new data)
                display = self._prepare_display_heatmap(src_ix)
                if display is not None:
                    # Update color levels
                    levels = self._update_color_levels(src_ix)
                    
                    # Determine time range for x-axis
                    if self.plot_mode == "Scroll":
                        # In scroll mode, use actual time range from buffer
                        if buf._tvec.size > 0:
                            t_min = float(np.nanmin(buf._tvec))
                            t_max = float(np.nanmax(buf._tvec))
                            # Ensure valid range
                            if np.isfinite(t_min) and np.isfinite(t_max) and t_max > t_min:
                                time_start = t_min
                                time_width = t_max - t_min
                            else:
                                # Fallback to duration-based range
                                time_start = 0.0
                                time_width = float(self.duration)
                        else:
                            time_start = 0.0
                            time_width = float(self.duration)
                    else:
                        # In sweep mode, use fixed 0 to duration
                        time_start = 0.0
                        time_width = float(self.duration)
                    
                    # Update x-axis range
                    pw.setXRange(time_start, time_start + time_width)
                    
                    # Update image with performance optimization: use _callSync='off' for operations that don't need return values
                    if src_ix < len(self._image_items):
                        img = self._image_items[src_ix]
                        if img is not None:
                            img.setImage(display, levels=levels, autoLevels=False, _callSync='off')
                            img.setLookupTable(lut, _callSync='off')
                            img.setRect(pg.QtCore.QRectF(
                                time_start, float(self._fmin_hz),
                                time_width,
                                float(self._fmax_hz - self._fmin_hz)
                            ), _callSync='off')

            # Update markers
            self._update_markers(src_ix, pw, mrk, mrk_ts)

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
        # Update Y-axis range in-place if plots exist
        if self._plot_items:
            for pw in self._plot_items:
                if pw is not None:
                    pw.setYRange(self._fmin_hz, self._fmax_hz)
            # Invalidate frequency mask - will recompute on next update
            for state in self._source_states:
                state.freq_mask = None
        else:
            # No plots yet, need full reset
            self._schedule_reset(reset_channel_labels=False)

    @property
    def fmax_hz(self):
        return self._fmax_hz

    @fmax_hz.setter
    def fmax_hz(self, value):
        self._fmax_hz = float(value)
        # Update Y-axis range in-place if plots exist
        if self._plot_items:
            for pw in self._plot_items:
                if pw is not None:
                    pw.setYRange(self._fmin_hz, self._fmax_hz)
            # Invalidate frequency mask - will recompute on next update
            for state in self._source_states:
                state.freq_mask = None
        else:
            # No plots yet, need full reset
            self._schedule_reset(reset_channel_labels=False)

    @property
    def nperseg(self):
        return self._nperseg

    @nperseg.setter
    def nperseg(self, value):
        self._nperseg = int(value)
        # Invalidate state - will recompute with new parameters on next update
        if self._image_items:
            for state in self._source_states:
                state.hop_size = None
                state.n_time_cols = None
                state.heatmap = None
                state.write_index = 0
                state.last_processed_write_idx = None
                state.sample_carry = 0
        else:
            # No plots yet, need full reset
            self._schedule_reset(reset_channel_labels=False)

    @property
    def noverlap(self):
        return self._noverlap

    @noverlap.setter
    def noverlap(self, value):
        self._noverlap = int(value)
        # Invalidate state - will recompute with new parameters on next update
        if self._image_items:
            for state in self._source_states:
                state.hop_size = None
                state.n_time_cols = None
                state.heatmap = None
                state.write_index = 0
                state.last_processed_write_idx = None
                state.sample_carry = 0
        else:
            # No plots yet, need full reset
            self._schedule_reset(reset_channel_labels=False)

    @RendererDataTimeSeries.auto_scale.setter
    def auto_scale(self, value):
        self._requested_auto_scale = value.lower()
        self._schedule_reset(reset_channel_labels=False)
    
    @property
    def color_set(self):
        """Get current color set."""
        return super().color_set
    
    @color_set.setter
    def color_set(self, value):
        """Set color set and invalidate LUT cache."""
        super().color_set = value  # type: ignore
        self._cached_lut = None
        self._cached_color_set = None
        # Update image items with new colormap if they exist
        if self._image_items:
            lut = self._get_colormap_lut()
            for img in self._image_items:
                if img is not None:
                    img.setLookupTable(lut)


