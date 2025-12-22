from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("uzmat", "0015_support_chat_threads"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="badge_expiry_notified_until",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Напоминание о продлении отправлено для срока до"),
        ),
        migrations.AddField(
            model_name="chatmessage",
            name="system_action",
            field=models.CharField(blank=True, choices=[("renew_badge", "Продлить галочку")], max_length=50, null=True, verbose_name="Системное действие"),
        ),
        migrations.AddField(
            model_name="chatmessage",
            name="system_url",
            field=models.CharField(blank=True, max_length=500, null=True, verbose_name="URL действия"),
        ),
    ]





