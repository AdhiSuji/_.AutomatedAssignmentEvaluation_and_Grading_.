# Generated by Django 5.1.7 on 2025-04-12 07:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classmanagement', '0026_remove_performance_average_score'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='assignment',
            name='keywords',
        ),
        migrations.AddField(
            model_name='assignment',
            name='model_answer_file',
            field=models.FileField(blank=True, null=True, upload_to='model_answers/'),
        ),
    ]
