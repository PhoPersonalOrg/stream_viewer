"""Adapter TrackDatasource that feeds pyPhoTimeline from stream_viewer's LSLDataSource."""

from __future__ import annotations

import time
from collections import deque
from typing import List, Optional, Tuple, Any

import numpy as np
import pandas as pd
from qtpy import QtCore
import pyqtgraph as pg

from pypho_timeline.rendering.datasources.track_datasource import IntervalProvidingTrackDatasource
from pypho_timeline.utils.datetime_helpers import unix_timestamp_to_datetime
from pypho_timeline.rendering.datasources.specific.eeg import EEGPlotDetailRenderer
from pypho_timeline.rendering.datasources.specific.motion import MotionPlotDetailRenderer
from pypho_timeline.rendering.detail_renderers.generic_plot_renderer import DataframePlotDetailRenderer
from pypho_timeline.rendering.helpers import ChannelNormalizationMode

from stream_viewer.data.stream_lsl import LSLDataSource


# ─────────────────────────────────────────────────────────────────────────────
# Ring buffer (thread-safe, same interface as pyPhoTimeline's _LiveRingBuffer)
# ─────────────────────────────────────────────────────────────────────────────

class _LiveRingBuffer:
    """Thread-safe ring buffer keeping the most recent buffer_seconds of data. Samples are (n_samples, n_channels)."""

    def __init__(self, channel_names: List[str], buffer_seconds: float = 300.0) -> None:
        self._channel_names = list(channel_names)
        self._buffer_seconds = buffer_seconds
        self._chunks: deque = deque()
        self._total_samples: int = 0
        self._lock = QtCore.QMutex()

    def append(self, timestamps: np.ndarray, samples: np.ndarray, channel_names: List[str]) -> None:
        if len(timestamps) == 0:
            return
        if channel_names != self._channel_names:
            self._channel_names = list(channel_names)
            self._chunks.clear()
            self._total_samples = 0
        locker = QtCore.QMutexLocker(self._lock)
        self._chunks.append((timestamps.copy(), samples.copy()))
        self._total_samples += len(timestamps)
        self._trim()

    def _trim(self) -> None:
        if not self._chunks:
            return
        latest_ts = self._chunks[-1][0][-1]
        cutoff = latest_ts - self._buffer_seconds
        while self._chunks:
            oldest_ts = self._chunks[0][0]
            if oldest_ts[-1] < cutoff:
                removed = len(oldest_ts)
                self._chunks.popleft()
                self._total_samples -= removed
            else:
                break

    def to_dataframe(self) -> pd.DataFrame:
        locker = QtCore.QMutexLocker(self._lock)
        if not self._chunks:
            return pd.DataFrame(columns=["t"] + self._channel_names)
        ts_parts = [c[0] for c in self._chunks]
        samp_parts = [c[1] for c in self._chunks]
        all_ts = np.concatenate(ts_parts)
        all_samp = np.concatenate(samp_parts, axis=0)
        df = pd.DataFrame(all_samp, columns=self._channel_names)
        df.insert(0, "t", all_ts)
        return df

    def get_window(self, t_start: float, t_end: float) -> pd.DataFrame:
        df = self.to_dataframe()
        if df.empty:
            return df
        mask = (df["t"] >= t_start) & (df["t"] <= t_end)
        return df.loc[mask].reset_index(drop=True)

    @property
    def latest_timestamp(self) -> Optional[float]:
        locker = QtCore.QMutexLocker(self._lock)
        if not self._chunks:
            return None
        return float(self._chunks[-1][0][-1])

    @property
    def earliest_timestamp(self) -> Optional[float]:
        locker = QtCore.QMutexLocker(self._lock)
        if not self._chunks:
            return None
        return float(self._chunks[0][0][0])

    @property
    def channel_names(self) -> List[str]:
        return list(self._channel_names)


def _make_stub_intervals_df(t_start: float, t_end: Optional[float] = None) -> pd.DataFrame:
    if t_end is None:
        t_end = t_start + 1.0
    duration = max(float(t_end) - float(t_start), 1.0)
    return pd.DataFrame({"t_start": [float(t_start)], "t_duration": [duration], "t_end": [float(t_end)]})


def _stub_intervals_with_visualization_columns(t_start: float, t_end: float) -> pd.DataFrame:
    """Build stub intervals DataFrame with t_start_dt, t_end_dt, series_*, pen, brush for timeline rendering."""
    duration = max(float(t_end) - float(t_start), 1.0)
    df = pd.DataFrame({"t_start": [float(t_start)], "t_duration": [duration], "t_end": [float(t_end)]})
    df["t_start_dt"] = df["t_start"].map(unix_timestamp_to_datetime)
    df["t_end_dt"] = df["t_start_dt"] + pd.to_timedelta(df["t_duration"], unit="s")
    df = df.astype({"t_start_dt": "datetime64[ns]", "t_end_dt": "datetime64[ns]"})
    df["series_vertical_offset"] = 0.0
    df["series_height"] = 1.0
    color = pg.mkColor("grey")
    color.setAlphaF(0.7)
    pen = pg.mkPen(color, width=1)
    brush = pg.mkBrush(color)
    df["pen"] = [pen] * len(df)
    df["brush"] = [brush] * len(df)
    return df


