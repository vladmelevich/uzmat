from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("uzmat", "0013_chat_models"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="user",
            name="verification_doc1",
        ),
        migrations.RemoveField(
            model_name="user",
            name="verification_doc2",
        ),
        migrations.RemoveField(
            model_name="user",
            name="verification_doc3",
        ),
        migrations.DeleteModel(
            name="VerificationDocument",
        ),
    ]












