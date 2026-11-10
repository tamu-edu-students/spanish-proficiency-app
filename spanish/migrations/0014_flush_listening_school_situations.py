# Listening selections now come from elementary-school situations (parent conferences,
# calls to parents, LPAC meetings…) and the model no longer labels options "A) …";
# drop pooled selections made before so the pool refills with the new ones.
from django.db import migrations


def flush(apps, schema_editor):
    apps.get_model('spanish', 'PromptPool').objects.filter(kind='listening').delete()


class Migration(migrations.Migration):
    dependencies = [('spanish', '0013_flush_pool_teacher_perspective')]
    operations = [migrations.RunPython(flush, migrations.RunPython.noop)]
