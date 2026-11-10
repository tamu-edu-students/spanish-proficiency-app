# Writing/Speaking prompts pooled before TEACHER_ROLE_RULE may cast the user as a pupil;
# drop them so the pool refills with teacher-perspective tasks. Listening is unaffected.
from django.db import migrations


def flush(apps, schema_editor):
    apps.get_model('spanish', 'PromptPool').objects.filter(kind__in=['essay', 'audio']).delete()


class Migration(migrations.Migration):
    dependencies = [('spanish', '0012_flush_listening_pool')]
    operations = [migrations.RunPython(flush, migrations.RunPython.noop)]
