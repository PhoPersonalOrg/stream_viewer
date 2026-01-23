# Building Self-Contained Executables

This project supports building self-contained executables using PyInstaller.

## Prerequisites

1. Install development dependencies:
   ```bash
   uv sync --all-extras --group dev
   ```

2. Ensure all runtime dependencies are installed and working.

## Building the Executable

### Option 1: Using the Build Script (Recommended)

```bash
python build_exe.py
```

This will:
- Clean previous builds
- Build the executable using the spec file
- Output the executable to `dist/lsl_viewer` (or `dist/lsl_viewer.exe` on Windows)

### Option 2: Using PyInstaller Directly

```bash
pyinstaller --clean lsl_viewer.spec
```

Or for a one-file executable:

```bash
pyinstaller --onefile --clean lsl_viewer.spec
```

## Output

The built executable will be located in the `dist/` directory:
- **Linux/macOS**: `dist/lsl_viewer`
- **Windows**: `dist/lsl_viewer.exe`

## Troubleshooting

### Missing Modules

If you encounter "ModuleNotFoundError" at runtime, you may need to add the missing module to the `hiddenimports` list in `lsl_viewer.spec`.

### QML Files Not Found

If QML files are not loading correctly, ensure they are included in the `datas` section of the spec file. The current spec includes:
- `stream_viewer/qml/streamInfoListView.qml`

### Large Executable Size

The executable may be large (100+ MB) due to:
- PyQt5 libraries
- NumPy, SciPy, and other scientific libraries
- MNE-Python and related dependencies

This is normal for applications with many dependencies.

### Console Window on Windows

The spec file is configured with `console=False` to hide the console window. If you need to see debug output, change it to `console=True` in `lsl_viewer.spec`.

## Customization

Edit `lsl_viewer.spec` to:
- Add additional data files
- Include/exclude specific modules
- Change executable name or icon
- Adjust build options

## Notes

- The first run of the executable may be slower as it extracts files to a temporary directory
- On Windows, antivirus software may flag PyInstaller executables; this is a known false positive
- The executable is platform-specific; build on the target platform
