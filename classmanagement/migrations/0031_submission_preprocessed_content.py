# Generated by Django 5.1.7 on 2025-04-13 10:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classmanagement', '0030_rename_keyword_match_submission_content_match_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='submission',
            name='preprocessed_content',
            field=models.TextField(blank=True, null=True),
        ),
    ]
