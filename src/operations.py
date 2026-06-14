import json
import logging
import threading
from collections import defaultdict
from dataclasses import dataclass


@dataclass(slots=True)
class RequestMetric:
    count: int = 0
    duration_seconds: float = 0.0


class RuntimeMetrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._requests: dict[tuple[str, str, int], RequestMetric] = defaultdict(
            RequestMetric
        )

    def record(
        self,
        *,
        method: str,
        route: str,
        status_code: int,
        duration_seconds: float,
    ) -> None:
        key = (method, route, status_code)
        with self._lock:
            metric = self._requests[key]
            metric.count += 1
            metric.duration_seconds += duration_seconds

    def render_prometheus(self) -> str:
        lines = [
            "# HELP compliance_http_requests_total HTTP requests processed.",
            "# TYPE compliance_http_requests_total counter",
        ]
        with self._lock:
            items = sorted(self._requests.items())
            for (method, route, status_code), metric in items:
                labels = (
                    f'method="{_escape(method)}",'
                    f'route="{_escape(route)}",'
                    f'status="{status_code}"'
                )
                lines.append(
                    f"compliance_http_requests_total{{{labels}}} {metric.count}"
                )
            lines.extend(
                [
                    "# HELP compliance_http_request_duration_seconds_total "
                    "Cumulative HTTP request duration.",
                    "# TYPE compliance_http_request_duration_seconds_total counter",
                ]
            )
            for (method, route, status_code), metric in items:
                labels = (
                    f'method="{_escape(method)}",'
                    f'route="{_escape(route)}",'
                    f'status="{status_code}"'
                )
                lines.append(
                    "compliance_http_request_duration_seconds_total"
                    f"{{{labels}}} {metric.duration_seconds:.6f}"
                )
        return "\n".join(lines) + "\n"


def log_access(
    logger: logging.Logger,
    *,
    request_id: str,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
) -> None:
    logger.info(
        json.dumps(
            {
                "event": "http_request",
                "request_id": request_id,
                "method": method,
                "path": path,
                "status_code": status_code,
                "duration_ms": round(duration_ms, 3),
            },
            sort_keys=True,
        )
    )


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
