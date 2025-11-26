#  Copyright (C) 2024 Pho Hale. All rights reserved.

"""
LSL EEG Sonification Application

This application creates an auditory representation of EEG data
streamed via Lab Streaming Layer. It converts EEG signals to sound
in real-time using various mapping strategies.

Usage:
    python -m stream_viewer.applications.lsl_sonify
    
    Or via command line:
    lsl_sonify
"""

import sys
from pathlib import Path
from qtpy import QtWidgets, QtCore, QtGui

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from stream_viewer.data import LSLDataSource
from stream_viewer.renderers import SonifyAudio


class SonificationControlPanel(QtWidgets.QWidget):
    """Control panel for the sonification renderer."""
    
    def __init__(self, renderer: SonifyAudio, parent=None):
        super().__init__(parent)
        self._renderer = renderer
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Setup the control panel UI."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Title
        title = QtWidgets.QLabel("🎵 Sonification Controls")
        title.setStyleSheet("font-size: 14pt; font-weight: bold; color: #00ccff;")
        layout.addWidget(title)
        
        # Audio Enable
        audio_group = QtWidgets.QGroupBox("Audio")
        audio_layout = QtWidgets.QVBoxLayout(audio_group)
        
        self._audio_enabled = QtWidgets.QCheckBox("Enable Audio Output")
        self._audio_enabled.setChecked(self._renderer.audio_enabled)
        audio_layout.addWidget(self._audio_enabled)
        
        # Volume slider
        vol_layout = QtWidgets.QHBoxLayout()
        vol_layout.addWidget(QtWidgets.QLabel("Volume:"))
        self._volume_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self._volume_slider.setMinimum(0)
        self._volume_slider.setMaximum(100)
        self._volume_slider.setValue(int(self._renderer.volume * 100))
        vol_layout.addWidget(self._volume_slider)
        self._volume_label = QtWidgets.QLabel(f"{int(self._renderer.volume * 100)}%")
        self._volume_label.setMinimumWidth(40)
        vol_layout.addWidget(self._volume_label)
        audio_layout.addLayout(vol_layout)
        
        # Test audio buttons
        test_layout = QtWidgets.QHBoxLayout()
        
        self._test_tone_btn = QtWidgets.QPushButton("🔊 Test Tone (1s)")
        self._test_tone_btn.setToolTip("Play a 440 Hz test tone for 1 second to verify audio output")
        self._test_tone_btn.setStyleSheet("""
            QPushButton { background-color: #2a4a2a; color: white; padding: 8px; }
            QPushButton:hover { background-color: #3a5a3a; }
            QPushButton:pressed { background-color: #1a3a1a; }
        """)
        test_layout.addWidget(self._test_tone_btn)
        
        self._constant_tone_btn = QtWidgets.QPushButton("🎵 Constant Tone")
        self._constant_tone_btn.setCheckable(True)
        self._constant_tone_btn.setToolTip("Toggle a constant 440 Hz tone (bypasses EEG data)")
        self._constant_tone_btn.setStyleSheet("""
            QPushButton { background-color: #4a4a2a; color: white; padding: 8px; }
            QPushButton:hover { background-color: #5a5a3a; }
            QPushButton:checked { background-color: #00aa00; color: white; }
        """)
        test_layout.addWidget(self._constant_tone_btn)
        
        audio_layout.addLayout(test_layout)
        
        # Device selection
        device_layout = QtWidgets.QFormLayout()
        self._device_combo = QtWidgets.QComboBox()
        self._device_combo.addItem("Default", -1)
        
        # Populate with available devices
        from stream_viewer.renderers.display.audio import AudioRenderer
        devices = AudioRenderer.list_audio_devices()
        for idx, name, channels in devices:
            # Truncate long names
            display_name = name[:40] + "..." if len(name) > 40 else name
            self._device_combo.addItem(f"[{idx}] {display_name}", idx)
        
        # Select current device
        current_device = self._renderer.audio_device
        if current_device is None:
            self._device_combo.setCurrentIndex(0)
        else:
            for i in range(self._device_combo.count()):
                if self._device_combo.itemData(i) == current_device:
                    self._device_combo.setCurrentIndex(i)
                    break
        
        device_layout.addRow("Output Device:", self._device_combo)
        audio_layout.addLayout(device_layout)
        
        layout.addWidget(audio_group)
        
        # Mapping Settings
        mapping_group = QtWidgets.QGroupBox("EEG → Audio Mapping")
        mapping_layout = QtWidgets.QFormLayout(mapping_group)
        
        self._mapping_mode = QtWidgets.QComboBox()
        self._mapping_mode.addItems(SonifyAudio.MAPPING_MODES)
        self._mapping_mode.setCurrentText(self._renderer.mapping_mode)
        mapping_layout.addRow("Mapping Mode:", self._mapping_mode)
        
        self._synth_mode = QtWidgets.QComboBox()
        self._synth_mode.addItems(SonifyAudio.SYNTH_MODES if hasattr(SonifyAudio, 'SYNTH_MODES') 
                                  else ['sine', 'sawtooth', 'square', 'triangle', 'noise', 'additive'])
        self._synth_mode.setCurrentText(self._renderer.synth_mode)
        mapping_layout.addRow("Waveform:", self._synth_mode)
        
        layout.addWidget(mapping_group)
        
        # Pitch Settings
        pitch_group = QtWidgets.QGroupBox("Pitch Settings")
        pitch_layout = QtWidgets.QFormLayout(pitch_group)
        
        self._base_freq = QtWidgets.QDoubleSpinBox()
        self._base_freq.setRange(20.0, 2000.0)
        self._base_freq.setValue(self._renderer.base_freq)
        self._base_freq.setSuffix(" Hz")
        pitch_layout.addRow("Base Frequency:", self._base_freq)
        
        self._freq_range = QtWidgets.QDoubleSpinBox()
        self._freq_range.setRange(0.0, 4000.0)
        self._freq_range.setValue(self._renderer.freq_range)
        self._freq_range.setSuffix(" Hz")
        pitch_layout.addRow("Frequency Range:", self._freq_range)
        
        self._polyphonic = QtWidgets.QCheckBox("Polyphonic (one tone per channel)")
        self._polyphonic.setChecked(self._renderer.polyphonic)
        pitch_layout.addRow("", self._polyphonic)
        
        self._pitch_per_channel = QtWidgets.QCheckBox("Spread channels across pitch range")
        self._pitch_per_channel.setChecked(self._renderer.pitch_per_channel)
        pitch_layout.addRow("", self._pitch_per_channel)
        
        self._note_quantize = QtWidgets.QCheckBox("Quantize to musical notes")
        self._note_quantize.setChecked(self._renderer.note_quantize)
        pitch_layout.addRow("", self._note_quantize)
        
        layout.addWidget(pitch_group)
        
        # Data Settings
        data_group = QtWidgets.QGroupBox("Data Processing")
        data_layout = QtWidgets.QFormLayout(data_group)
        
        self._duration = QtWidgets.QDoubleSpinBox()
        self._duration.setRange(0.1, 10.0)
        self._duration.setValue(self._renderer.duration)
        self._duration.setSuffix(" s")
        data_layout.addRow("Buffer Duration:", self._duration)
        
        self._highpass = QtWidgets.QDoubleSpinBox()
        self._highpass.setRange(0.0, 100.0)
        self._highpass.setValue(self._renderer.highpass_cutoff)
        self._highpass.setSuffix(" Hz")
        data_layout.addRow("Highpass Filter:", self._highpass)
        
        layout.addWidget(data_group)
        
        # Freeze/Unfreeze button
        self._freeze_btn = QtWidgets.QPushButton("⏸ Freeze")
        self._freeze_btn.setCheckable(True)
        self._freeze_btn.setStyleSheet("""
            QPushButton { background-color: #2a2a4a; color: white; padding: 10px; }
            QPushButton:checked { background-color: #ff4444; }
        """)
        layout.addWidget(self._freeze_btn)
        
        layout.addStretch()
        
        self.setStyleSheet("""
            QGroupBox { 
                font-weight: bold; 
                border: 1px solid #444; 
                border-radius: 5px; 
                margin-top: 10px; 
                padding-top: 10px;
            }
            QGroupBox::title { 
                subcontrol-origin: margin; 
                left: 10px; 
                padding: 0 5px; 
            }
        """)

    def _connect_signals(self):
        """Connect UI signals to renderer slots."""
        self._audio_enabled.stateChanged.connect(self._renderer.audio_enabled_stateChanged)
        
        self._volume_slider.valueChanged.connect(self._on_volume_changed)
        
        self._test_tone_btn.clicked.connect(self._on_test_tone)
        self._constant_tone_btn.toggled.connect(self._on_constant_tone_toggled)
        self._device_combo.currentIndexChanged.connect(self._on_device_changed)
        
        self._mapping_mode.currentTextChanged.connect(self._renderer.mapping_mode_currentTextChanged)
        self._synth_mode.currentTextChanged.connect(self._renderer.synth_mode_currentTextChanged)
        
        self._base_freq.valueChanged.connect(self._renderer.base_freq_valueChanged)
        self._freq_range.valueChanged.connect(self._renderer.freq_range_valueChanged)
        
        self._polyphonic.stateChanged.connect(self._renderer.polyphonic_stateChanged)
        self._pitch_per_channel.stateChanged.connect(self._renderer.pitch_per_channel_stateChanged)
        self._note_quantize.stateChanged.connect(self._renderer.note_quantize_stateChanged)
        
        self._duration.valueChanged.connect(self._renderer.duration_valueChanged)
        self._highpass.valueChanged.connect(self._renderer.highpass_cutoff_valueChanged)
        
        self._freeze_btn.toggled.connect(self._on_freeze_toggled)

    def _on_volume_changed(self, value):
        """Handle volume slider change."""
        self._renderer.volume = value / 100.0
        self._volume_label.setText(f"{value}%")

    def _on_test_tone(self):
        """Play a test tone to verify audio output."""
        self._test_tone_btn.setEnabled(False)
        self._test_tone_btn.setText("Playing...")
        QtWidgets.QApplication.processEvents()
        
        try:
            # Use blocking playback for test tone
            success = self._renderer.play_test_tone(frequency=440.0, duration=1.0)
            if not success:
                QtWidgets.QMessageBox.warning(
                    self, "Audio Test Failed",
                    "Could not play test tone.\n\n"
                    "Check your audio device settings and ensure sounddevice is installed."
                )
        finally:
            self._test_tone_btn.setEnabled(True)
            self._test_tone_btn.setText("🔊 Test Tone (1s)")

    def _on_constant_tone_toggled(self, checked):
        """Toggle constant tone output."""
        if checked:
            # Start constant tone at 440 Hz
            self._renderer.set_constant_tone(frequency=440.0, amplitude=0.5)
            # Make sure audio stream is running
            self._renderer.start_audio()
            self._constant_tone_btn.setText("🎵 Stop Tone")
        else:
            # Stop tone by setting amplitude to 0
            self._renderer.set_constant_tone(frequency=440.0, amplitude=0.0)
            self._constant_tone_btn.setText("🎵 Constant Tone")

    def _on_device_changed(self, index):
        """Handle device selection change."""
        device_idx = self._device_combo.itemData(index)
        self._renderer.audio_device = device_idx if device_idx >= 0 else None

    def _on_freeze_toggled(self, checked):
        """Handle freeze button toggle."""
        if checked:
            self._renderer.freeze()
            self._freeze_btn.setText("▶ Resume")
        else:
            self._renderer.unfreeze()
            self._freeze_btn.setText("⏸ Freeze")


