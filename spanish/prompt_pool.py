"""Pre-generated task prompts. A request takes (and deletes) a random stored prompt;
a background thread tops the pool back up to POOL_SIZE."""
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import grading_service, listening_service
from .models import PromptPool

POOL_SIZE = 10
# Listening selections carry their MP3 (~0.5-1 MB) and cost a TTS call each, so keep fewer.
LISTENING_POOL_SIZE = 4
LEVELS = ["A1", "A2", "B1", "B2"]
# Gemini calls made at once while refilling one pool; higher refills faster but risks 429s.
REFILL_PARALLEL = 3

_refilling = set()
_lock = threading.Lock()


def pool_size(kind):
    return LISTENING_POOL_SIZE if kind == "listening" else POOL_SIZE


def _generate(kind, task_type, level):
    if kind == "listening":
        return listening_service.generate_selection(level)
    if kind == "essay":
        return grading_service.service.generate_task(kind, level, task_type or "opinion")
    return grading_service.service.generate_task(kind, level, "opinion", task_type or None)


def is_current(kind, task):
    """False for a pooled task made before a format change — e.g. a listening selection from
    before each question carried an English rationale. Stale rows are dropped, not served."""
    if kind == "listening":
        questions = task.get("questions") or []
        return bool(questions) and all(q.get("explanation_english") for q in questions)
    return True


def take(kind, task_type, level):
    rows = PromptPool.objects.filter(kind=kind, task_type=task_type, level=level)
    task = None
    while task is None:
        row = rows.order_by("?").first()
        if row is None:
            task = _generate(kind, task_type, level)
        # delete() returning 0 means a concurrent request took this row first — try another
        elif PromptPool.objects.filter(pk=row.pk).delete()[0] and is_current(kind, row.task):
            task = row.task
    refill_async(kind, task_type, level)
    return task


def refill(kind, task_type, level):
    """Top the pool up to pool_size(kind). Generation runs REFILL_PARALLEL at a time (worker threads
    only call Gemini; rows are saved here, on the calling thread). A failed generation is
    skipped, not fatal — the next take() refills again."""
    missing = pool_size(kind) - PromptPool.objects.filter(kind=kind, task_type=task_type, level=level).count()
    if missing <= 0:
        return
    with ThreadPoolExecutor(max_workers=REFILL_PARALLEL) as pool:
        futures = [pool.submit(_generate, kind, task_type, level) for _ in range(missing)]
        for future in as_completed(futures):
            try:
                task = future.result()
            except Exception as e:
                print(f"Prompt generation failed for {(kind, task_type, level)}: {e}")
                continue
            PromptPool.objects.create(kind=kind, task_type=task_type, level=level, task=task)


def refill_async(kind, task_type, level):
    # ponytail: in-process thread; relies on Cloud Run's --no-cpu-throttling (cloudbuild.yaml)
    # or the thread stalls after the response — move to Cloud Tasks if that bites.
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
