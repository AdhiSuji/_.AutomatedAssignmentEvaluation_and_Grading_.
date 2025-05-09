# Generated by Django 5.1.7 on 2025-04-27 19:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classmanagement', '0043_rename_grade_submission_grade_before_plagiarism_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='submission',
            name='final_marks',
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=5),
        ),
        migrations.AlterField(
            model_name='submission',
            name='provisional_marks',
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=5),
        ),
    ]
