"""Pre-generated task prompts. A request takes (and deletes) a random stored prompt;
a background thread tops the pool back up to POOL_SIZE."""
import threading

from . import grading_service
from .models import PromptPool

POOL_SIZE = 5
LEVELS = ["A1", "A2", "B1", "B2"]

_refilling = set()
_lock = threading.Lock()


def _generate(kind, task_type, level):
    if kind == "essay":
        return grading_service.service.generate_task(kind, level, task_type or "opinion")
    return grading_service.service.generate_task(kind, level, "opinion", task_type or None)


def take(kind, task_type, level):
    row = PromptPool.objects.filter(kind=kind, task_type=task_type, level=level).order_by("?").first()
    # delete() returning 0 means a concurrent request took this row first
    task = row.task if row and PromptPool.objects.filter(pk=row.pk).delete()[0] else _generate(kind, task_type, level)
    refill_async(kind, task_type, level)
    return task


def refill(kind, task_type, level):
    have = PromptPool.objects.filter(kind=kind, task_type=task_type, level=level).count()
    for _ in range(POOL_SIZE - have):
        PromptPool.objects.create(kind=kind, task_type=task_type, level=level, task=_generate(kind, task_type, level))


def refill_async(kind, task_type, level):
    # ponytail: in-process thread; on Cloud Run this needs CPU-always-allocated or the
    # thread stalls after the response — move to Cloud Tasks if that bites.
    key = (kind, task_type, level)
    with _lock:
        if key in _refilling:
            return
        _refilling.add(key)

    def run():
        try:
            refill(*key)
        except Exception as e:
            print(f"Prompt pool refill failed for {key}: {e}")
        finally:
            with _lock:
                _refilling.discard(key)

    threading.Thread(target=run, daemon=True).start()
