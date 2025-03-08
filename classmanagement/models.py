from django.db import models
from django.contrib.auth.models import AbstractUser,  BaseUserManager
from django.utils import timezone
from difflib import SequenceMatcher
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import uuid


class CustomUserManager(BaseUserManager):
    """Custom user model manager where email is the unique identifier instead of username"""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        extra_fields.setdefault("username", email.split("@")[0])  # Set username automatically
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)

class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ("student", "Student"),
        ("teacher", "Teacher"),
    ]

    username = models.CharField(max_length=150, unique=True, blank=True, null=True)  # Allow blank username
    email = models.EmailField(unique=True)  # Use email as primary identifier
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="student")
    reference_id = models.CharField(max_length=12, unique=True, null=True, blank=True)
    USERNAME_FIELD = "email"  # Set email as the primary field for authentication
    REQUIRED_FIELDS = ["username"]  # Keep username but auto-generate it

    objects = CustomUserManager()

    def save(self, *args, **kwargs):
        if not self.username:
            self.username = self.email.split("@")[0]  # Auto-generate username from email
        super().save(*args, **kwargs)
    
    def save(self, *args, **kwargs):
        if self.role == "teacher" and not self.reference_id:
            self.reference_id = "TCH-" + str(uuid.uuid4().hex[:8]).upper()  # Generate Unique Reference ID
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email


# Class Model (Teachers can create classes)
class Classroom(models.Model):
    name = models.CharField(max_length=100)
    teacher = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='classes')
    
    def __str__(self):
        return self.name


class TeacherProfile(models.Model):
    teacher = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name="teacher_profile")
    
    def __str__(self):
        return self.teacher.first_name

# Student Profile (Linked to Classes)
class StudentProfile(models.Model):
    student = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='student_profile')
    assigned_class = models.ForeignKey(Classroom, on_delete=models.SET_NULL, null=True, blank=True)
    
    def __str__(self):
        return f"{self.student.email} - {self.assigned_class.name if self.assigned_class else 'No Class'}"
# Assignments
class Assignment(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(default="No description provided.")
    due_date = models.DateTimeField()  # Ensure this field is present
    keywords = models.TextField(blank=True, null=True)  # Ensure this field is present
    teacher = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='assignments')
    assigned_class = models.ForeignKey(Classroom, on_delete=models.CASCADE, related_name='assignments', null=True, blank=True, default=None)

    def __str__(self):
        return self.title

# Assignment Submission
class Submission(models.Model):
    student = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='submissions')
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='submissions')
    file = models.FileField(upload_to='submissions/')
    submitted_at = models.DateTimeField(default=timezone.now)
    plagiarism_score = models.FloatField(default=0.0)
    is_late = models.BooleanField(default=False)
    grade = models.CharField(max_length=2, blank=True, null=True)
    feedback = models.TextField(blank=True, null=True)
    comments = models.TextField(blank=True, null=True)
    
    def calculate_plagiarism(self, other_submissions):
        highest_score = 0.0
        for other in other_submissions:
            similarity = SequenceMatcher(None, self.file.read(), other.file.read()).ratio()
            highest_score = max(highest_score, similarity)
        self.plagiarism_score = round(highest_score * 100, 2)
        self.save()
    
    def __str__(self):
        return f"{self.student.username} - {self.assignment.title}"

# Performance Tracking
class Performance(models.Model):
    student = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='performance')
    average_score = models.FloatField(default=0.0)
    completed_assignments = models.IntegerField(default=0)
    
    def update_performance(self):
        submissions = Submission.objects.filter(student=self.student, graded=True)
        if submissions.exists():
            grades = [float(sub.grade) for sub in submissions if sub.grade is not None]
            if grades:
                self.average_score = sum(grades) / len(grades)
            self.completed_assignments = submissions.count()
        self.save()
    
    def __str__(self):
        return f"{self.student.username} - {self.average_score}"

# Query Model for student queries
class Query(models.Model):
    student = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='queries')
    teacher = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='received_queries')
    question = models.TextField()
    answer = models.TextField(blank=True, null=True)
    asked_at = models.DateTimeField(default=timezone.now)
    answered_at = models.DateTimeField(blank=True, null=True)
    response = models.TextField(blank=True, null=True) 

    def __str__(self):
        return f"Query by {self.student.username} to {self.teacher.username}"

