import os
import sys
from src.app import main
import re


def run_with_log_filter():
    error_patterns = [
        re.compile(r"MESA-LOADER: failed to open i965"),
        re.compile(r"failed to load driver: i965"),
        re.compile(r"Buffer handle is null"),
        re.compile(r"Creation of StagingBuffer's SharedImage failed"),
        re.compile(r"shared_image_interface_proxy.cc"),
        re.compile(r"one_copy_raster_buffer_provider.cc"),
    ]

    class LogFilter:
        def __init__(self, stream):
            self.stream = stream

        def write(self, data):
            modified = data
            for pattern in error_patterns:
                if pattern.search(data):
                    modified = data
                    modified = modified.replace("ERROR", "WARNING (safe to ignore)")
                    modified = modified.replace("failed", "note: failed")
                    break
            self.stream.write(modified)

        def flush(self):
            self.stream.flush()

    sys.stdout = LogFilter(sys.stdout)
    sys.stderr = LogFilter(sys.stderr)

    # Mesa/Qt sane defaults
    os.environ.setdefault("MESA_LOADER_DRIVER_OVERRIDE", "iris")

    # QtWebEngine prefers ANGLE on some Intel setups
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--use-gl=angle")

    # Warn if not in the right conda env
    conda_env = os.environ.get("CONDA_DEFAULT_ENV")
    if conda_env != "monaco-viewer-env":
        print(
            f"WARNING: Not running inside 'monaco-viewer-env' (current: {conda_env}).\n"
            "Please run: conda activate monaco-viewer-env before launching."
        )

    main()


if __name__ == "__main__":
    run_with_log_filter()

