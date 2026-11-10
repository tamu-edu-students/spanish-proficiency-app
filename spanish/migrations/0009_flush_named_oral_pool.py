# Pooled conversation / Q&A / situation prompts predate the rule that the person the
# student speaks to has a name; drop them so the pool refills with named ones.
from django.db import migrations


def flush(apps, schema_editor):
    apps.get_model('spanish', 'PromptPool').objects.filter(
        kind='audio', task_type__in=['conversation', 'qa', 'situation']
    ).delete()


class Migration(migrations.Migration):
    dependencies = [('spanish', '0008_flush_correspondence_pool')]
    operations = [migrations.RunPython(flush, migrations.RunPython.noop)]
