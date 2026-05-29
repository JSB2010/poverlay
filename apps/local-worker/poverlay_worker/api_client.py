from __future__ import annotations

import json
from typing import Any
from urllib import request


def post_json(url: str, payload: dict[str, Any], *, bearer_token: str | None = None, timeout: float = 30.0) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"

    req = request.Request(url, data=body, headers=headers, method="POST")
    with request.urlopen(req, timeout=timeout) as response:
        data = response.read()
    decoded = json.loads(data.decode("utf-8")) if data else {}
    if not isinstance(decoded, dict):
        raise ValueError(f"Expected object response from {url}")
    return decoded


def patch_json(url: str, payload: dict[str, Any], *, bearer_token: str, timeout: float = 30.0) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {bearer_token}"},
        method="PATCH",
    )
    with request.urlopen(req, timeout=timeout) as response:
        data = response.read()
    decoded = json.loads(data.decode("utf-8")) if data else {}
    if not isinstance(decoded, dict):
        raise ValueError(f"Expected object response from {url}")
    return decoded