class SonifyWindow(QtWidgets.QMainWindow):
    """Main window for the EEG Sonification application."""

    def __init__(self, stream_query: dict = None):
        super().__init__()
        self.setWindowTitle("StreamViewer - EEG Sonification")
        self.setMinimumSize(800, 600)
        
        # Default to EEG streams
        if stream_query is None:
            stream_query = {'type': 'EEG'}
        
        # Create renderer
        sonify_kwargs = dict(
            audio_enabled=True,
            volume=0.3,
            base_freq=220.0,
            freq_range=440.0,
            synth_mode='sine',
            mapping_mode='alpha',
            polyphonic=True,
            pitch_per_channel=True,
            duration=1.0,
            auto_scale='by-channel',
        )
        self._renderer = SonifyAudio(**sonify_kwargs)
        
        # Add data source
        try:
            self._renderer.add_source(LSLDataSource(stream_query))
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self, "Stream Warning",
                f"Could not connect to LSL stream: {e}\n\n"
                "Make sure an EEG stream is available."
            )
        
        # Create main layout
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QHBoxLayout(central)
        
        # Control panel on the left
        self._ctrl_panel = SonificationControlPanel(self._renderer)
        self._ctrl_panel.setMaximumWidth(350)
        layout.addWidget(self._ctrl_panel)
        
        # Renderer widget (status display) on the right
        renderer_widget = self._renderer.native_widget
        if renderer_widget is not None:
            layout.addWidget(renderer_widget, stretch=1)
        else:
            # Create a placeholder
            placeholder = QtWidgets.QLabel("Audio output only\n(no visual display)")
            placeholder.setAlignment(QtCore.Qt.AlignCenter)
            placeholder.setStyleSheet("font-size: 16pt; color: #666;")
            layout.addWidget(placeholder, stretch=1)
        
        # Apply dark theme
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #1a1a2e;
                color: #e0e0e0;
            }
            QLabel {
                color: #e0e0e0;
            }
            QGroupBox {
                color: #88aaff;
            }
            QComboBox, QSpinBox, QDoubleSpinBox {
                background-color: #2a2a4a;
                border: 1px solid #444;
                padding: 5px;
                color: white;
            }
            QSlider::groove:horizontal {
                background: #2a2a4a;
                height: 8px;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #00ccff;
                width: 16px;
                margin: -4px 0;
                border-radius: 8px;
            }
            QCheckBox {
                color: #e0e0e0;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
        """)

    def closeEvent(self, event):
        """Handle window close."""
        # Stop audio and cleanup
        self._renderer.freeze()
        self._renderer.close_audio()
        super().closeEvent(event)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="EEG Sonification via LSL")
    parser.add_argument('--type', default='EEG', help='LSL stream type to connect to')
    parser.add_argument('--name', default=None, help='LSL stream name to connect to')
    args = parser.parse_args()
    
    # Build stream query
    stream_query = {'type': args.type}
    if args.name:
        stream_query['name'] = args.name
    
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle('Fusion')
    
    window = SonifyWindow(stream_query)
    window.show()
    
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()

