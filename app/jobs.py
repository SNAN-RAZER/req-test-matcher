from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Job:
    id: str
    events: list[dict[str, Any]] = field(default_factory=list)
    report: dict[str, Any] | None = None
    error: str | None = None
    done: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock)

    def emit(self, payload: dict[str, Any]) -> None:
        row = {"ts": time.strftime("%H:%M:%S"), **payload}
        with self.lock:
            self.events.append(row)

    def snapshot_from(self, index: int) -> tuple[list[dict[str, Any]], int, bool]:
        with self.lock:
            chunk = self.events[index:]
            return chunk, len(self.events), self.done


JOBS: dict[str, Job] = {}
_JOBS_LOCK = threading.Lock()


def create_job() -> Job:
    job = Job(id=uuid.uuid4().hex[:12])
    with _JOBS_LOCK:
        JOBS[job.id] = job
    return job


def get_job(job_id: str) -> Job | None:
    return JOBS.get(job_id)


def finish_job(job: Job, *, report: dict | None = None, error: str | None = None) -> None:
    job.emit(
        {
            "type": "status",
            "agent": "swarm",
            "action": "failed" if error else "done",
            "detail": error or "run complete",
        }
    )
    with job.lock:
        job.report = report
        job.error = error
        job.done = True
