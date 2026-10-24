# SPDX-FileCopyrightText: 2026 O-Form Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""HTTP client for ``shilpi-http`` (same gateway O-Draft / AORMS use).

Defaults match O-Draft take-off: ``shilpid`` on ``127.0.0.1:7420``, gateway on
``127.0.0.1:7421``. Spawns local binaries from ``%LocalAppData%\\ShilpiDB\\bin``
when nothing answers — same pattern as O-Draft ``ensure_server``.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Optional

DEFAULT_SHILPID = "127.0.0.1:7420"
DEFAULT_GATEWAY = "127.0.0.1:7421"
DEFAULT_TIMEOUT = 8.0

# Suite data dir — sibling to O-Draft takeoff/library.
_OSAS_OFORM = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
    "OSAS",
    "oform",
)
DEFAULT_DATA = os.path.join(_OSAS_OFORM, "bim.vdb")


def _bin_dirs():
    env = os.environ.get("SHILPIDB_BIN", "").strip()
    if env:
        yield env
    yield os.path.join(os.environ.get("LOCALAPPDATA", ""), "ShilpiDB", "bin")
    yield os.path.join(os.environ.get("LOCALAPPDATA", ""), "OSAS", "ShilpiDB", "bin")


def find_program(name: str) -> Optional[str]:
    exe = name if name.lower().endswith(".exe") else name + ".exe"
    for folder in _bin_dirs():
        if not folder:
            continue
        path = os.path.join(folder, exe)
        if os.path.isfile(path):
            return path
    # PATH
    for folder in os.environ.get("PATH", "").split(os.pathsep):
        path = os.path.join(folder, exe)
        if os.path.isfile(path):
            return path
    return None


def _tcp_open(addr: str, timeout: float = 0.4) -> bool:
    host, _, port_s = addr.partition(":")
    try:
        port = int(port_s or "7420")
    except ValueError:
        return False
    try:
        with socket.create_connection((host or "127.0.0.1", port), timeout=timeout):
            return True
    except OSError:
        return False


def ensure_server(
    addr: str = DEFAULT_SHILPID,
    gateway: str = DEFAULT_GATEWAY,
    data_path: str = DEFAULT_DATA,
) -> tuple[bool, str]:
    """Ensure ``shilpid`` (+ HTTP gateway) answer. Starts them if needed."""
    os.makedirs(os.path.dirname(data_path) or ".", exist_ok=True)
    if _tcp_open(addr):
        # Prefer existing shared suite server (O-Draft may already own 7420).
        if not _http_ok(gateway):
            _spawn_http(gateway, addr)
            time.sleep(0.35)
        return True, "connected " + addr

    shilpid = find_program("shilpid")
    if shilpid is None:
        return False, "shilpid not found (install ShilpiDB or set SHILPIDB_BIN)"

    try:
        creation = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.Popen(
            [shilpid, "--bind", addr, "--data", data_path, "--autosave-secs", "5"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creation,
        )
    except OSError as exc:
        return False, "failed to start shilpid: " + str(exc)

    for _ in range(20):
        time.sleep(0.15)
        if _tcp_open(addr):
            break
    else:
        return False, "shilpid did not open " + addr

    _spawn_http(gateway, addr)
    time.sleep(0.35)
    if not _http_ok(gateway):
        return False, "shilpi-http not reachable on " + gateway
    return True, "started " + addr + " → " + data_path


def _spawn_http(gateway: str, backend: str) -> None:
    if _http_ok(gateway):
        return
    http = find_program("shilpi-http")
    if http is None:
        return
    try:
        creation = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.Popen(
            [http, "--bind", gateway, "--backend", backend],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creation,
        )
    except OSError:
        pass


def _http_ok(gateway: str, timeout: float = 0.6) -> bool:
    try:
        url = "http://{}/health".format(gateway)
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


@dataclass
class Record:
    id: int
    min_x: float
    min_y: float
    max_x: float
    max_y: float
    payload: bytes


class ShilpiHttp:
    """Thin REST client for ``shilpi-http``."""

    def __init__(self, gateway: str = DEFAULT_GATEWAY, timeout: float = DEFAULT_TIMEOUT):
        self.gateway = gateway.strip() or DEFAULT_GATEWAY
        self.timeout = timeout

    def _url(self, path: str, query: Optional[dict] = None) -> str:
        base = "http://{}{}".format(self.gateway, path)
        if not query:
            return base
        return base + "?" + urllib.parse.urlencode(query)

    def _json(self, req: urllib.request.Request):
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}

    def health(self) -> bool:
        return _http_ok(self.gateway, timeout=self.timeout)

    def stats(self) -> dict:
        req = urllib.request.Request(self._url("/stats"), method="GET")
        return self._json(req)

    def put_record(self, record: Record) -> None:
        query = {
            "minX": record.min_x,
            "minY": record.min_y,
            "maxX": record.max_x,
            "maxY": record.max_y,
        }
        req = urllib.request.Request(
            self._url("/records/{}".format(record.id), query),
            data=record.payload,
            method="PUT",
            headers={"Content-Type": "application/octet-stream"},
        )
        self._json(req)

    def get_record(self, record_id: int) -> Optional[Record]:
        try:
            req = urllib.request.Request(
                self._url("/records/{}".format(record_id)), method="GET"
            )
            data = self._json(req)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            raise
        bbox = data.get("bbox") or {}
        payload = b""
        if data.get("payloadText") is not None:
            payload = str(data["payloadText"]).encode("utf-8")
        elif data.get("payloadHex"):
            payload = bytes.fromhex(data["payloadHex"])
        return Record(
            id=int(data["id"]),
            min_x=float(bbox.get("minX", 0)),
            min_y=float(bbox.get("minY", 0)),
            max_x=float(bbox.get("maxX", 0)),
            max_y=float(bbox.get("maxY", 0)),
            payload=payload,
        )

    def delete_record(self, record_id: int) -> bool:
        req = urllib.request.Request(
            self._url("/records/{}".format(record_id)), method="DELETE"
        )
        data = self._json(req)
        return bool(data.get("deleted"))

    def list_boxes(self) -> list:
        req = urllib.request.Request(self._url("/records"), method="GET")
        data = self._json(req)
        return data.get("records") or []

    def save(self) -> None:
        req = urllib.request.Request(
            self._url("/save"), data=b"", method="POST"
        )
        self._json(req)
