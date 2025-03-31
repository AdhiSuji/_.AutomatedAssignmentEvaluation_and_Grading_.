from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import models
from collections import Counter
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser,  BaseUserManager
from django.utils import timezone
from difflib import SequenceMatcher
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import uuid
from django.utils.timezone import now
from PyPDF2 import PdfReader
from docx import Document
from io import BytesIO


# Custom User Manager
class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        extra_fields.setdefault("username", email.split("@")[0])
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)

# Custom User Model
class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('student', 'Student'),
        ('teacher', 'Teacher'),
    ]

    username = models.CharField(max_length=150, unique=True, blank=True, null=True)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    reference_id = models.CharField(max_length=12, unique=True, null=True, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    objects = CustomUserManager()

    def save(self, *args, **kwargs):
        if not self.username:
            self.username = self.email.split('@')[0]
        if self.role == 'teacher' and not self.reference_id:
            self.reference_id = "TCH-" + str(uuid.uuid4().hex[:8]).upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email


CustomUser = get_user_model()

# Teacher Profile
class TeacherProfile(models.Model):
    teacher = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='teacher_profile', primary_key=True)
    reference_id = models.CharField(max_length=20, unique=True, null=True, blank=True, editable=False)
    profile_pic = models.ImageField(upload_to='teacher_profiles/', default='default_folder/default_teacher.jpg')
    bio = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        if self.teacher and not self.reference_id:
            # Generate unique reference ID if not set
            self.reference_id = f"REF-{self.teacher.id:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.teacher.first_name} ({self.reference_id})"

# Student Profile
class StudentProfile(models.Model):
    student = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='student_profile', primary_key=True)
    profile_pic = models.ImageField(upload_to='profile_pics/', default='default_folder/default_student.jpg')
    bio = models.TextField(blank=True, null=True)
    name = models.CharField(max_length=100)
    joined_classes = models.ManyToManyField('Classroom', related_name='joined_students', blank=True)  # ✅ Correct Many-to-Many

    def __str__(self):
        return self.student.email


# Classroom Model
class Classroom(models.Model):
    teacher = models.ForeignKey(TeacherProfile, on_delete=models.CASCADE, related_name='classrooms')
    students = models.ManyToManyField('StudentProfile', related_name='joined_classes')
    name = models.CharField(max_length=100)
    subject = models.CharField(max_length=100, null=False, default="General") 
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.teacher.teacher.first_name}"


# Assignment Model
class Assignment(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(default="No description provided.")
    due_date = models.DateTimeField()
    keywords = models.TextField(blank=True, null=True)

    teacher = models.ForeignKey(TeacherProfile, on_delete=models.CASCADE, related_name='assignments')
    joined_classes = models.ForeignKey(Classroom, on_delete=models.CASCADE, related_name='assignments', null=True, blank=True)
    plagiarism_active = models.BooleanField(default=False) 

    def __str__(self):
        return f"{self.title} ({self.joined_classes.name if self.joined_classes else 'No Class'})"


class Submission(models.Model):
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='submissions')
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='submissions')
    file = models.FileField(upload_to='submissions/')
    submitted_at = models.DateTimeField(default=timezone.now)
    content = models.TextField(blank=True, null=True)  # Store extracted text
    plagiarism_score = models.FloatField(default=0.0)  # Only for student-to-student comparisons
    keyword_match = models.FloatField(default=0.0)  # Teacher-to-student keyword match percentage
    is_late = models.BooleanField(default=False)
    grammar_score = models.IntegerField(default=0)
    total_marks = models.IntegerField(default=0) 
    grade = models.CharField(max_length=2, blank=True, null=True) 
    feedback = models.TextField(blank=True, null=True)
    comments = models.TextField(blank=True, null=True)
    word_frequencies = models.JSONField(default=dict)  # Stores word frequency as JSON

    def __str__(self):
        return f"{self.student.student.email} - {self.assignment.title}"

# Performance Model
class Performance(models.Model):
    student = models.OneToOneField(StudentProfile, on_delete=models.CASCADE, related_name='performance')
    average_score = models.FloatField(default=0.0)
    completed_assignments = models.IntegerField(default=0)

    def update_performance(self):
        submissions = Submission.objects.filter(student=self.student, grade__isnull=False)
        if submissions.exists():
            GRADE_MAPPING = {(0, 20): 10,    (21, 40): 8,     (41, 60): 5,     (61, 80): 3,(81, 100): 0,}

            grades = [GRADE_MAPPING.get(sub.grade, 0) for sub in submissions if sub.grade]
            if grades:
                self.average_score = sum(grades) / len(grades)
            self.completed_assignments = submissions.count()
        self.save()

    def __str__(self):
        return f"{self.student.student.email} - Avg: {self.average_score}"



User = get_user_model()

class QueryMessage(models.Model):
    classroom = models.ForeignKey('Classroom', on_delete=models.CASCADE, related_name='queries')
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    timestamp = models.DateTimeField(default=now)

    def __str__(self):
        return f"{self.sender.first_name}: {self.message[:50]}"


class PrivateMessage(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    message = models.TextField()
    timestamp = models.DateTimeField(default=now)

    def __str__(self):
        return f"From {self.sender.first_name} to {self.receiver.first_name}: {self.message[:50]}"

class PrivateChat(models.Model):
    user1 = models.ForeignKey(User, on_delete=models.CASCADE, related_name="private_chats1")
    user2 = models.ForeignKey(User, on_delete=models.CASCADE, related_name="private_chats2")

    class Meta:
        unique_together = ('user1', 'user2')  # Ensure each chat is unique
