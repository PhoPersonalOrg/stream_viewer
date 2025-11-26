#  Copyright (C) 2024 Pho Hale. All rights reserved.

"""
Audio display base class for sonification renderers.

This module provides the base infrastructure for audio output,
similar to how pyqtgraph.py provides base infrastructure for visual output.
"""

import logging
import numpy as np
from qtpy import QtCore
from stream_viewer.renderers.display.base import RendererBaseDisplay

logger = logging.getLogger(__name__)

# Try to import sounddevice for audio output
try:
    import sounddevice as sd
    HAS_SOUNDDEVICE = True
except ImportError:
    HAS_SOUNDDEVICE = False
    logger.warning("sounddevice not installed. Audio output will be disabled. "
                   "Install with: pip install sounddevice")


class AudioRenderer(RendererBaseDisplay):
    """
    Mix-in for audio-based renderers (sonification).
    
    This class provides the timing and audio output infrastructure
    for renderers that convert EEG data to sound.
    
    Mixed-in target must also inherit from a stream_viewer.renderers.data.base class
    or implement its own `on_timer` and `fetch_data` methods.
    """
    
    # Available synthesis modes
    SYNTH_MODES = ['sine', 'sawtooth', 'square', 'triangle', 'noise', 'additive']
    
    # Timer interval in ms - audio needs faster updates than visual
    TIMER_INTERVAL = int(1000 / 30)  # 30 Hz update rate
    
    # Audio settings
    DEFAULT_SAMPLE_RATE = 44100
    DEFAULT_BLOCK_SIZE = 1024
    
    gui_kwargs = {
        'audio_enabled': bool,
        'volume': float,
        'base_freq': float,
        'freq_range': float,
        'synth_mode': str,
        # Note: audio_device is not in gui_kwargs because it can be None and
        # device indices may change between sessions
    }

    def __init__(self,
                 audio_enabled: bool = True,
                 volume: float = 0.3,
                 base_freq: float = 220.0,
                 freq_range: float = 440.0,
                 synth_mode: str = 'sine',
                 audio_sample_rate: int = DEFAULT_SAMPLE_RATE,
                 audio_block_size: int = DEFAULT_BLOCK_SIZE,
                 audio_device: int = None,
                 **kwargs):
        """
        Initialize the audio renderer.
        
        Args:
            audio_enabled: Whether audio output is enabled.
            volume: Master volume (0.0 to 1.0).
            base_freq: Base frequency in Hz for pitch mapping.
            freq_range: Frequency range in Hz for pitch variation.
            synth_mode: Synthesis waveform type ('sine', 'sawtooth', 'square', 'triangle', 'noise', 'additive').
            audio_sample_rate: Audio sample rate in Hz.
            audio_block_size: Audio buffer block size in samples.
            audio_device: Audio output device index (None for default). Use list_audio_devices() to see available devices.
            **kwargs: Additional arguments passed to parent classes.
        """
        self._audio_enabled = audio_enabled and HAS_SOUNDDEVICE
        self._volume = float(np.clip(volume, 0.0, 1.0))
        self._base_freq = base_freq
        self._freq_range = freq_range
        self._synth_mode = synth_mode
        self._audio_sample_rate = audio_sample_rate
        self._audio_block_size = audio_block_size
        self._audio_device = audio_device
        
        # Audio state
        self._audio_stream = None
        self._phase = 0.0  # For continuous waveform generation
        self._channel_phases = None  # Per-channel phases for polyphonic synthesis
        self._current_freqs = None  # Current frequencies for each channel
        self._current_amps = None   # Current amplitudes for each channel
        self._target_freqs = None   # Target frequencies (for smoothing)
        self._target_amps = None    # Target amplitudes (for smoothing)
        
        # Smoothing factor for parameter changes (prevents clicks)
        self._smoothing = 0.1
        
        super().__init__(**kwargs)
        
        # Timer for data fetching
        self._timer = QtCore.QTimer()
        self._timer.timeout.connect(self.on_timer)
        
        # Initialize audio stream if enabled
        if self._audio_enabled:
            self._init_audio_stream()

    def _init_audio_stream(self):
        """Initialize the audio output stream."""
        if not HAS_SOUNDDEVICE:
            return
        
        device_name = "default"
        if self._audio_device is not None:
            try:
                device_info = sd.query_devices(self._audio_device)
                device_name = device_info['name']
            except Exception:
                device_name = f"device {self._audio_device}"
            
        try:
            self._audio_stream = sd.OutputStream(
                samplerate=self._audio_sample_rate,
                blocksize=self._audio_block_size,
                device=self._audio_device,
                channels=1,  # Mono output (mixed from all channels)
                dtype='float32',
                callback=self._audio_callback
            )
            logger.info(f"Audio stream initialized: {self._audio_sample_rate} Hz, "
                       f"block size {self._audio_block_size}, device: {device_name}")
        except Exception as e:
            logger.error(f"Failed to initialize audio stream: {e}")
            self._audio_enabled = False

    def _audio_callback(self, outdata, frames, time_info, status):
        """
        Audio stream callback - generates audio samples.
        
        This is called by sounddevice in a separate thread.
        """
        if status:
            logger.warning(f"Audio callback status: {status}")
        
        if self._current_freqs is None or self._current_amps is None:
            # No data yet, output silence
            outdata.fill(0)
            return
        
        # Safety check for empty arrays
        if len(self._current_freqs) == 0 or len(self._current_amps) == 0:
            outdata.fill(0)
            return
        
        # Smooth parameter transitions
        if self._target_freqs is not None:
            self._current_freqs = (1 - self._smoothing) * self._current_freqs + self._smoothing * self._target_freqs
        if self._target_amps is not None:
            self._current_amps = (1 - self._smoothing) * self._current_amps + self._smoothing * self._target_amps
        
        # Generate audio for each channel and mix
        t = np.arange(frames) / self._audio_sample_rate
        mixed_signal = np.zeros(frames, dtype=np.float32)
        
        n_channels = len(self._current_freqs)
        if n_channels == 0:
            outdata[:] = 0
            return
        
        for ch_idx in range(n_channels):
            freq = self._current_freqs[ch_idx]
            amp = self._current_amps[ch_idx]
            
            if amp < 0.001:  # Skip very quiet channels
                continue
            
            # Generate waveform based on synthesis mode
            phase = self._channel_phases[ch_idx] if self._channel_phases is not None else 0
            signal = self._generate_waveform(t, freq, phase)
            mixed_signal += signal * amp
            
            # Update phase for continuity
            if self._channel_phases is not None:
                self._channel_phases[ch_idx] = (phase + 2 * np.pi * freq * frames / self._audio_sample_rate) % (2 * np.pi)
        
        # Normalize and apply master volume
        if n_channels > 1:
            mixed_signal /= np.sqrt(n_channels)  # Prevent clipping when mixing
        mixed_signal *= self._volume
        
        # Soft clip to prevent harsh distortion
        mixed_signal = np.tanh(mixed_signal)
        
        outdata[:, 0] = mixed_signal

    def _generate_waveform(self, t: np.ndarray, freq: float, phase: float = 0.0) -> np.ndarray:
        """
        Generate waveform samples based on the current synthesis mode.
        
        Args:
            t: Time array in seconds.
            freq: Frequency in Hz.
            phase: Initial phase in radians.
            
        Returns:
            Array of waveform samples.
        """
        omega = 2 * np.pi * freq
        theta = omega * t + phase
        
        if self._synth_mode == 'sine':
            return np.sin(theta)
        elif self._synth_mode == 'sawtooth':
            return 2 * (theta / (2 * np.pi) % 1) - 1
        elif self._synth_mode == 'square':
            return np.sign(np.sin(theta))
        elif self._synth_mode == 'triangle':
            return 2 * np.abs(2 * (theta / (2 * np.pi) % 1) - 1) - 1
        elif self._synth_mode == 'noise':
            # Filtered noise modulated by frequency
            noise = np.random.randn(len(t))
            # Simple lowpass via moving average
            kernel_size = max(1, int(self._audio_sample_rate / freq / 4))
            if kernel_size > 1:
                kernel = np.ones(kernel_size) / kernel_size
                noise = np.convolve(noise, kernel, mode='same')
            return noise
        elif self._synth_mode == 'additive':
            # Additive synthesis with harmonics
            signal = np.sin(theta)
            for harmonic in range(2, 6):
                signal += np.sin(harmonic * theta) / harmonic
            return signal / 2  # Normalize
        else:
            return np.sin(theta)  # Default to sine

    def update_audio_params(self, freqs: np.ndarray, amps: np.ndarray):
        """
        Update the target frequencies and amplitudes for audio synthesis.
        
        Args:
            freqs: Array of frequencies for each channel.
            amps: Array of amplitudes for each channel.
        """
        self._target_freqs = np.array(freqs, dtype=np.float32)
        self._target_amps = np.array(amps, dtype=np.float32)
        
        # Initialize current values if needed
        if self._current_freqs is None or len(self._current_freqs) != len(freqs):
            self._current_freqs = self._target_freqs.copy()
            self._current_amps = self._target_amps.copy()
            self._channel_phases = np.zeros(len(freqs), dtype=np.float32)

    @property
    def native_widget(self):
        """Return None as audio renderers don't have a visual widget."""
        return None

    def stop_timer(self):
        """Stop the data fetch timer."""
        self._timer.stop()

    def restart_timer(self):
        """Restart the data fetch timer."""
        if self._timer.isActive():
            self._timer.stop()
        self._timer.start(self.TIMER_INTERVAL)

    def start_audio(self):
        """Start the audio output stream."""
        if not HAS_SOUNDDEVICE:
            logger.warning("sounddevice not available - cannot start audio")
            return
        
        # Initialize stream if needed
        if self._audio_stream is None:
            self._init_audio_stream()
        
        if self._audio_stream is not None and not self._audio_stream.active:
            try:
                self._audio_stream.start()
                logger.info("Audio stream started")
            except Exception as e:
                logger.error(f"Failed to start audio stream: {e}")

    def stop_audio(self):
        """Stop the audio output stream."""
        if self._audio_stream is not None and self._audio_stream.active:
            try:
                self._audio_stream.stop()
                logger.info("Audio stream stopped")
            except Exception as e:
                logger.error(f"Failed to stop audio stream: {e}")

    def close_audio(self):
        """Close and cleanup the audio stream."""
        if self._audio_stream is not None:
            try:
                self._audio_stream.close()
                self._audio_stream = None
                logger.info("Audio stream closed")
            except Exception as e:
                logger.error(f"Failed to close audio stream: {e}")

    def play_test_tone(self, frequency: float = 440.0, duration: float = 1.0, volume: float = None):
        """
        Play a simple test tone to verify audio output is working.
        
        This uses blocking playback (sd.play) which is separate from the 
        streaming callback system, useful for diagnosing audio issues.
        
        Args:
            frequency: Tone frequency in Hz (default 440 Hz = A4).
            duration: Duration in seconds.
            volume: Volume 0-1 (defaults to current volume setting).
        """
        if not HAS_SOUNDDEVICE:
            logger.error("sounddevice not available - cannot play test tone")
            return False
        
        if volume is None:
            volume = self._volume
        
        logger.info(f"Playing test tone: {frequency} Hz for {duration}s at volume {volume:.0%}")
        
        try:
            # Generate tone
            t = np.linspace(0, duration, int(self._audio_sample_rate * duration), dtype=np.float32)
            tone = (volume * np.sin(2 * np.pi * frequency * t)).astype(np.float32)
            
            # Apply fade in/out to prevent clicks (50ms)
            fade_samples = int(self._audio_sample_rate * 0.05)
            if fade_samples > 0 and len(tone) > 2 * fade_samples:
                fade_in = np.linspace(0, 1, fade_samples, dtype=np.float32)
                fade_out = np.linspace(1, 0, fade_samples, dtype=np.float32)
                tone[:fade_samples] *= fade_in
                tone[-fade_samples:] *= fade_out
            
            # Play (blocking) - use same device as streaming
            sd.play(tone, self._audio_sample_rate, device=self._audio_device, blocking=True)
            logger.info("Test tone completed")
            return True
        except Exception as e:
            logger.error(f"Test tone failed: {e}")
            return False

    def set_constant_tone(self, frequency: float = 440.0, amplitude: float = 0.5):
        """
        Set the audio output to a constant tone (useful for testing).
        
        This sets the streaming audio to output a constant frequency.
        Call with amplitude=0 to stop the tone.
        
        Args:
            frequency: Tone frequency in Hz.
            amplitude: Amplitude 0-1.
        """
        if not HAS_SOUNDDEVICE:
            logger.warning("sounddevice not available - cannot set constant tone")
            return
        
        # Ensure audio stream is initialized and running
        self.start_audio()
        
        # Set the audio parameters immediately (bypass smoothing for first value)
        freqs = np.array([frequency], dtype=np.float32)
        amps = np.array([amplitude], dtype=np.float32)
        
        self._target_freqs = freqs.copy()
        self._target_amps = amps.copy()
        self._current_freqs = freqs.copy()
        self._current_amps = amps.copy()
        self._channel_phases = np.zeros(1, dtype=np.float32)
        
        logger.info(f"Set constant tone: {frequency} Hz at amplitude {amplitude:.0%}")
        logger.info(f"  Stream active: {self._audio_stream.active if self._audio_stream else 'None'}")
        logger.info(f"  Current freqs: {self._current_freqs}")
        logger.info(f"  Current amps: {self._current_amps}")

    def play_streaming_test(self, frequency: float = 440.0, duration: float = 2.0):
        """
        Test the streaming audio callback by playing a tone for a fixed duration.
        
        Unlike play_test_tone (which uses blocking sd.play), this tests the
        actual streaming callback system that SonifyAudio uses.
        
        Args:
            frequency: Tone frequency in Hz.
            duration: Duration in seconds.
        """
        import time
        
        if not HAS_SOUNDDEVICE:
            logger.error("sounddevice not available")
            return False
        
        logger.info(f"Testing streaming audio: {frequency} Hz for {duration}s")
        
        # Set constant tone
        self.set_constant_tone(frequency=frequency, amplitude=0.5)
        
        # Wait
        time.sleep(duration)
        
        # Stop tone
        self.set_constant_tone(frequency=frequency, amplitude=0.0)
        
        logger.info("Streaming test completed")
        return True

    # Properties with Qt slots for GUI integration
    
    @property
    def audio_enabled(self):
        return self._audio_enabled
    
    @audio_enabled.setter
    def audio_enabled(self, value):
        self._audio_enabled = value and HAS_SOUNDDEVICE
        if self._audio_enabled:
            if self._audio_stream is None:
                self._init_audio_stream()
            self.start_audio()
        else:
            self.stop_audio()

    @QtCore.Slot(int)
    def audio_enabled_stateChanged(self, state):
        self.audio_enabled = state > 0

    @property
    def volume(self):
        return self._volume
    
    @volume.setter
    def volume(self, value):
        self._volume = float(np.clip(value, 0.0, 1.0))

    @QtCore.Slot(float)
    def volume_valueChanged(self, value):
        self.volume = value

    @property
    def base_freq(self):
        return self._base_freq
    
    @base_freq.setter
    def base_freq(self, value):
        self._base_freq = max(20.0, min(value, 2000.0))

    @QtCore.Slot(float)
    def base_freq_valueChanged(self, value):
        self.base_freq = value

    @property
    def freq_range(self):
        return self._freq_range
    
    @freq_range.setter
    def freq_range(self, value):
        self._freq_range = max(0.0, min(value, 4000.0))

    @QtCore.Slot(float)
    def freq_range_valueChanged(self, value):
        self.freq_range = value

    @property
    def synth_mode(self):
        return self._synth_mode
    
    @synth_mode.setter
    def synth_mode(self, value):
        if value in self.SYNTH_MODES:
            self._synth_mode = value

    @QtCore.Slot(str)
    def synth_mode_currentTextChanged(self, value):
        self.synth_mode = value

    @property
    def audio_device(self):
        return self._audio_device
    
    @audio_device.setter
    def audio_device(self, value):
        if value != self._audio_device:
            self._audio_device = value
            # Reinitialize audio stream with new device
            if self._audio_stream is not None:
                was_active = self._audio_stream.active
                self.close_audio()
                self._init_audio_stream()
                if was_active:
                    self.start_audio()

    @QtCore.Slot(int)
    def audio_device_valueChanged(self, value):
        self.audio_device = value if value >= 0 else None

    @staticmethod
    def list_audio_devices():
        """
        List available audio output devices.
        
        Returns:
            List of (index, name, channels) tuples for output devices.
        """
        if not HAS_SOUNDDEVICE:
            return []
        
        devices = []
        all_devices = sd.query_devices()
        for i, d in enumerate(all_devices):
            if d['max_output_channels'] > 0:
                devices.append((i, d['name'], d['max_output_channels']))
        return devices

    @staticmethod
    def get_default_device():
        """Get the default output device index and name."""
        if not HAS_SOUNDDEVICE:
            return None, "N/A"
        
        default_idx = sd.default.device[1]
        try:
            device_info = sd.query_devices(default_idx)
            return default_idx, device_info['name']
        except Exception:
            return default_idx, "Unknown"

    def __del__(self):
        """Cleanup on deletion."""
        self.close_audio()

