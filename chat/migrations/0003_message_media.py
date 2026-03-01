from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0002_message_audio"),
    ]

    operations = [
        migrations.AddField(
            model_name="message",
            name="image",
            field=models.ImageField(blank=True, null=True, upload_to="chat_images/"),
        ),
        migrations.AddField(
            model_name="message",
            name="video",
            field=models.FileField(blank=True, null=True, upload_to="chat_videos/"),
        ),
    ]
