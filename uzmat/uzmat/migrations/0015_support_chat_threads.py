from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("uzmat", "0014_remove_verification_documents"),
    ]

    operations = [
        migrations.AddField(
            model_name="chatthread",
            name="thread_type",
            field=models.CharField(choices=[("ad", "По объявлению"), ("support", "Техподдержка")], default="ad", max_length=20, verbose_name="Тип чата"),
        ),
        migrations.AlterField(
            model_name="chatthread",
            name="advertisement",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="chat_threads", to="uzmat.advertisement", verbose_name="Объявление"),
        ),
        migrations.RemoveConstraint(
            model_name="chatthread",
            name="unique_chat_by_ad_and_users",
        ),
        migrations.AddConstraint(
            model_name="chatthread",
            constraint=models.UniqueConstraint(fields=("thread_type", "advertisement", "buyer", "seller"), name="unique_chat_by_type_ad_and_users"),
        ),
    ]





