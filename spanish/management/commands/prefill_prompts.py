from django.core.management.base import BaseCommand

from spanish import grading_service
from spanish.models import PromptPool
from spanish.prompt_pool import LEVELS, refill


class Command(BaseCommand):
    help = "Fill the prompt pool for every writing/oral task type and level."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete all pooled prompts first.")

    def handle(self, *args, reset=False, **options):
        if reset:
            PromptPool.objects.all().delete()
        keys = [("essay", t) for t in grading_service.ESSAY_TYPE_RULES] + \
               [("audio", t) for t in grading_service.ORAL_TYPE_SHAPES]
        # A1 Writing only offers Opinion (see writingTypesFor in App.jsx), so don't pool the others at A1
        upper_only = {"correspondence", "lesson_plan"}
        for kind, task_type in keys:
            for level in LEVELS:
                if level == "A1" and kind == "essay" and task_type in upper_only:
                    continue
                refill(kind, task_type, level)
                self.stdout.write(f"{kind}/{task_type}/{level} ok")
