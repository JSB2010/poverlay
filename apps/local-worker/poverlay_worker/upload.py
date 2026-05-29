from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib import request


def upload_file_to_presigned_url(path: Path, upload_target: dict[str, Any], *, timeout: float = 60.0) -> None:
    upload_url = str(upload_target["upload_url"])
    method = str(upload_target.get("method") or "PUT")
    headers = {str(key): str(value) for key, value in dict(upload_target.get("headers") or {}).items()}
    headers.setdefault("Content-Length", str(path.stat().st_size))
    with path.open("rb") as handle:
        req = request.Request(upload_url, data=handle, headers=headers, method=method)
        with request.urlopen(req, timeout=timeout) as response:
            if response.status < 200 or response.status >= 300:
                raise RuntimeError(f"Upload failed with status {response.status}")
