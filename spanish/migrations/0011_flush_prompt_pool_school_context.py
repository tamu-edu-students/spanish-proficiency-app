# Every pooled prompt predates the school-context rule (SCHOOL_CONTEXT_RULE); drop them
# all so the pool refills with school-centred topics.
from django.db import migrations


def flush(apps, schema_editor):
    apps.get_model('spanish', 'PromptPool').objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [('spanish', '0010_reflush_correspondence_pool')]
    operations = [migrations.RunPython(flush, migrations.RunPython.noop)]
