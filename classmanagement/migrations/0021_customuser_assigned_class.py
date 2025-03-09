# Generated by Django 5.1.6 on 2025-03-08 12:52

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classmanagement', '0020_rename_class_classroom'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='assigned_class',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='students', to='classmanagement.classroom'),
        ),
    ]
