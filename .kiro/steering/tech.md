# Technology Stack

## Build System

- **Package Manager**: setuptools with setuptools-scm
- **Modern Alternative**: uv (Python package manager)
- **Python Version**: >=3.8

## Core Dependencies

### GUI Framework
- PyQt5 (5.15.11) with Qt5 (5.15.2)
- qtpy (Qt abstraction layer)
- QML for declarative UI components

### Visualization Libraries
- pyqtgraph: Primary plotting library
- vispy: GPU-accelerated visualization
- visbrain: Brain visualization
- matplotlib (>=3.7.5): Additional plotting

### Data Processing
- numpy: Numerical operations
- pandas: Data structures
- scipy: Scientific computing
- mne (>=1.6.1): Neural data processing

### Streaming
- pylsl (>=1.16.2): Lab Streaming Layer integration

### Graphics
- PyOpenGL: OpenGL bindings for 3D rendering

## Development Tools

- mkdocs with material theme: Documentation
- mkdocstrings: API documentation generation

## Common Commands

### Installation

```bash
# From source
pip install git+https://github.com/intheon/stream_viewer.git

# Using pip with requirements
pip install -r requirements.txt

# Using conda
conda env create -f conda-requirements.yml
conda activate streamviewer

# Using uv (recommended)
uv sync
```

### Running Applications

```bash
# Direct execution
python stream_viewer/applications/main.py
python -m stream_viewer.applications.{application_name}

# With uv
uv run stream_viewer/applications/main.py

# After package installation (entry points)
lsl_viewer
lsl_status
lsl_switching_viewer
lsl_viewer_custom
```

### Documentation

```bash
# Build and serve documentation
mkdocs serve
mkdocs build
```

## Configuration

- Application settings stored in INI format at `~/.stream_viewer/{application_name}.ini`
- Plugin directories configurable for custom renderers and widgets
- Visualization layouts saved as `.vis_config` files
