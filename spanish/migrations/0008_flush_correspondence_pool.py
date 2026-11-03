# Pooled correspondence prompts predate the formal colon greeting
# ("Estimada maestra:"); drop them so the pool refills with corrected ones.
from django.db import migrations


def flush(apps, schema_editor):
    apps.get_model('spanish', 'PromptPool').objects.filter(task_type='correspondence').delete()


class Migration(migrations.Migration):
    dependencies = [('spanish', '0007_flush_lesson_plan_pool')]
    operations = [migrations.RunPython(flush, migrations.RunPython.noop)]
