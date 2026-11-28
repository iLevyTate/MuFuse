"""Voice for the chat (007b): speech in and out on this computer, through sherpa-onnx.

Set before any speech package is imported: no model hub is asked anything, ever. The models come
from `mufuse voice fetch`, pinned and checked (`models.py`).
"""

import os

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
