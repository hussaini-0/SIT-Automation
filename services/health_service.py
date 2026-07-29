"""Fast pre-run reachability checks for configured bank/service URLs."""

from __future__ import annotations

import socket
from dataclasses import dataclass
from urllib.parse import urlparse

from runner import SITRunner
from services.config_service import ROOT_DIR
from services.testcase_service import TestcaseRecord


@dataclass(frozen=True)
class ReachabilityResult:
    bank: str
    service: str
    base_url: str
    reachable: bool
    error: str = ""


def check_records_reachability(
    records: list[TestcaseRecord],
    *,
    timeout_seconds: int = 3,
) -> list[ReachabilityResult]:
    """Check each unique bank/service target once before starting a run."""
    runner = SITRunner(ROOT_DIR)
    targets: dict[tuple[str, str], str] = {}
    results: list[ReachabilityResult] = []

    for record in records:
        key = (record.bank, record.service)
        if key in targets:
            continue
        try:
            targets[key] = runner._get_bank_base_url(record.bank, record.service)
        except Exception as exc:
            results.append(
                ReachabilityResult(
                    bank=record.bank,
                    service=record.service,
                    base_url="",
                    reachable=False,
                    error=str(exc),
                )
            )

    for (bank, service), base_url in sorted(targets.items()):
        parsed = urlparse(base_url)
        host = parsed.hostname
        if not host:
            results.append(
                ReachabilityResult(
                    bank=bank,
                    service=service,
                    base_url=base_url,
                    reachable=False,
                    error="Base URL is missing a host.",
                )
            )
            continue

        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        try:
            with socket.create_connection((host, port), timeout=max(1, timeout_seconds)):
                pass
            results.append(
                ReachabilityResult(
                    bank=bank,
                    service=service,
                    base_url=base_url,
                    reachable=True,
                )
            )
        except OSError as exc:
            results.append(
                ReachabilityResult(
                    bank=bank,
                    service=service,
                    base_url=base_url,
                    reachable=False,
                    error=f"{host}:{port} is not reachable ({exc})",
                )
            )

    return results
