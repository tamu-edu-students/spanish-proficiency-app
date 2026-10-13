# Pooled lesson-plan prompts predate the TEKS/K–5 alignment; drop them so the
# pool refills with aligned ones instead of serving stale prompts first.
from django.db import migrations


def flush(apps, schema_editor):
    apps.get_model('spanish', 'PromptPool').objects.filter(task_type='lesson_plan').delete()


class Migration(migrations.Migration):
    dependencies = [('spanish', '0006_promptpool')]
    operations = [migrations.RunPython(flush, migrations.RunPython.noop)]
