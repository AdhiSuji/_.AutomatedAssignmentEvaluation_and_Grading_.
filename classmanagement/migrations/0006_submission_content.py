# Generated by Django 5.1.7 on 2025-03-26 09:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classmanagement', '0005_assignment_plagiarism_active'),
    ]

    operations = [
        migrations.AddField(
            model_name='submission',
            name='content',
            field=models.TextField(blank=True, null=True),
        ),
    ]
