"""Network topology helpers for Proton Bridge."""

from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import os
from pathlib import Path
import socket
from typing import Mapping

LOCALHOST_HOSTS = {"127.0.0.1", "localhost", "::1"}


@dataclass(frozen=True)
class TcpProbeResult:
    host: str
    port: int
    reachable: bool
    error: str | None = None


def is_wsl_environment(
    *,
    env: Mapping[str, str] | None = None,
    version_path: Path = Path("/proc/version"),
) -> bool:
    """Return true when MailOps appears to be running inside WSL."""

    environment = os.environ if env is None else env
    if environment.get("WSL_DISTRO_NAME") or environment.get("WSL_INTEROP"):
        return True
    try:
        version = version_path.read_text(encoding="utf-8", errors="ignore").lower()
    except OSError:
        return False
    return "microsoft" in version or "wsl" in version


def bridge_host_candidates(
    primary_host: str,
    *,
    env: Mapping[str, str] | None = None,
    version_path: Path = Path("/proc/version"),
    resolv_conf_path: Path = Path("/etc/resolv.conf"),
    route_path: Path = Path("/proc/net/route"),
) -> list[str]:
    """Return host candidates for reaching Bridge from the current network namespace."""

    candidates = [_normalize_host(primary_host)]
    if not _is_localhost(primary_host) or not is_wsl_environment(env=env, version_path=version_path):
        return candidates

    for host in (
        windows_host_from_resolv_conf(resolv_conf_path),
        windows_host_from_default_route(route_path),
    ):
        if host and host not in candidates and not _is_localhost(host):
            candidates.append(host)
    return candidates


def windows_host_from_resolv_conf(path: Path = Path("/etc/resolv.conf")) -> str | None:
    """Extract the WSL Windows host candidate from resolv.conf nameserver entries."""

    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return None
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("nameserver "):
            continue
        candidate = stripped.split(maxsplit=1)[1].strip()
        if _is_ipv4(candidate):
            return candidate
    return None


def windows_host_from_default_route(path: Path = Path("/proc/net/route")) -> str | None:
    """Extract the default gateway from Linux route metadata."""

    try:
        rows = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return None
    for row in rows[1:]:
        columns = row.split()
        if len(columns) < 3 or columns[1] != "00000000":
            continue
        gateway_hex = columns[2]
        try:
            gateway_bytes = bytes.fromhex(gateway_hex)
        except ValueError:
            continue
        if len(gateway_bytes) != 4:
            continue
        candidate = socket.inet_ntoa(gateway_bytes[::-1])
        if _is_ipv4(candidate):
            return candidate
    return None


def probe_tcp_endpoint(host: str, port: int, *, timeout: float = 0.35) -> TcpProbeResult:
    """Check whether a TCP endpoint is reachable without sending credentials."""

    try:
        with socket.create_connection((host, port), timeout=timeout):
            return TcpProbeResult(host=host, port=port, reachable=True)
    except OSError as exc:
        return TcpProbeResult(host=host, port=port, reachable=False, error=str(exc))


def _normalize_host(host: str) -> str:
    return host.strip() or "127.0.0.1"


def _is_localhost(host: str) -> bool:
    normalized = _normalize_host(host).lower()
    if normalized in LOCALHOST_HOSTS:
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def _is_ipv4(value: str) -> bool:
    try:
        return isinstance(ipaddress.ip_address(value), ipaddress.IPv4Address)
    except ValueError:
        return False
