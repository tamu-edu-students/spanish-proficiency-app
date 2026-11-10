# Correspondence prompts pooled after 0008 lack the blank signature line after the
# closing ("Atentamente,"); drop them so the pool refills with the new layout.
from django.db import migrations


def flush(apps, schema_editor):
    apps.get_model('spanish', 'PromptPool').objects.filter(task_type='correspondence').delete()


class Migration(migrations.Migration):
    dependencies = [('spanish', '0009_flush_named_oral_pool')]
    operations = [migrations.RunPython(flush, migrations.RunPython.noop)]
