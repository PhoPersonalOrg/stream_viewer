"""Optional dependencies. Use these to guard features that require extra packages (e.g. rerun-sdk).

rerun-sdk is not declared in pyproject.toml so uv lock never requires it (it needs numpy>=2 and
conflicts with dev mne). Install when desired: uv add rerun-sdk. Then use RERUN_AVAILABLE and rr here.
"""

try:
    import rerun as rr
    RERUN_AVAILABLE = True
except ImportError:
    rr = None
    RERUN_AVAILABLE = False
