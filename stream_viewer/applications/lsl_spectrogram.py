#  Copyright (C) 2014-2021 Syntrogi Inc dba Intheon. All rights reserved.

"""
Example application for SpectrogramPG renderer.

Usage:
    python lsl_spectrogram.py

Requires an LSL stream with type 'EEG' to be running.
You can use pylsl's SendData example or any EEG device that broadcasts LSL.
"""

import sys
from pathlib import Path
from qtpy import QtWidgets
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from stream_viewer.data import LSLDataSource
from stream_viewer.widgets import SpectrogramControlPanel, ConfigAndRenderWidget
from stream_viewer.renderers import SpectrogramPG


class SpectrogramWindow(QtWidgets.QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("StreamViewer Example - SpectrogramPG")
        
        # Configure the spectrogram renderer
        spectrogram_kwargs = dict(
            bg_color='#202020',
            duration=10.0,
            show_chan_labels=False,
            color_set='viridis',
            font_size=10,
            fmin_hz=1.0,
            fmax_hz=45.0,
            nperseg=256,
            overlap_ratio=0.5,
            max_selected_channels=2,
        )
        
        self._renderer = SpectrogramPG(**spectrogram_kwargs)
        self._renderer.add_source(LSLDataSource({'type': 'EEG'}))
        self._ctrl_panel = SpectrogramControlPanel(self._renderer)
        cw = ConfigAndRenderWidget(self._renderer, self._ctrl_panel, make_hidable=True)
        self.setCentralWidget(cw)
        
        # Resize window
        self.resize(1200, 600)


def main():
    app = QtWidgets.QApplication(sys.argv)
    window = SpectrogramWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()

