from __future__ import annotations

import time
from typing import ClassVar

class SystemMetrics:
    """In-memory telemetry collector producing standard Prometheus plaintext format."""
    
    # Simple counters and timers
    http_requests_total: ClassVar[dict[str, int]] = {}
    agent_runs_total: ClassVar[dict[str, int]] = {}
    latency_sum: ClassVar[dict[str, float]] = {}
    latency_count: ClassVar[dict[str, int]] = {}

    @classmethod
    def record_request(cls, method: str, path: str, status_code: int) -> None:
        key = f'method="{method}",path="{path}",status="{status_code}"'
        cls.http_requests_total[key] = cls.http_requests_total.get(key, 0) + 1

    @classmethod
    def record_run(cls, status: str) -> None:
        cls.agent_runs_total[status] = cls.agent_runs_total.get(status, 0) + 1

    @classmethod
    def record_latency(cls, endpoint: str, duration_sec: float) -> None:
        cls.latency_sum[endpoint] = cls.latency_sum.get(endpoint, 0.0) + duration_sec
        cls.latency_count[endpoint] = cls.latency_count.get(endpoint, 0) + 1

    @classmethod
    def generate_prometheus_output(cls) -> str:
        lines = []
        
        # 1. HTTP Requests Metric
        lines.append("# HELP http_requests_total Total number of HTTP requests processed")
        lines.append("# TYPE http_requests_total counter")
        for labels, val in cls.http_requests_total.items():
            lines.append(f"http_requests_total{{{labels}}} {val}")
            
        # 2. Agent Runs Metric
        lines.append("# HELP agent_runs_total Total number of agent runs triggered")
        lines.append("# TYPE agent_runs_total counter")
        for status_lbl, val in cls.agent_runs_total.items():
            lines.append(f'agent_runs_total{{status="{status_lbl}"}} {val}')
            
        # 3. HTTP Request Latency Metric
        lines.append("# HELP http_request_duration_seconds Latency duration of HTTP requests in seconds")
        lines.append("# TYPE http_request_duration_seconds summary")
        for endpoint, val_sum in cls.latency_sum.items():
            val_count = cls.latency_count.get(endpoint, 0)
            lines.append(f'http_request_duration_seconds_sum{{endpoint="{endpoint}"}} {val_sum:.4f}')
            lines.append(f'http_request_duration_seconds_count{{endpoint="{endpoint}"}} {val_count}')
            
        return "\n".join(lines) + "\n"
