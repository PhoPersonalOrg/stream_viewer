# Project Structure

## Top-Level Organization

```
stream_viewer/
├── stream_viewer/          # Main package
├── docs/                   # Documentation
├── icons/                  # Application icons
├── dist/                   # Build artifacts
└── .venv/                  # Virtual environment
```

## Package Architecture

The `stream_viewer` package follows a modular architecture with clear separation of concerns:

### Core Modules

- **applications/**: Pre-built applications and entry points
  - `main.py`: Primary LSLViewer GUI application
  - `lsl_*.py`: Various specialized viewer applications
  - `minimal_*.py`: Minimal example applications

- **data/**: Data source abstractions
  - `data_source.py`: Base data source interface
  - `stream_lsl.py`: LSL stream implementation
  - `stream_info.py`: Stream metadata handling

- **buffers/**: Data buffering and stream resolution
  - `stream_data_buffers.py`: Buffer management
  - `resolver.py`: Stream discovery and resolution

- **renderers/**: Visualization renderers (pluggable)
  - `bar_pg.py`: Bar chart renderer (pyqtgraph)
  - `line_pg.py`: Line plot renderer (pyqtgraph)
  - `line_vis.py`: Line visualization (vispy)
  - `topo_*.py`: Topographic visualizations
  - `heatmap_pg.py`: Heatmap renderer
  - `resolver.py`: Renderer discovery and loading
  - `data/`: Renderer-specific data handling
  - `display/`: Display-specific implementations

- **widgets/**: UI control panels and widgets (pluggable)
  - `control_panel.py`: Base control panel
  - `config_renderer.py`: Renderer configuration widget
  - `*_ctrl.py`: Specific control panels for different renderers
  - `interface.py`: Widget interfaces
  - `resolver.py`: Widget discovery and loading

- **qml/**: QML declarative UI components
  - `streamInfoListView.qml`: Stream list view

- **utils/**: Utility functions
  - `headmodel.py`: Head model utilities
  - `resolver.py`: General resolver utilities

## Plugin System

The application supports plugins for renderers and widgets:
- Default search directory: `~/.stream_viewer/plugins/{renderers|widgets}`
- Additional directories configurable via settings
- Plugins discovered dynamically using resolver pattern

## Configuration Files

- `pyproject.toml`: Package metadata, dependencies, and build configuration
- `requirements.txt`: Pip-compatible dependency list
- `conda-requirements.yml`: Conda environment specification
- `mkdocs.yml`: Documentation configuration
- `uv.lock`: Locked dependencies for uv package manager

## Documentation Structure

```
docs/
├── README.md               # Main documentation entry
├── development/            # Development guides
├── modules/                # Module-specific docs
├── outline/                # Documentation outline
└── img/                    # Images and screenshots
```

## Design Patterns

- **Resolver Pattern**: Used for dynamic discovery of renderers, widgets, and data sources
- **Model-View Architecture**: Qt-based MVC for stream status and UI
- **Plugin Architecture**: Extensible renderer and widget system
- **Settings Persistence**: QSettings (INI format) for application state
