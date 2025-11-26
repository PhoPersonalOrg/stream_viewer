#  Copyright (C) 2024 Pho Hale. All rights reserved.

"""
Control panel for the SonifyAudio renderer.

Provides a sidebar with controls for audio output settings,
EEG-to-audio mapping configuration, and pitch/synthesis options.
"""

from qtpy import QtWidgets, QtCore
from stream_viewer.widgets.interface import IControlPanel


class SonifyControlPanel(IControlPanel):
    """
    A panel of configuration widgets for configuring the SonifyAudio renderer.
    
    This panel extends the base IControlPanel with audio-specific controls:
    - Audio enable/disable and volume
    - Mapping mode (amplitude, alpha, beta, etc.)
    - Synthesis waveform selection
    - Pitch and polyphony settings
    
    Usage:
        my_renderer = SonifyAudio(...)
        ctrl_panel = SonifyControlPanel(my_renderer)
    """
    
    def __init__(self, renderer, name="SonifyControlPanelWidget", **kwargs):
        super().__init__(renderer, name=name, **kwargs)  # Calls _init_widgets and reset_widgets

    def _init_widgets(self):
        super()._init_widgets()
        
        # Continue filling in the grid of widgets
        row_ix = self._last_row
        
        # =====================================
        # Audio Section Header
        # =====================================
        row_ix += 1
        _header = QtWidgets.QLabel("── Audio ──")
        _header.setStyleSheet("font-weight: bold; color: #00ccff;")
        self.layout().addWidget(_header, row_ix, 0, 1, 2)
        
        # Audio Enabled checkbox
        row_ix += 1
        self.layout().addWidget(QtWidgets.QLabel("Audio Output"), row_ix, 0, 1, 1)
        _checkbox = QtWidgets.QCheckBox()
        _checkbox.setObjectName("AudioEnabled_CheckBox")
        self.layout().addWidget(_checkbox, row_ix, 1, 1, 1)
        
        # Volume slider
        row_ix += 1
        self.layout().addWidget(QtWidgets.QLabel("Volume"), row_ix, 0, 1, 1)
        _volume_widget = QtWidgets.QWidget()
        _volume_layout = QtWidgets.QHBoxLayout(_volume_widget)
        _volume_layout.setContentsMargins(0, 0, 0, 0)
        
        _slider = QtWidgets.QSlider(orientation=QtCore.Qt.Horizontal)
        _slider.setObjectName("Volume_Slider")
        _slider.setMinimum(0)
        _slider.setMaximum(100)
        _slider.setPageStep(5)
        _volume_layout.addWidget(_slider)
        
        _label = QtWidgets.QLabel("0%")
        _label.setObjectName("Volume_Label")
        _label.setMinimumWidth(35)
        _volume_layout.addWidget(_label)
        
        self.layout().addWidget(_volume_widget, row_ix, 1, 1, 1)
        
        # Audio Device ComboBox
        row_ix += 1
        self.layout().addWidget(QtWidgets.QLabel("Output Device"), row_ix, 0, 1, 1)
        _combo = QtWidgets.QComboBox()
        _combo.setObjectName("AudioDevice_ComboBox")
        self.layout().addWidget(_combo, row_ix, 1, 1, 1)
        
        # =====================================
        # Mapping Section Header
        # =====================================
        row_ix += 1
        _header = QtWidgets.QLabel("── Mapping ──")
        _header.setStyleSheet("font-weight: bold; color: #00ccff;")
        self.layout().addWidget(_header, row_ix, 0, 1, 2)
        
        # Mapping Mode ComboBox
        row_ix += 1
        self.layout().addWidget(QtWidgets.QLabel("Mapping Mode"), row_ix, 0, 1, 1)
        _combo = QtWidgets.QComboBox()
        _combo.setObjectName("MappingMode_ComboBox")
        self.layout().addWidget(_combo, row_ix, 1, 1, 1)
        
        # Synth Mode ComboBox
        row_ix += 1
        self.layout().addWidget(QtWidgets.QLabel("Waveform"), row_ix, 0, 1, 1)
        _combo = QtWidgets.QComboBox()
        _combo.setObjectName("SynthMode_ComboBox")
        self.layout().addWidget(_combo, row_ix, 1, 1, 1)
        
        # =====================================
        # Pitch Section Header
        # =====================================
        row_ix += 1
        _header = QtWidgets.QLabel("── Pitch ──")
        _header.setStyleSheet("font-weight: bold; color: #00ccff;")
        self.layout().addWidget(_header, row_ix, 0, 1, 2)
        
        # Base Frequency SpinBox
        row_ix += 1
        self.layout().addWidget(QtWidgets.QLabel("Base Freq"), row_ix, 0, 1, 1)
        _spinbox = QtWidgets.QDoubleSpinBox()
        _spinbox.setObjectName("BaseFreq_SpinBox")
        _spinbox.setMinimum(20.0)
        _spinbox.setMaximum(2000.0)
        _spinbox.setSingleStep(10.0)
        _spinbox.setSuffix(" Hz")
        self.layout().addWidget(_spinbox, row_ix, 1, 1, 1)
        
        # Frequency Range SpinBox
        row_ix += 1
        self.layout().addWidget(QtWidgets.QLabel("Freq Range"), row_ix, 0, 1, 1)
        _spinbox = QtWidgets.QDoubleSpinBox()
        _spinbox.setObjectName("FreqRange_SpinBox")
        _spinbox.setMinimum(0.0)
        _spinbox.setMaximum(4000.0)
        _spinbox.setSingleStep(20.0)
        _spinbox.setSuffix(" Hz")
        self.layout().addWidget(_spinbox, row_ix, 1, 1, 1)
        
        # Polyphonic checkbox
        row_ix += 1
        self.layout().addWidget(QtWidgets.QLabel("Polyphonic"), row_ix, 0, 1, 1)
        _checkbox = QtWidgets.QCheckBox()
        _checkbox.setObjectName("Polyphonic_CheckBox")
        _checkbox.setToolTip("One tone per channel")
        self.layout().addWidget(_checkbox, row_ix, 1, 1, 1)
        
        # Pitch per channel checkbox
        row_ix += 1
        self.layout().addWidget(QtWidgets.QLabel("Spread Pitch"), row_ix, 0, 1, 1)
        _checkbox = QtWidgets.QCheckBox()
        _checkbox.setObjectName("PitchPerChannel_CheckBox")
        _checkbox.setToolTip("Spread channels across pitch range")
        self.layout().addWidget(_checkbox, row_ix, 1, 1, 1)
        
        # Note quantize checkbox
        row_ix += 1
        self.layout().addWidget(QtWidgets.QLabel("Quantize Notes"), row_ix, 0, 1, 1)
        _checkbox = QtWidgets.QCheckBox()
        _checkbox.setObjectName("NoteQuantize_CheckBox")
        _checkbox.setToolTip("Quantize pitches to musical notes")
        self.layout().addWidget(_checkbox, row_ix, 1, 1, 1)
        
        # =====================================
        # Data Section Header
        # =====================================
        row_ix += 1
        _header = QtWidgets.QLabel("── Data ──")
        _header.setStyleSheet("font-weight: bold; color: #00ccff;")
        self.layout().addWidget(_header, row_ix, 0, 1, 2)
        
        # Duration SpinBox
        row_ix += 1
        self.layout().addWidget(QtWidgets.QLabel("Buffer Duration"), row_ix, 0, 1, 1)
        _spinbox = QtWidgets.QDoubleSpinBox()
        _spinbox.setObjectName("Duration_SpinBox")
        _spinbox.setMinimum(0.1)
        _spinbox.setMaximum(30.0)
        _spinbox.setSingleStep(0.5)
        _spinbox.setSuffix(" s")
        self.layout().addWidget(_spinbox, row_ix, 1, 1, 1)
        
        # AutoScale ComboBox
        row_ix += 1
        self.layout().addWidget(QtWidgets.QLabel("AutoScale"), row_ix, 0, 1, 1)
        _combo = QtWidgets.QComboBox()
        _combo.setObjectName("AutoScale_ComboBox")
        self.layout().addWidget(_combo, row_ix, 1, 1, 1)
        
        self._last_row = row_ix

    def reset_widgets(self, renderer):
        super().reset_widgets(renderer)
        
        # =====================================
        # Audio Section
        # =====================================
        
        # Audio Enabled checkbox
        _checkbox = self.findChild(QtWidgets.QCheckBox, name="AudioEnabled_CheckBox")
        try:
            _checkbox.stateChanged.disconnect()
        except TypeError:
            pass
        _checkbox.setChecked(renderer.audio_enabled)
        _checkbox.stateChanged.connect(renderer.audio_enabled_stateChanged)
        
        # Volume slider
        _slider = self.findChild(QtWidgets.QSlider, name="Volume_Slider")
        _label = self.findChild(QtWidgets.QLabel, name="Volume_Label")
        try:
            _slider.valueChanged.disconnect()
        except TypeError:
            pass
        volume_pct = int(renderer.volume * 100)
        _slider.setValue(volume_pct)
        _label.setText(f"{volume_pct}%")
        
        def on_volume_changed(value):
            renderer.volume = value / 100.0
            _label.setText(f"{value}%")
        _slider.valueChanged.connect(on_volume_changed)
        
        # Audio Device ComboBox
        _combo = self.findChild(QtWidgets.QComboBox, name="AudioDevice_ComboBox")
        try:
            _combo.currentIndexChanged.disconnect()
        except TypeError:
            pass
        _combo.clear()
        _combo.addItem("Default", -1)
        
        # Populate audio devices
        from stream_viewer.renderers.display.audio import AudioRenderer
        devices = AudioRenderer.list_audio_devices()
        for idx, name, channels in devices:
            display_name = name[:35] + "..." if len(name) > 35 else name
            _combo.addItem(f"[{idx}] {display_name}", idx)
        
        # Select current device
        current_device = renderer.audio_device
        if current_device is None:
            _combo.setCurrentIndex(0)
        else:
            for i in range(_combo.count()):
                if _combo.itemData(i) == current_device:
                    _combo.setCurrentIndex(i)
                    break
        
        def on_device_changed(index):
            device_idx = _combo.itemData(index)
            renderer.audio_device = device_idx if device_idx >= 0 else None
        _combo.currentIndexChanged.connect(on_device_changed)
        
        # =====================================
        # Mapping Section
        # =====================================
        
        # Mapping Mode ComboBox
        _combo = self.findChild(QtWidgets.QComboBox, name="MappingMode_ComboBox")
        try:
            _combo.currentTextChanged.disconnect()
        except TypeError:
            pass
        _combo.clear()
        if hasattr(renderer, 'MAPPING_MODES'):
            _combo.addItems(renderer.MAPPING_MODES)
        _combo.setCurrentText(renderer.mapping_mode)
        _combo.currentTextChanged.connect(renderer.mapping_mode_currentTextChanged)
        
        # Synth Mode ComboBox
        _combo = self.findChild(QtWidgets.QComboBox, name="SynthMode_ComboBox")
        try:
            _combo.currentTextChanged.disconnect()
        except TypeError:
            pass
        _combo.clear()
        if hasattr(renderer, 'SYNTH_MODES'):
            _combo.addItems(renderer.SYNTH_MODES)
        _combo.setCurrentText(renderer.synth_mode)
        _combo.currentTextChanged.connect(renderer.synth_mode_currentTextChanged)
        
        # =====================================
        # Pitch Section
        # =====================================
        
        # Base Frequency SpinBox
        _spinbox = self.findChild(QtWidgets.QDoubleSpinBox, name="BaseFreq_SpinBox")
        try:
            _spinbox.valueChanged.disconnect()
        except TypeError:
            pass
        _spinbox.setValue(renderer.base_freq)
        _spinbox.valueChanged.connect(renderer.base_freq_valueChanged)
        
        # Frequency Range SpinBox
        _spinbox = self.findChild(QtWidgets.QDoubleSpinBox, name="FreqRange_SpinBox")
        try:
            _spinbox.valueChanged.disconnect()
        except TypeError:
            pass
        _spinbox.setValue(renderer.freq_range)
        _spinbox.valueChanged.connect(renderer.freq_range_valueChanged)
        
        # Polyphonic checkbox
        _checkbox = self.findChild(QtWidgets.QCheckBox, name="Polyphonic_CheckBox")
        try:
            _checkbox.stateChanged.disconnect()
        except TypeError:
            pass
        _checkbox.setChecked(renderer.polyphonic)
        _checkbox.stateChanged.connect(renderer.polyphonic_stateChanged)
        
        # Pitch per channel checkbox
        _checkbox = self.findChild(QtWidgets.QCheckBox, name="PitchPerChannel_CheckBox")
        try:
            _checkbox.stateChanged.disconnect()
        except TypeError:
            pass
        _checkbox.setChecked(renderer.pitch_per_channel)
        _checkbox.stateChanged.connect(renderer.pitch_per_channel_stateChanged)
        
        # Note quantize checkbox
        _checkbox = self.findChild(QtWidgets.QCheckBox, name="NoteQuantize_CheckBox")
        try:
            _checkbox.stateChanged.disconnect()
        except TypeError:
            pass
        _checkbox.setChecked(renderer.note_quantize)
        _checkbox.stateChanged.connect(renderer.note_quantize_stateChanged)
        
        # =====================================
        # Data Section
        # =====================================
        
        # Duration SpinBox
        _spinbox = self.findChild(QtWidgets.QDoubleSpinBox, name="Duration_SpinBox")
        try:
            _spinbox.valueChanged.disconnect()
        except TypeError:
            pass
        _spinbox.setValue(renderer.duration)
        _spinbox.valueChanged.connect(renderer.duration_valueChanged)
        
        # AutoScale ComboBox
        _combo = self.findChild(QtWidgets.QComboBox, name="AutoScale_ComboBox")
        try:
            _combo.currentTextChanged.disconnect()
        except TypeError:
            pass
        _combo.clear()
        _combo.addItems(renderer.autoscale_modes)
        _combo.setCurrentText(renderer.auto_scale)
        _combo.currentTextChanged.connect(renderer.auto_scale_currentTextChanged)

