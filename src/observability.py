import logging
import time
import uuid
from contextlib import contextmanager
from functools import wraps
from typing import Optional, Callable, Any
from datetime import datetime, timezone

from src.config import config

class StructuredLogger:
    def __init__(self, name: str, correlation_id: Optional[str] = None):
        self.logger = logging.getLogger(name)
        self.correlation_id = correlation_id or str(uuid.uuid4())[:8]
        self._set_level()

    def _set_level(self):
        level = getattr(logging, config.observability.log_level)
        self.logger.setLevel(level)
        for handler in self.logger.handlers:
            handler.setLevel(level)

    def _format(self, msg: str, **kwargs) -> str:
        parts = [f"[{self.correlation_id}]", msg]
        for k, v in kwargs.items():
            parts.append(f"{k}={v}")
        return " ".join(parts)

    def debug(self, msg: str, **kwargs):
        self.logger.debug(self._format(msg, **kwargs))

    def info(self, msg: str, **kwargs):
        self.logger.info(self._format(msg, **kwargs))

    def warning(self, msg: str, **kwargs):
        self.logger.warning(self._format(msg, **kwargs))

    def error(self, msg: str, **kwargs):
        self.logger.error(self._format(msg, **kwargs))


class ProgressTracker:
    def __init__(self, correlation_id: str, total_steps: int = 5):
        self.correlation_id = correlation_id
        self.total_steps = total_steps
        self.current_step = 0
        self.started_at = datetime.now(timezone.utc)
        self.step_times: list[tuple[str, float]] = []

    def update(self, step: str, node_name: str):
        if not config.observability.trace_nodes:
            return
        elapsed = (datetime.now(timezone.utc) - self.started_at).total_seconds()
        self.step_times.append((node_name, elapsed))
        self.current_step += 1
        progress_pct = min(100, int((self.current_step / self.total_steps) * 100))
        logging.getLogger("progress").info(
            f"[{self.correlation_id}] {step} ({node_name}) - {progress_pct}% complete"
        )

    def summary(self) -> dict:
        if not self.step_times:
            return {}
        return {
            "correlation_id": self.correlation_id,
            "total_duration_s": round(self.step_times[-1][1], 2) if self.step_times else 0,
            "node_count": len(self.step_times),
        }


class TokenMonitor:
    def __init__(self):
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.agent_costs: dict[str, dict[str, int]] = {}

    def record(self, agent_name: str, input_tokens: int, output_tokens: int):
        if not config.observability.track_tokens:
            return
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        if agent_name not in self.agent_costs:
            self.agent_costs[agent_name] = {"input": 0, "output": 0, "calls": 0}
        self.agent_costs[agent_name]["input"] += input_tokens
        self.agent_costs[agent_name]["output"] += output_tokens
        self.agent_costs[agent_name]["calls"] += 1
        logging.getLogger("tokens").debug(
            f"[{agent_name}] input={input_tokens} output={output_tokens}"
        )

    def summary(self) -> dict:
        return {
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "by_agent": dict(self.agent_costs),
        }


_global_token_monitor = TokenMonitor()


def get_token_monitor() -> TokenMonitor:
    return _global_token_monitor


@contextmanager
def track_node_execution(node_name: str, correlation_id: str):
    start = time.perf_counter()
    logger = logging.getLogger("nodes")
    logger.debug(f"[{correlation_id}] → {node_name} started")
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        logger.info(f"[{correlation_id}] ← {node_name} completed in {elapsed:.2f}s")


def with_token_tracking(agent_name: str):
    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            monitor = get_token_monitor()
            start_tokens = monitor.total_input_tokens + monitor.total_output_tokens
            result = fn(*args, **kwargs)
            end_tokens = monitor.total_input_tokens + monitor.total_output_tokens
            if end_tokens > start_tokens:
                tokens_delta = end_tokens - start_tokens
                monitor.record(agent_name, tokens_delta // 2, tokens_delta // 2)
            return result
        return wrapper
    return decorator