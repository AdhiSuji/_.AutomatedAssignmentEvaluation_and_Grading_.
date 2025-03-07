# Generated by Django 5.1.6 on 2025-03-04 06:04

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classmanagement', '0014_class'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='teacher',
            name='user',
        ),
        migrations.RemoveField(
            model_name='teacherstudent',
            name='student',
        ),
        migrations.RemoveField(
            model_name='teacherstudent',
            name='teacher',
        ),
        migrations.RenameField(
            model_name='query',
            old_name='message',
            new_name='question',
        ),
        migrations.RemoveField(
            model_name='assignment',
            name='created_at',
        ),
        migrations.RemoveField(
            model_name='assignment',
            name='file',
        ),
        migrations.RemoveField(
            model_name='assignment',
            name='is_submission',
        ),
        migrations.RemoveField(
            model_name='assignment',
            name='submitted_assignments',
        ),
        migrations.RemoveField(
            model_name='customuser',
            name='assigned_teacher',
        ),
        migrations.RemoveField(
            model_name='customuser',
            name='teacher_reference_id',
        ),
        migrations.RemoveField(
            model_name='performance',
            name='assignment',
        ),
        migrations.RemoveField(
            model_name='performance',
            name='grade',
        ),
        migrations.RemoveField(
            model_name='query',
            name='created_at',
        ),
        migrations.AddField(
            model_name='assignment',
            name='assigned_class',
            field=models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='assignments', to='classmanagement.class'),
        ),
        migrations.AddField(
            model_name='customuser',
            name='reference_id',
            field=models.CharField(blank=True, max_length=10, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='performance',
            name='average_score',
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name='performance',
            name='completed_assignments',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='query',
            name='answer',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='query',
            name='answered_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='query',
            name='asked_at',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AddField(
            model_name='submission',
            name='comments',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='submission',
            name='plagiarism_score',
            field=models.FloatField(default=0.0),
        ),
        migrations.AlterField(
            model_name='assignment',
            name='description',
            field=models.TextField(default='No description provided.'),
        ),
        migrations.AlterField(
            model_name='assignment',
            name='due_date',
            field=models.DateTimeField(),
        ),
        migrations.AlterField(
            model_name='assignment',
            name='keywords',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='assignment',
            name='teacher',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assignments', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='class',
            name='name',
            field=models.CharField(max_length=100),
        ),
        migrations.AlterField(
            model_name='customuser',
            name='first_name',
            field=models.CharField(blank=True, max_length=150, verbose_name='first name'),
        ),
        migrations.AlterField(
            model_name='customuser',
            name='last_name',
            field=models.CharField(blank=True, max_length=150, verbose_name='last name'),
        ),
        migrations.AlterField(
            model_name='performance',
            name='student',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='performance', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='query',
            name='teacher',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='received_queries', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='submission',
            name='grade',
            field=models.CharField(blank=True, max_length=2, null=True),
        ),
        migrations.AlterField(
            model_name='submission',
            name='student',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='submissions', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='submission',
            name='submitted_at',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.CreateModel(
            name='StudentProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('assigned_class', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='classmanagement.class')),
                ('student', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='profile', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.DeleteModel(
            name='Student',
        ),
        migrations.DeleteModel(
            name='Teacher',
        ),
        migrations.DeleteModel(
            name='TeacherStudent',
        ),
    ]
