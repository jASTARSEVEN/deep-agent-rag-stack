"""Celery 骨架 worker 的 task 模組。"""

from worker.tasks.health import ping

__all__ = ["ping"]
