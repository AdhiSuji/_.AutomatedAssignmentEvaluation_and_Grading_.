# Generated by Django 5.1.6 on 2025-02-22 10:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classmanagement', '0010_alter_customuser_first_name_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customuser',
            name='teacher_reference_id',
            field=models.CharField(blank=True, max_length=20, null=True, unique=True),
        ),
    ]
