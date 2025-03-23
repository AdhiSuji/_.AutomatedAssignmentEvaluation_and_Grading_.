from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import models
from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser,  BaseUserManager, User
from django.utils import timezone
from difflib import SequenceMatcher
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import uuid


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


# Classroom Model
class Classroom(models.Model):
    teacher = models.ForeignKey(TeacherProfile, on_delete=models.CASCADE, related_name='classrooms')
    name = models.CharField(max_length=100)
    subject = models.CharField(max_length=100, null=False, default="General") 
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.teacher.teacher.first_name}"


# Student Profile
class StudentProfile(models.Model):
    student = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='student_profile', primary_key=True)
    profile_pic = models.ImageField(upload_to='profile_pics/', default='default_folder/default_student.jpg')
    bio = models.TextField(blank=True, null=True)
    name = models.CharField(max_length=100)
    joined_classes = models.ManyToManyField(Classroom, related_name='joined_students', blank=True)
    
    def __str__(self):
        return self.student.email

# Assignment Model
class Assignment(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(default="No description provided.")
    due_date = models.DateTimeField()
    keywords = models.TextField(blank=True, null=True)

    teacher = models.ForeignKey(TeacherProfile, on_delete=models.CASCADE, related_name='assignments')
    assigned_class = models.ForeignKey(Classroom, on_delete=models.CASCADE, related_name='assignments', null=True, blank=True)

    def __str__(self):
        return f"{self.title} ({self.assigned_class.name if self.assigned_class else 'No Class'})"

# Submission Model
class Submission(models.Model):
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='submissions')
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='submissions')
    file = models.FileField(upload_to='submissions/')
    submitted_at = models.DateTimeField(default=timezone.now)
    plagiarism_score = models.FloatField(default=0.0)
    is_late = models.BooleanField(default=False)
    grade = models.FloatField(blank=True, null=True)
    feedback = models.TextField(blank=True, null=True)
    comments = models.TextField(blank=True, null=True)

    # ✅ Always check keywords after submission
    def check_keywords(self):
        assignment_keywords = self.assignment.keywords.lower().split(",") if self.assignment.keywords else []
        
        try:
            self.file.open()
            file_content = self.file.read().decode('utf-8').lower()
            self.file.close()

            missing_keywords = [kw.strip() for kw in assignment_keywords if kw.strip() not in file_content]

            if missing_keywords:
                return f"Missing keywords: {', '.join(missing_keywords)}"
            else:
                return "All keywords present."

        except Exception as e:
            return f"Error reading file: {str(e)}"

    # ✅ Teacher-triggered plagiarism check (TF-IDF + Cosine Similarity)
    def calculate_plagiarism_between_students(self):
        # Get all submissions for this assignment (excluding self)
        other_submissions = Submission.objects.filter(assignment=self.assignment).exclude(id=self.id)

        # Load current submission text
        try:
            self.file.open()
            current_text = self.file.read().decode('utf-8').lower()
            self.file.close()
        except Exception as e:
            return f"Error reading file: {str(e)}"

        # Collect all other submissions
        texts = [current_text]
        submission_ids = [self.id]

        for submission in other_submissions:
            try:
                submission.file.open()
                other_text = submission.file.read().decode('utf-8').lower()
                submission.file.close()

                texts.append(other_text)
                submission_ids.append(submission.id)
            except Exception as e:
                continue  # Skip if file can't be read

        # No other submissions to compare?
        if len(texts) <= 1:
            self.plagiarism_score = 0.0
            self.save()
            return "No other submissions to compare."

        # Calculate similarity matrix
        vectorizer = TfidfVectorizer().fit_transform(texts)
        similarity_matrix = cosine_similarity(vectorizer)

        # Current submission is at index 0
        similarities = similarity_matrix[0]

        # Ignore self-comparison
        similarities[0] = -1

        # Get the highest similarity score (excluding self)
        highest_similarity = max(similarities)

        self.plagiarism_score = round(highest_similarity * 100, 2)
        self.save()

        return f"Plagiarism score updated: {self.plagiarism_score}%"

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


# Query Model for student queries
class Query(models.Model):
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='queries')
    teacher = models.ForeignKey(TeacherProfile, on_delete=models.CASCADE, related_name='received_queries')
    question = models.TextField()
    answer = models.TextField(blank=True, null=True)
    asked_at = models.DateTimeField(default=timezone.now)
    answered_at = models.DateTimeField(blank=True, null=True)
    response = models.TextField(blank=True, null=True) 

    def __str__(self):
        return f"Query by {self.student.username} to {self.teacher.username}"

