from collections import deque, namedtuple
import json
import numpy as np
from qtpy import QtGui
import pyqtgraph as pg
from scipy import signal
from stream_viewer.renderers.data.base import RendererDataTimeSeries
from stream_viewer.renderers.display.pyqtgraph import PGRenderer


MarkerMap = namedtuple('MarkerMap', ['source_id', 'timestamp', 'item'])


class HeatmapPG(RendererDataTimeSeries, PGRenderer):
    """
    Pyqtgraph-based 2D spectrogram (heatmap) renderer analogous to LinePG, rendering one
    averaged-across-channels spectrogram per data source. Supports Sweep and Scroll modes.
    """
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
                 ylabel_width: int = None,
                 ylabel: str = None,
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

        self._widget = pg.GraphicsLayoutWidget()
        self._do_yaxis_sync = False
        self._src_last_marker_time = []
        self._marker_texts_pool = deque()
        self._marker_info = deque()
        self._t_expired = -np.inf
        self._image_items = []
        # Per-source state for column-wise updates
        self._heatmaps = []
        self._freq_masks = []
        self._n_time_cols = []
        self._hop_sizes = []
        self._write_indices = []
        self._last_total_frames = []
        self._locked_levels = []
        self._last_t_end = []

        super().__init__(show_chan_labels=show_chan_labels, color_set=color_set, **kwargs)
        self.reset_renderer()

    # ------------------------------ #
    # Lifecycle / layout
    # ------------------------------ #
    def reset_renderer(self, reset_channel_labels=True):
        self._widget.clear()
        self._widget.setBackground(self.parse_color_str(self.bg_color))
        self._src_last_marker_time = [-np.inf for _ in range(len(self._data_sources))]
        self._image_items = []
        self._heatmaps = [None for _ in range(len(self._data_sources))]
        self._freq_masks = [None for _ in range(len(self._data_sources))]
        self._n_time_cols = [None for _ in range(len(self._data_sources))]
        self._hop_sizes = [None for _ in range(len(self._data_sources))]
        self._write_indices = [0 for _ in range(len(self._data_sources))]
        self._last_total_frames = [0 for _ in range(len(self._data_sources))]
        self._locked_levels = [None for _ in range(len(self._data_sources))]
        self._last_t_end = [None for _ in range(len(self._data_sources))]

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
        for src_ix, src in enumerate(self._data_sources):
            ch_states = self.chan_states[self.chan_states['src'] == src.identifier]
            n_vis_src = ch_states['vis'].sum()
            if n_vis_src == 0:
                continue

            row_offset += 1
            pw = self._widget.addPlot(row=row_offset, col=0, antialias=True)
            last_row = row_offset
            pw.showGrid(x=True, y=True, alpha=0.3)

            font = QtGui.QFont()
            font.setPointSize(self.font_size - 2)
            pw.setXRange(0, self.duration)
            pw.getAxis("bottom").setTickFont(font)
            pw.getAxis("bottom").setStyle(showValues=self.ylabel_as_title)

            yax = pw.getAxis('left')
            yax.setTickFont(font)
            stream_ylabel = json.loads(src.identifier)['name']
            if 'unit' in ch_states and ch_states['unit'].nunique() == 1:
                stream_ylabel = stream_ylabel + ' (%s)' % ch_states['unit'].iloc[0]
            pw.setLabel('top' if self.ylabel_as_title else 'left', self._ylabel or stream_ylabel, **labelStyle)
            if self.ylabel_as_title:
                pw.getAxis("top").setStyle(showValues=False)

            # Create the image item for spectrogram; attach color LUT later on first update
            img = pg.ImageItem(axisOrder='row-major')
            pw.addItem(img)
            self._image_items.append(img)

            # Y axis range (frequency)
            pw.setYRange(self._fmin_hz, self._fmax_hz)

        # Bottom axis label and link x-axes
        bottom_pw = self._widget.getItem(last_row, 0)
        if bottom_pw is not None:
            bottom_pw.setLabel('bottom', 'Time', units='s', **labelStyle)
            bottom_pw.getAxis("bottom").setStyle(showValues=True)
            for row_ix in range(last_row):
                pw = self._widget.getItem(row_ix, 0)
                if pw is None:
                    break
                pw.setXLink(bottom_pw)

        self._widget.ci.setSpacing(10. if self.ylabel_as_title else 0.)
        self._do_yaxis_sync = True

    def _ensure_source_state(self, src_ix, srate, f, Pxx):
        # Initialize frequency mask
        if self._freq_masks[src_ix] is None and f is not None and f.size:
            f_mask = (f >= float(self._fmin_hz)) & (f <= float(self._fmax_hz))
            if not np.any(f_mask):
                f_mask = np.ones_like(f, dtype=bool)
            self._freq_masks[src_ix] = f_mask

        # Initialize hop and column count
        if self._hop_sizes[src_ix] is None and srate > 0:
            hop = max(1, int(self._nperseg - self._noverlap))
            N = max(0, int(srate * self.duration))
            n_cols = 1 + max(0, (N - int(self._nperseg)) // hop) if N >= int(self._nperseg) else 1
            self._hop_sizes[src_ix] = hop
            self._n_time_cols[src_ix] = n_cols

        # Initialize heatmap with NaNs sized to freq mask and columns
        if (self._heatmaps[src_ix] is None) and (self._freq_masks[src_ix] is not None) and (self._n_time_cols[src_ix] is not None):
            n_freq = int(np.sum(self._freq_masks[src_ix]))
            n_cols = int(self._n_time_cols[src_ix])
            self._heatmaps[src_ix] = np.full((n_freq, n_cols), np.nan, dtype=float)
            self._write_indices[src_ix] = 0
            self._last_total_frames[src_ix] = 0
            self._locked_levels[src_ix] = None
            self._last_t_end[src_ix] = None

    def sync_y_axes(self):
        max_width = self._ylabel_width or 0.
        for src_ix in range(len(self._data_sources)):
            pw = self._widget.getItem(src_ix, 0)
            if pw is None:
                break
            yax = pw.getAxis('left')
            max_width = max(max_width, yax.minimumWidth())

        for src_ix in range(len(self._data_sources)):
            pw = self._widget.getItem(src_ix, 0)
            if pw is None:
                break
            pw.getAxis('left').setWidth(max_width)
        self._do_yaxis_sync = False

    # ------------------------------ #
    # Update loop
    # ------------------------------ #
    def update_visualization(self, data: np.ndarray, timestamps: np.ndarray) -> None:
        if not any([np.any(_) for _ in timestamps[0]]):
            return

        # Prepare LUT for heatmap colors (once)
        lut = self.get_colormap(self.color_set, 256)

        for src_ix in range(len(data)):
            pw = self._widget.getItem(src_ix, 0)
            if pw is None:
                return

            dat, mrk = data[src_ix]
            ts, mrk_ts = timestamps[src_ix]

            # Align axis label widths if needed
            if self._do_yaxis_sync:
                self.sync_y_axes()

            # Spectrogram from buffered latest window (compute once per tick)
            if self._buffers[src_ix]._data.size:
                # Average across visible channels (ignore NaNs)
                buff_data = self._buffers[src_ix]._data
                if buff_data.size == 0 or buff_data.shape[0] == 0 or buff_data.shape[1] == 0:
                    x = np.array([], dtype=float)
                else:
                    x = np.nanmean(buff_data, axis=0)
                    x = np.nan_to_num(x, nan=0.0)

                # Need a valid sampling rate
                srate = self._data_sources[src_ix].data_stats.get('srate', 0.0) or 0.0
                if srate <= 0.0:
                    # Cannot compute proper spectrogram without a rate; skip
                    pass
                else:
                    nperseg = max(8, min(self._nperseg, x.size))
                    noverlap = max(0, min(self._noverlap, nperseg - 1))
                    try:
                        f, t, Sxx = signal.spectrogram(
                            x, fs=float(srate), nperseg=int(nperseg), noverlap=int(noverlap),
                            scaling='density', mode='psd'
                        )
                    except Exception:
                        f, t, Sxx = np.array([]), np.array([]), np.array([[]])

                    if Sxx.size:
                        # Convert to dB
                        Pxx = 10.0 * np.log10(Sxx + 1e-12)
                        # Ensure state initialized (freq mask, columns, heatmap)
                        self._ensure_source_state(src_ix, srate, f, Pxx)
                        if self._freq_masks[src_ix] is None or self._heatmaps[src_ix] is None:
                            # Not enough information yet to render
                            pass
                        else:
                            f_mask = self._freq_masks[src_ix]
                            P_use = Pxx[f_mask, :]

                            # Determine how many new frames arrived since last update
                            # Use spectrogram frame count difference to determine new columns
                            total_frames = int(P_use.shape[1])
                            prev_frames = int(self._last_total_frames[src_ix] or 0)
                            new = max(0, total_frames - prev_frames)
                            self._last_total_frames[src_ix] = total_frames
                            if new > 0:
                                heat = self._heatmaps[src_ix]
                                n_cols = heat.shape[1]
                                new = min(new, P_use.shape[1], n_cols)
                                if self.plot_mode != "Sweep":
                                    # Scroll: roll left and append new columns on the right
                                    if new >= n_cols:
                                        heat[:, :] = P_use[:, -n_cols:]
                                    else:
                                        heat[:, :-new] = heat[:, new:]
                                        heat[:, -new:] = P_use[:, -new:]
                                else:
                                    # Sweep: circular write into columns
                                    widx = self._write_indices[src_ix] or 0
                                    for k in range(new):
                                        col = (widx + k) % n_cols
                                        heat[:, col] = P_use[:, -new + k]
                                    self._write_indices[src_ix] = (widx + new) % n_cols

                                self._heatmaps[src_ix] = heat

                            # Stable color levels
                            levels = self._locked_levels[src_ix]
                            if self._auto_scale == 'none':
                                levels = (float(self.lower_limit), float(self.upper_limit))
                            else:
                                if levels is None:
                                    # Lock from current heat (ignore NaNs)
                                    h = self._heatmaps[src_ix]
                                    if np.isfinite(h).any():
                                        hmin = float(np.nanmin(h))
                                        hmax = float(np.nanmax(h))
                                        if not np.isfinite(hmin) or not np.isfinite(hmax) or (hmax <= hmin):
                                            hmin, hmax = -120.0, 0.0
                                        levels = (hmin, hmax)
                                        self._locked_levels[src_ix] = levels
                                    else:
                                        levels = (-120.0, 0.0)

                            # Update image from persistent heatmap
                            img = self._image_items[src_ix]
                            img.setImage(self._heatmaps[src_ix], levels=levels, autoLevels=False)
                            img.setLookupTable(lut)
                            img.setRect(pg.QtCore.QRectF(0.0, float(self._fmin_hz),
                                                         float(self.duration),
                                                         float(self._fmax_hz - self._fmin_hz)))

            # Update expiry threshold
            if not self._buffers[src_ix]._tvec.size:
                continue
            lead_t = self._buffers[src_ix]._tvec[self._buffers[src_ix]._write_idx]
            self._t_expired = max(lead_t - self._duration, self._t_expired)

            # Remove expired markers
            if isinstance(pw.items[-1], pg.TextItem):
                while (len(self._marker_info) > 0) and (self._marker_info[0].timestamp < self._t_expired):
                    pop_info = self._marker_info.popleft()
                    pw.removeItem(pop_info[2])
                    self._marker_texts_pool.append(pop_info[2])

            # Add new markers
            if mrk.size:
                b_new = mrk_ts > self._src_last_marker_time[src_ix]
                for _t, _m in zip(mrk_ts[b_new], mrk[b_new]):
                    if len(self._marker_texts_pool) > 0:
                        text = self._marker_texts_pool.popleft()
                        text.setText(_m)
                    else:
                        text = pg.TextItem(text=_m, angle=90)
                        font = QtGui.QFont()
                        font.setPointSize(self.font_size + 2.0)
                        text.setFont(font)

                    # Place at bottom of frequency range
                    text.setPos((_t % self.duration), float(self._fmin_hz))
                    pw.addItem(text)
                    self._marker_info.append(MarkerMap(src_ix, _t, text))

                if np.any(b_new):
                    self._src_last_marker_time[src_ix] = mrk_ts[b_new][-1]

    # ------------------------------ #
    # Properties
    # ------------------------------ #
    @property
    def ylabel_as_title(self):
        return self._ylabel_as_title

    @ylabel_as_title.setter
    def ylabel_as_title(self, value):
        self._ylabel_as_title = value
        self.reset_renderer(reset_channel_labels=True)

    @property
    def ylabel_width(self):
        return self._ylabel_width

    @ylabel_width.setter
    def ylabel_width(self, value):
        self._ylabel_width = value
        self.reset_renderer(reset_channel_labels=True)

    @property
    def fmin_hz(self):
        return self._fmin_hz

    @fmin_hz.setter
    def fmin_hz(self, value):
        self._fmin_hz = float(value)
        self.reset_renderer(reset_channel_labels=False)

    @property
    def fmax_hz(self):
        return self._fmax_hz

    @fmax_hz.setter
    def fmax_hz(self, value):
        self._fmax_hz = float(value)
        self.reset_renderer(reset_channel_labels=False)

    @property
    def nperseg(self):
        return self._nperseg

    @nperseg.setter
    def nperseg(self, value):
        self._nperseg = int(value)
        self.reset_renderer(reset_channel_labels=False)

    @property
    def noverlap(self):
        return self._noverlap

    @noverlap.setter
    def noverlap(self, value):
        self._noverlap = int(value)
        self.reset_renderer(reset_channel_labels=False)

    @RendererDataTimeSeries.auto_scale.setter
    def auto_scale(self, value):
        self._requested_auto_scale = value.lower()
        self.reset_renderer(reset_channel_labels=False)


