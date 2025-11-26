#  Copyright (C) 2024 Pho Hale. All rights reserved.

"""
EEG Sonification Renderer - Converts EEG data to audio in real-time.

This renderer maps EEG signal features to audio parameters, creating
an auditory representation of brain activity. Inspired by eegsynth
(https://github.com/eegsynth/eegsynth).

Features:
- Multiple mapping modes (amplitude, frequency bands, spectral)
- Per-channel or merged audio output
- Various synthesis waveforms
- Real-time parameter smoothing for pleasant audio
"""

import logging
import json
import numpy as np
from scipy import signal as scipy_signal
from qtpy import QtCore
from qtpy import QtWidgets

from stream_viewer.renderers.data.base import RendererBufferData
from stream_viewer.renderers.display.audio import AudioRenderer, HAS_SOUNDDEVICE

logger = logging.getLogger(__name__)


class SonifyAudio(RendererBufferData, AudioRenderer):
    """
    EEG Sonification renderer that converts EEG signals to audio.
    
    This renderer processes EEG data and maps various features
    (amplitude, power in frequency bands, etc.) to audio parameters
    (pitch, volume) to create a real-time auditory representation
    of brain activity.
    
    Mapping Modes:
        - 'amplitude': Direct mapping of signal amplitude to pitch
        - 'alpha': Alpha band (8-13 Hz) power to pitch
        - 'beta': Beta band (13-30 Hz) power to pitch  
        - 'theta': Theta band (4-8 Hz) power to pitch
        - 'delta': Delta band (1-4 Hz) power to pitch
        - 'gamma': Gamma band (30-100 Hz) power to pitch
        - 'spectral': Spectral centroid to pitch
        - 'rms': RMS energy to volume (combined with amplitude mapping)
    """
    
    COMPAT_ICONTROL = ['SonifyControlPanel']  # Compatible control panels
    
    # Available mapping modes for EEG-to-audio conversion
    MAPPING_MODES = [
        'amplitude',  # Direct amplitude mapping
        'alpha',      # Alpha band power (8-13 Hz)
        'beta',       # Beta band power (13-30 Hz)
        'theta',      # Theta band power (4-8 Hz)
        'delta',      # Delta band power (1-4 Hz)
        'gamma',      # Gamma band power (30-100 Hz)
        'spectral',   # Spectral centroid
        'rms',        # RMS energy
    ]
    
    # Frequency band definitions (Hz)
    FREQ_BANDS = {
        'delta': (1, 4),
        'theta': (4, 8),
        'alpha': (8, 13),
        'beta': (13, 30),
        'gamma': (30, 44),
    }
    
    gui_kwargs = dict(
        RendererBufferData.gui_kwargs,
        **AudioRenderer.gui_kwargs,
        mapping_mode=str,
        polyphonic=bool,
        pitch_per_channel=bool,
        note_quantize=bool,
        min_note=int,
        max_note=int,
    )

    def __init__(self,
                 # Override inherited defaults
                 auto_scale: str = 'by-channel',
                 duration: float = 1.0,  # Shorter buffer for lower latency
                 # Audio settings (inherited from AudioRenderer)
                 audio_enabled: bool = True,
                 volume: float = 0.3,
                 base_freq: float = 220.0,
                 freq_range: float = 440.0,
                 synth_mode: str = 'sine',
                 # Sonification-specific settings
                 mapping_mode: str = 'amplitude',
                 polyphonic: bool = True,
                 pitch_per_channel: bool = True,
                 note_quantize: bool = False,
                 min_note: int = 36,   # C2 in MIDI
                 max_note: int = 84,   # C6 in MIDI
                 **kwargs):
        """
        Initialize the EEG sonification renderer.
        
        Args:
            auto_scale: Auto-scaling mode for data normalization.
            duration: Buffer duration in seconds (shorter = lower latency).
            audio_enabled: Whether audio output is enabled.
            volume: Master volume (0.0 to 1.0).
            base_freq: Base frequency in Hz for pitch mapping.
            freq_range: Frequency range in Hz for pitch variation.
            synth_mode: Synthesis waveform type.
            mapping_mode: How to map EEG features to pitch ('amplitude', 'alpha', etc.).
            polyphonic: If True, each channel produces a separate tone.
            pitch_per_channel: If True, channels get different base pitches.
            note_quantize: If True, quantize pitches to musical notes.
            min_note: Minimum MIDI note number for pitch range.
            max_note: Maximum MIDI note number for pitch range.
            **kwargs: Additional arguments passed to parent classes.
        """
        # Sonification-specific params
        self._mapping_mode = mapping_mode
        self._polyphonic = polyphonic
        self._pitch_per_channel = pitch_per_channel
        self._note_quantize = note_quantize
        self._min_note = min_note
        self._max_note = max_note
        
        # Filter state for band power extraction
        self._band_filters = {}
        self._band_zi = {}
        
        # For spectral analysis
        self._fft_size = 256
        
        # Placeholder widget for compatibility
        self._widget = None
        
        super().__init__(
            auto_scale=auto_scale,
            duration=duration,
            audio_enabled=audio_enabled,
            volume=volume,
            base_freq=base_freq,
            freq_range=freq_range,
            synth_mode=synth_mode,
            **kwargs
        )
        
        self.reset_renderer()

    def reset_renderer(self, reset_channel_labels=True):
        """Reset the renderer state."""
        # Reset band filters when sample rate might have changed
        self._band_filters = {}
        self._band_zi = {}
        
        # Initialize widget if needed (minimal status display)
        if self._widget is None:
            self._widget = self._create_status_widget()
        
        # Start audio if enabled
        if self._audio_enabled and HAS_SOUNDDEVICE:
            self.start_audio()

    def _create_status_widget(self) -> QtWidgets.QWidget:
        """Create a minimal status widget for the sonification renderer."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        
        # Title
        title = QtWidgets.QLabel("🔊 EEG Sonification")
        title.setStyleSheet("font-size: 16pt; font-weight: bold; color: #00ff88;")
        title.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(title)
        
        # Status info
        self._status_label = QtWidgets.QLabel("Initializing...")
        self._status_label.setStyleSheet("font-size: 10pt; color: #aaaaaa;")
        self._status_label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(self._status_label)
        
        # Level meters placeholder
        self._level_container = QtWidgets.QWidget()
        self._level_layout = QtWidgets.QHBoxLayout(self._level_container)
        layout.addWidget(self._level_container)
        
        # Audio indicator
        self._audio_indicator = QtWidgets.QLabel("● Audio: " + ("ON" if self._audio_enabled else "OFF"))
        self._audio_indicator.setStyleSheet(
            f"font-size: 12pt; color: {'#00ff00' if self._audio_enabled else '#ff0000'};"
        )
        self._audio_indicator.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(self._audio_indicator)
        
        # Mode display
        mode_label = QtWidgets.QLabel(f"Mode: {self._mapping_mode.title()} → {self._synth_mode.title()}")
        mode_label.setStyleSheet("font-size: 10pt; color: #88aaff;")
        mode_label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(mode_label)
        
        layout.addStretch()
        
        widget.setStyleSheet("background-color: #1a1a2e;")
        return widget

    def _update_status(self, n_channels: int, levels: np.ndarray):
        """Update the status widget with current information."""
        if hasattr(self, '_status_label'):
            n_sources = len(self._data_sources)
            self._status_label.setText(
                f"Sources: {n_sources} | Channels: {n_channels} | "
                f"Buffer: {self._duration:.1f}s"
            )
        
        if hasattr(self, '_audio_indicator'):
            active = self._audio_enabled and HAS_SOUNDDEVICE
            self._audio_indicator.setText("● Audio: " + ("ON" if active else "OFF"))
            self._audio_indicator.setStyleSheet(
                f"font-size: 12pt; color: {'#00ff00' if active else '#ff0000'};"
            )

    @property
    def native_widget(self):
        """Return the status widget."""
        return self._widget

    def _init_band_filter(self, band_name: str, srate: float):
        """Initialize a bandpass filter for the given frequency band."""
        if band_name not in self.FREQ_BANDS:
            return None, None
        
        low, high = self.FREQ_BANDS[band_name]
        
        # Ensure frequencies are valid for the sample rate
        nyq = srate / 2
        if high >= nyq:
            high = nyq - 1
        if low >= high:
            return None, None
        
        try:
            sos = scipy_signal.butter(4, [low / nyq, high / nyq], 
                                     btype='bandpass', output='sos')
            return sos, None  # zi will be initialized on first use
        except Exception as e:
            logger.warning(f"Failed to create filter for {band_name}: {e}")
            return None, None

    def _extract_band_power(self, data: np.ndarray, band_name: str, srate: float) -> np.ndarray:
        """
        Extract power in a specific frequency band.
        
        Args:
            data: EEG data array (channels x samples).
            band_name: Name of frequency band ('alpha', 'beta', etc.).
            srate: Sample rate in Hz.
            
        Returns:
            Array of band power values for each channel.
        """
        if band_name not in self._band_filters:
            sos, zi = self._init_band_filter(band_name, srate)
            if sos is None:
                return np.zeros(data.shape[0])
            self._band_filters[band_name] = sos
        
        sos = self._band_filters[band_name]
        
        # Initialize filter state if needed
        if band_name not in self._band_zi or self._band_zi[band_name] is None:
            zi = scipy_signal.sosfilt_zi(sos)
            self._band_zi[band_name] = np.tile(zi[:, None, :], (1, data.shape[0], 1))
        
        try:
            # Apply bandpass filter
            filtered, self._band_zi[band_name] = scipy_signal.sosfilt(
                sos, data, axis=-1, zi=self._band_zi[band_name]
            )
            
            # Calculate power (RMS of filtered signal)
            power = np.sqrt(np.mean(filtered ** 2, axis=-1))
            return power
        except Exception as e:
            logger.warning(f"Band power extraction failed: {e}")
            return np.zeros(data.shape[0])

    def _extract_spectral_centroid(self, data: np.ndarray, srate: float) -> np.ndarray:
        """
        Extract spectral centroid for each channel.
        
        The spectral centroid indicates the "center of mass" of the spectrum,
        providing a measure of spectral brightness.
        
        Args:
            data: EEG data array (channels x samples).
            srate: Sample rate in Hz.
            
        Returns:
            Array of spectral centroid values (Hz) for each channel.
        """
        n_channels, n_samples = data.shape
        
        # Use last portion of data for FFT
        fft_data = data[:, -min(n_samples, self._fft_size):]
        
        # Compute FFT
        freqs = np.fft.rfftfreq(fft_data.shape[-1], 1/srate)
        fft_mag = np.abs(np.fft.rfft(fft_data, axis=-1))
        
        # Compute spectral centroid
        centroids = np.zeros(n_channels)
        for ch in range(n_channels):
            mag = fft_mag[ch]
            total = np.sum(mag)
            if total > 0:
                centroids[ch] = np.sum(freqs * mag) / total
        
        return centroids

    def _extract_rms(self, data: np.ndarray) -> np.ndarray:
        """
        Extract RMS (root mean square) energy for each channel.
        
        Args:
            data: EEG data array (channels x samples).
            
        Returns:
            Array of RMS values for each channel.
        """
        return np.sqrt(np.mean(data ** 2, axis=-1))

    def _map_to_frequency(self, values: np.ndarray, n_channels: int) -> np.ndarray:
        """
        Map normalized values to frequencies.
        
        Args:
            values: Normalized values (0-1) for each channel.
            n_channels: Total number of channels.
            
        Returns:
            Array of frequencies in Hz.
        """
        if self._note_quantize:
            # Map to MIDI notes and convert to frequency
            note_range = self._max_note - self._min_note
            notes = self._min_note + values * note_range
            notes = np.round(notes).astype(int)
            # MIDI to frequency: f = 440 * 2^((n-69)/12)
            freqs = 440.0 * (2.0 ** ((notes - 69) / 12.0))
        else:
            # Linear frequency mapping
            freqs = self._base_freq + values * self._freq_range
        
        # Add per-channel offset for polyphonic mode
        if self._pitch_per_channel and n_channels > 1:
            # Spread channels across an octave
            octave_spread = np.linspace(0, 1, n_channels)
            freqs = freqs * (2.0 ** (octave_spread * 0.5))  # Half octave spread
        
        return freqs

    def update_visualization(self, data, timestamps) -> None:
        """
        Process EEG data and update audio parameters.
        
        This method extracts features from the EEG data based on the
        selected mapping mode and updates the audio synthesis parameters.
        
        Args:
            data: List of (signal_data, marker_data) tuples per source.
            timestamps: List of (signal_ts, marker_ts) tuples per source.
        """
        if not any([np.any(_[0]) for _ in timestamps]):
            return
        
        # Collect all channel data
        all_data = []
        all_srates = []
        
        for src_ix, src in enumerate(self._data_sources):
            dat, mrk = data[src_ix]
            if dat.size == 0:
                continue
            all_data.append(dat)
            all_srates.append(src.data_stats['srate'])
        
        if not all_data:
            return
        
        # Concatenate data from all sources
        combined_data = np.vstack(all_data) if len(all_data) > 1 else all_data[0]
        avg_srate = np.mean(all_srates)
        
        n_channels = combined_data.shape[0]
        
        # Extract features based on mapping mode
        if self._mapping_mode == 'amplitude':
            # Direct amplitude mapping (use last sample)
            features = combined_data[:, -1]
            # Normalize assuming data is already scaled to 0-1 by auto_scale
            features = np.clip(features + 0.5, 0, 1)  # Shift from [-0.5, 0.5] to [0, 1]
            amps = np.ones(n_channels) * 0.5
            
        elif self._mapping_mode in self.FREQ_BANDS:
            # Band power mapping
            features = self._extract_band_power(combined_data, self._mapping_mode, avg_srate)
            # Normalize with log scaling for better perceptual range
            features = np.log1p(features * 1000) / np.log1p(1000)
            features = np.clip(features, 0, 1)
            amps = features * 0.8 + 0.1  # Scale amplitude by power
            
        elif self._mapping_mode == 'spectral':
            # Spectral centroid mapping
            features = self._extract_spectral_centroid(combined_data, avg_srate)
            # Normalize to 0-1 (assuming centroid in 0-50 Hz range for EEG)
            features = np.clip(features / 50.0, 0, 1)
            amps = np.ones(n_channels) * 0.5
            
        elif self._mapping_mode == 'rms':
            # RMS energy to volume
            rms = self._extract_rms(combined_data)
            features = combined_data[:, -1]  # Use amplitude for pitch
            features = np.clip(features + 0.5, 0, 1)
            # Normalize RMS to amplitude
            amps = np.clip(np.log1p(rms * 100) / np.log1p(100), 0, 1)
            
        else:
            # Default to amplitude
            features = np.clip(combined_data[:, -1] + 0.5, 0, 1)
            amps = np.ones(n_channels) * 0.5
        
        # Map features to frequencies
        freqs = self._map_to_frequency(features, n_channels)
        
        # Handle mono/polyphonic modes
        if not self._polyphonic:
            # Mix to mono
            freqs = np.array([np.mean(freqs)])
            amps = np.array([np.mean(amps)])
        
        # Update audio parameters
        self.update_audio_params(freqs, amps)
        
        # Update status display
        self._update_status(n_channels, amps)

    def freeze(self) -> None:
        """Freeze the renderer and stop audio."""
        super().freeze()
        self.stop_audio()

    def unfreeze(self) -> None:
        """Unfreeze the renderer and start audio."""
        super().unfreeze()
        if self._audio_enabled:
            self.start_audio()

    # Properties with Qt slots
    
    @property
    def mapping_mode(self):
        return self._mapping_mode
    
    @mapping_mode.setter
    def mapping_mode(self, value):
        if value in self.MAPPING_MODES:
            self._mapping_mode = value
            # Reset band filters when mode changes
            self._band_filters = {}
            self._band_zi = {}

    @QtCore.Slot(str)
    def mapping_mode_currentTextChanged(self, value):
        self.mapping_mode = value

    @property
    def polyphonic(self):
        return self._polyphonic
    
    @polyphonic.setter
    def polyphonic(self, value):
        self._polyphonic = value

    @QtCore.Slot(int)
    def polyphonic_stateChanged(self, state):
        self.polyphonic = state > 0

    @property
    def pitch_per_channel(self):
        return self._pitch_per_channel
    
    @pitch_per_channel.setter
    def pitch_per_channel(self, value):
        self._pitch_per_channel = value

    @QtCore.Slot(int)
    def pitch_per_channel_stateChanged(self, state):
        self.pitch_per_channel = state > 0

    @property
    def note_quantize(self):
        return self._note_quantize
    
    @note_quantize.setter
    def note_quantize(self, value):
        self._note_quantize = value

    @QtCore.Slot(int)
    def note_quantize_stateChanged(self, state):
        self.note_quantize = state > 0

    @property
    def min_note(self):
        return self._min_note
    
    @min_note.setter
    def min_note(self, value):
        self._min_note = max(0, min(value, 127))

    @property
    def max_note(self):
        return self._max_note
    
    @max_note.setter
    def max_note(self, value):
        self._max_note = max(0, min(value, 127))

    def __del__(self):
        """Cleanup on deletion."""
        self.close_audio()

