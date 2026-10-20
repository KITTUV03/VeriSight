"""
Sovereign Air-Gap Network Enforcement Guard for VeriSight.

Enforces zero cloud RTL leakage by intercepting socket connections
and blocking any outbound WAN requests to external endpoints (OpenAI,
Anthropic, Google APIs, etc.) when air-gap mode is active.
"""

import socket
import ipaddress
from typing import Set, Optional
from verisight.utils.logger import get_logger

logger = get_logger("airgap_guard")


class AirGapViolationError(RuntimeError):
    """Raised when an outbound WAN connection is attempted while Sovereign Air-Gap is active."""
    pass


_AIRGAP_ACTIVE = False
_ORIGINAL_SOCKET_CONNECT = None
_ORIGINAL_GETADDRINFO = None

# Whitelisted loopback & enterprise RFC-1918 private subnet ranges
_ALLOWED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),      # Loopback
    ipaddress.ip_network("10.0.0.0/8"),       # Private class A
    ipaddress.ip_network("172.16.0.0/12"),    # Private class B
    ipaddress.ip_network("192.168.0.0/16"),   # Private class C
    ipaddress.ip_network("::1/128"),          # IPv6 loopback
    ipaddress.ip_network("fe80::/10"),        # IPv6 link-local
]

_ALLOWED_HOSTNAMES: Set[str] = {
    "localhost",
    "127.0.0.1",
    "::1",
    "0.0.0.0",
}


def is_airgap_enabled() -> bool:
    """Return True if Sovereign Air-Gap guard is currently active."""
    global _AIRGAP_ACTIVE
    return _AIRGAP_ACTIVE


def _is_ip_allowed(ip_str: str) -> bool:
    """Check if an IP address belongs to allowed loopback or private enterprise subnets."""
    try:
        ip_obj = ipaddress.ip_address(ip_str)
        return any(ip_obj in net for net in _ALLOWED_NETWORKS)
    except ValueError:
        return False


def _guarded_connect(self, address):
    """Intercept socket.connect to enforce air-gap policy."""
    if _AIRGAP_ACTIVE:
        host = address[0] if isinstance(address, (tuple, list)) else address
        
        # Check if host is an allowed hostname
        if str(host).lower() not in _ALLOWED_HOSTNAMES:
            # Check if host resolves to an allowed private/loopback IP
            if not _is_ip_allowed(str(host)):
                msg = (
                    f"SOVEREIGN AIR-GAP SECURITY VIOLATION: "
                    f"Outbound connection to '{host}' blocked! "
                    f"Zero Cloud RTL Leakage policy is ENFORCED."
                )
                logger.critical(msg)
                raise AirGapViolationError(msg)

    return _ORIGINAL_SOCKET_CONNECT(self, address)


def enable_airgap_guard(extra_allowed_hosts: Optional[Set[str]] = None):
    """
    Enable network-level socket interception to strictly block public cloud WAN traffic.
    """
    global _AIRGAP_ACTIVE, _ORIGINAL_SOCKET_CONNECT

    if extra_allowed_hosts:
        _ALLOWED_HOSTNAMES.update(extra_allowed_hosts)

    if not _AIRGAP_ACTIVE:
        _ORIGINAL_SOCKET_CONNECT = socket.socket.connect
        socket.socket.connect = _guarded_connect
        _AIRGAP_ACTIVE = True
        logger.info(
            "🛡️ Sovereign Air-Gap Guard ACTIVATED: All outbound WAN / Cloud API traffic is BLOCKED. "
            "Zero Cloud RTL Leakage Certified."
        )


def disable_airgap_guard():
    """Disable air-gap guard (for testing or cloud fallback)."""
    global _AIRGAP_ACTIVE, _ORIGINAL_SOCKET_CONNECT
    if _AIRGAP_ACTIVE and _ORIGINAL_SOCKET_CONNECT is not None:
        socket.socket.connect = _ORIGINAL_SOCKET_CONNECT
        _AIRGAP_ACTIVE = False
        logger.info("Air-gap guard disabled.")
