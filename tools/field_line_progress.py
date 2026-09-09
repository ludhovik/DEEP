"""Rate-limited terminal progress for the converters' serial line tracers."""
from __future__ import annotations

import time


class TraceProgress:
    def __init__(self, label, total, max_steps, *, item="seeds", interval=5.0):
        self.label, self.total, self.max_steps = label, int(total), int(max_steps)
        self.item, self.interval = item, float(interval)
        self.started = self.last_report = time.monotonic()
        self.index = 0
        print(f"{label}: 0/{self.total} {item} completed; "
              f"up to {self.max_steps} steps per branch.", flush=True)

    def begin(self, index):
        self.index = int(index)
        self.tick("starting")

    def tick(self, detail):
        now = time.monotonic()
        if now - self.last_report < self.interval:
            return
        self.last_report = now
        print(f"  {self.label}: {self.index}/{self.total} {self.item} completed; "
              f"item {self.index + 1}, {detail}; elapsed {now-self.started:.1f}s", flush=True)

    def finish(self, retained):
        elapsed = time.monotonic() - self.started
        print(f"{self.label}: {self.total}/{self.total} {self.item} completed; "
              f"retained {retained} lines; elapsed {elapsed:.1f}s", flush=True)
