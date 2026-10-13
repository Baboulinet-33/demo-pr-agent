"""Minimal in-process scheduler for recurring report exports.

The scheduler runs a daemon worker thread that ticks every few hundred
milliseconds and invokes every job whose wall-clock deadline has passed.
It is intentionally dependency-free and simple enough to unit test.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Dict, List, Optional, Tuple


class Scheduler:
    """Runs registered callables on fixed wall-clock intervals."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: Dict[int, dict] = {}
        self._next_id = 1
        self._thread: Optional[threading.Thread] = None
        self._started = False

    def add(self, interval_seconds: int, fn: Callable[[], None]) -> int:
        """Register ``fn`` to run every ``interval_seconds`` seconds."""
        with self._lock:
            job_id = self._next_id
            self._next_id += 1
            now = time.time()
            due = now + (interval_seconds - (now % interval_seconds))
            self._jobs[job_id] = {
                "fn": fn,
                "interval": interval_seconds,
                "next_run": due,
            }
            return job_id

    def due_jobs(self) -> List[Tuple[int, dict]]:
        """Snapshot of jobs whose deadline has passed; safe for tests."""
        now = time.time()
        with self._lock:
            return [(jid, job) for jid, job in self._jobs.items() if job["next_run"] <= now]

    def tick(self) -> None:
        """Run every due job exactly once, rescheduling it afterwards."""
        for job_id, job in self.due_jobs():
            try:
                job["fn"]()
            except Exception:  # noqa: BLE001 - a failing job must not kill the thread
                continue
            with self._lock:
                now = time.time()
                job["next_run"] = max(now, job["next_run"]) + job["interval"]

    def start(self) -> None:
        """Start the background worker thread if it is not running yet."""
        if self._started:
            return
        self._thread = threading.Thread(
            target=self._worker, name="report-scheduler", daemon=True
        )
        self._thread.start()
        self._started = True

    def stop(self) -> None:
        """Stop the worker thread and clear pending jobs."""
        with self._lock:
            self._jobs = {}
            self._thread = None
            self._started = False

    def _worker(self) -> None:
        while True:
            self.tick()
            time.sleep(0.4)