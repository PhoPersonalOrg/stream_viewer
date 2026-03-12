"""Timeline integration for stream_viewer: render live LSL streams on pyPhoTimeline tracks."""

from stream_viewer.utils.optional_imports import PYPHOTIMELINE_AVAILABLE

if PYPHOTIMELINE_AVAILABLE:
    from stream_viewer.timeline.stream_viewer_lsl_track_datasource import StreamViewerLSLTrackDatasource
    __all__ = ["StreamViewerLSLTrackDatasource"]
else:
    StreamViewerLSLTrackDatasource = None
    __all__ = []
