# Generated by Django 5.1.7 on 2025-03-24 09:50

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('classmanagement', '0001_initial'),
    ]

    operations = [
        migrations.RenameField(
            model_name='assignment',
            old_name='assigned_class',
            new_name='joined_classes',
        ),
    ]
