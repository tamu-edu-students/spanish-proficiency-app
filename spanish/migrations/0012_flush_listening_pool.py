# Listening selections pooled before each question carried an English rationale
# (explanation_english) show no "Show English" at A1/A2; drop them so the pool refills.
# prompt_pool.is_current also skips any stale row that slips through.
from django.db import migrations


def flush(apps, schema_editor):
    apps.get_model('spanish', 'PromptPool').objects.filter(kind='listening').delete()


class Migration(migrations.Migration):
    dependencies = [('spanish', '0011_flush_prompt_pool_school_context')]
    operations = [migrations.RunPython(flush, migrations.RunPython.noop)]