# ─────────────────────────────────────────────────────────────────────────────
# StreamViewerLSLTrackDatasource
# ─────────────────────────────────────────────────────────────────────────────

class StreamViewerLSLTrackDatasource(IntervalProvidingTrackDatasource):
    """TrackDatasource that wraps stream_viewer's LSLDataSource for pyPhoTimeline.

    Keeps a ring buffer of the last buffer_seconds of data. One growing interval is
    exposed; fetch_detailed_data returns a DataFrame slice. Use get_detail_renderer()
    for EEG, Motion, or generic time-series (Dataframe) rendering.
    """

    new_data_available = QtCore.Signal()

    def __init__(self, lsl_data_source: LSLDataSource, buffer_seconds: float = 300.0, stream_type: Optional[str] = None, channel_names: Optional[List[str]] = None, custom_datasource_name: Optional[str] = None, poll_interval_ms: int = 100, parent: Optional[QtCore.QObject] = None) -> None:
        now = time.time()
        stub = _make_stub_intervals_df(now - buffer_seconds, now)
        super().__init__(intervals_df=stub, detailed_df=None, custom_datasource_name=custom_datasource_name or "LiveLSL", parent=parent)
        self._buffer_seconds = buffer_seconds
        self._stream_type = (stream_type or "").strip() or None
        self._channel_names: List[str] = list(channel_names) if channel_names else []
        self._ring = _LiveRingBuffer(self._channel_names, buffer_seconds)
        self._lsl_source = lsl_data_source
        self._poll_interval_ms = poll_interval_ms
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._lsl_source.state_changed.connect(self._on_source_changed)

    def _on_source_changed(self, _src: Any) -> None:
        stats = getattr(self._lsl_source, "data_stats", None)
        if callable(stats):
            try:
                s = stats()
                if s and s.get("channel_names"):
                    self._channel_names = s["channel_names"]
                    self._ring = _LiveRingBuffer(self._channel_names, self._buffer_seconds)
            except Exception:
                pass

    def start_polling(self) -> None:
        """Start the timer that pulls from LSLDataSource and fills the ring buffer."""
        self._timer.start(self._poll_interval_ms)

    def stop_polling(self) -> None:
        self._timer.stop()

    def _poll(self) -> None:
        data, timestamps = self._lsl_source.fetch_data()
        if timestamps is None or len(timestamps) == 0:
            return
        timestamps = np.asarray(timestamps, dtype=np.float64)
        if data.ndim == 2 and data.shape[0] > 0:
            samples = np.asarray(data.T, dtype=np.float64)
        else:
            return
        ch_names = self._channel_names
        if not ch_names and data.shape[0] > 0:
            ch_names = [f"ch{i}" for i in range(data.shape[0])]
            self._channel_names = ch_names
            self._ring = _LiveRingBuffer(ch_names, self._buffer_seconds)
        self._ring.append(timestamps, samples, ch_names)
        self._update_intervals()
        self.new_data_available.emit()
        self.source_data_changed_signal.emit()

    def _update_intervals(self) -> None:
        t0 = self._ring.earliest_timestamp
        t1 = self._ring.latest_timestamp
        if t0 is None or t1 is None:
            return
        self.intervals_df = _stub_intervals_with_visualization_columns(t0, t1)

    @property
    def total_df_start_end_times(self) -> Tuple[float, float]:
        t0 = self._ring.earliest_timestamp
        t1 = self._ring.latest_timestamp
        if t0 is None or t1 is None:
            now = time.time()
            return (now, now)
        return (float(t0), float(t1))

    def fetch_detailed_data(self, interval: pd.Series) -> pd.DataFrame:
        t_start = float(interval.get("t_start", 0.0))
        t_duration = float(interval.get("t_duration", 0.0))
        t_end = t_start + t_duration
        return self._ring.get_window(t_start, t_end)

    def get_detail_renderer(self) -> Any:
        ch_names = self._channel_names or ["ch0"]
        st = (self._stream_type or "").lower()
        if st == "eeg":
            return EEGPlotDetailRenderer(pen_width=1, channel_names=ch_names, fallback_normalization_mode=ChannelNormalizationMode.GROUPMINMAXRANGE, normalize=True, normalize_over_full_data=False)
        if st in ("accelerometer", "gyroscope", "motion", "imu"):
            return MotionPlotDetailRenderer(pen_width=1, channel_names=ch_names)
        return DataframePlotDetailRenderer(pen_width=1, channel_names=ch_names, fallback_normalization_mode=ChannelNormalizationMode.GROUPMINMAXRANGE, normalize=True, normalize_over_full_data=False)

    @property
    def live_timestamp(self) -> Optional[float]:
        return self._ring.latest_timestamp

    def get_full_buffer_df(self) -> pd.DataFrame:
        return self._ring.to_dataframe()
