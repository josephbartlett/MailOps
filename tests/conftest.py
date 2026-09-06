"""Keep every automated test independent of operator mail and credentials."""

from __future__ import annotations

import os
import socket

import pytest


@pytest.fixture(autouse=True)
def isolated_mailops_runtime(tmp_path, monkeypatch):
    for name in tuple(os.environ):
        if name.upper().startswith("MAILOPS_"):
            monkeypatch.delenv(name)
    monkeypatch.setenv("MAILOPS_HOME", str(tmp_path / ".mailops"))

    def deny_network(*args, **kwargs):
        raise OSError("Tests must mock provider/network access; live connections are disabled.")

    monkeypatch.setattr(socket.socket, "connect", deny_network)
    monkeypatch.setattr(socket.socket, "connect_ex", deny_network)
