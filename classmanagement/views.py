from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.core.mail import send_mail
import nltk
import PyPDF2
import docx
import logging
import json
from django.db import models
from collections import defaultdict
from textblob import TextBlob
from difflib import SequenceMatcher
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from django.http import JsonResponse
from django.db.models import Q
from django.core.paginator import Paginator
from .models import (CustomUser, Classroom, Assignment, Submission,Performance,  StudentProfile, TeacherProfile)
from .forms import ( AssignmentForm, SubmissionForm, ClassForm,StudentProfileForm)
from .notifications import notify_teacher_and_student  # Ensure this function exists
User = get_user_model()

#UTILS             

def is_admin(user):
    return user.is_authenticated and user.role == 'admin'

def is_teacher(user):
    return user.is_authenticated and user.role == 'teacher'

def is_student(user):
    return user.is_authenticated and user.role == 'student'

def profile_view(request):
    profile = StudentProfile.objects.get(user=request.user)
    print(profile.profile_pic)
    print(profile.profile_pic.url)
    
    return render(request, 'profile.html', {'profile': profile})

 #VIEWS             

def home_view(request):
    return render(request, 'home.html')

def privacy_policy(request):
    return render(request, 'privacy_policy.html')

from django.shortcuts import render
from django.core.mail import send_mail
from django.contrib import messages

def contact_us(request):
    if request.method == "POST":
        name = request.POST.get('name')
        email = request.POST.get('email')
        message = request.POST.get('message')

        # Sending email (you need to configure email settings in Django)
        send_mail(
            f"Contact Form Submission from {name}",
            message,
            email,
            ['submitech1@gmail.com'],  # Replace with your email
            fail_silently=False,
        )

        messages.success(request, "Your message has been sent!")
    
    return render(request, 'contact_us.html')

# REGISTRATION      
def register(request):
    if request.method == "POST":
        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        email = request.POST.get("email")
        role = request.POST.get("role")
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")

        if password != confirm_password:
            messages.error(request, "Passwords do not match!")
            return render(request, "register.html", {"form_data": request.POST})

        if CustomUser.objects.filter(email=email).exists():
            messages.error(request, "Email is already registered!")
            return render(request, "register.html", {"form_data": request.POST})

        user = CustomUser.objects.create_user(
            username=email,
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=password,
            role=role
        )

        login(request, user)

        if role == "student":
            # Create StudentProfile + Performance
            student_profile = StudentProfile.objects.create(student=user)
            Performance.objects.create(student=student_profile)

            messages.success(request, "Student registered successfully!")
            return redirect("student_profile")

        elif role == "teacher":
            # Create TeacherProfile
            teacher_profile = TeacherProfile.objects.create(teacher=user)
            messages.success(request, "Teacher registered successfully!")
            return redirect('teacher_create_class')

        messages.error(request, "Invalid role! Contact admin.")
        return redirect('register')

    return render(request, "register.html")


#LOGIN           
def user_login(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        user = authenticate(request, email=email, password=password)

        if not user:
            messages.error(request, "Invalid email or password!")
            return redirect("login")

        login(request, user)
        messages.success(request, "Login successful!")

        # STUDENT LOGIN
        if user.role == "student":
            # Get or Create StudentProfile
            student_profile, created = StudentProfile.objects.get_or_create(student=user)

            # Create performance record if new profile was created
            if created:
                Performance.objects.create(student=student_profile)

            # ✅ FIX: Access classrooms instead of assigned_class
            joined_classes = student_profile.joined_classes.all()

            if joined_classes.exists():
                first_class = joined_classes.first()  # Grab the first class
                return redirect("student_dashboard", class_id=first_class.id)
            else:
                messages.warning(request, "No class assigned! Contact your teacher.")
                return redirect("student_profile")

        # TEACHER LOGIN
        elif user.role == "teacher":
            # Get or Create TeacherProfile (avoid duplicates)
            teacher_profile, created = TeacherProfile.objects.get_or_create(teacher=user)

            # ✅ Corrected: Use teacher_profile instead of user
            teacher_classes = Classroom.objects.filter(teacher=teacher_profile)

            if teacher_classes.exists():
                class_obj = teacher_classes.first()
                return redirect('teacher_dashboard', class_id=class_obj.id)
            else:
                return redirect('teacher_profile')

        # ADMIN LOGIN
        elif user.role == "admin":
            return redirect("admin_dashboard")

        # Unknown role
        messages.error(request, "Invalid role! Contact admin.")
        return redirect("login")

    return render(request, "login.html")

def user_logout(request):
    logout(request)
    return redirect('login')

def student_default_profile():
    return 'default_folder/default_student.jpg'  # path inside media folder

def teacher_default_profile():
    return 'default_folder/default_teacher.jpg'  # path inside media folder

@login_required
@user_passes_test(is_teacher)
def teacher_profile(request):
    teacher_profile = get_object_or_404(TeacherProfile, teacher=request.user)

    # ✅ Fetch all classrooms assigned to this teacher
    created_classes = Classroom.objects.filter(teacher=teacher_profile)

    query = request.GET.get('q')

    # ✅ Corrected field here!
    students = StudentProfile.objects.filter(joined_classes__in=created_classes).distinct()

    if query:
        students = students.filter(
            Q(name__icontains=query) |
            Q(student__email__icontains=query)
        )

    paginator = Paginator(students, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    if not created_classes.exists():
        messages.info(request, "You haven't created any classrooms yet.")

    return render(request, 'teacher_profile.html', {
        'teacher_profile': teacher_profile,
        'created_classes': created_classes,
        'page_obj': page_obj,
        'query': query,

    })


@login_required
@user_passes_test(is_student)
def student_profile(request):
    student_user = request.user
    student_profile, created = StudentProfile.objects.get_or_create(student=student_user)

    if request.method == 'POST':
        form = StudentProfileForm(request.POST, request.FILES, instance=student_profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully!")
            return redirect('student_profile')
    else:
        form = StudentProfileForm(instance=student_profile)

    joined_classes = student_profile.joined_classes.all()
    assignments = Assignment.objects.filter(joined_classes__in=joined_classes)
    teachers = TeacherProfile.objects.filter(classrooms__in=joined_classes).distinct()
    performance, _ = Performance.objects.get_or_create(student=student_profile)

    classroom = joined_classes.first() if joined_classes.exists() else None
    teacher = teachers.first()  # Get the first teacher if multiple exist

    teacher_id = teacher.teacher.id if teacher else None  # ✅ Get correct teacher ID
    student_id = student_profile.student.id if student_profile else None  # ✅ Get correct student ID

    context = {
        'student_profile': student_profile,
        'joined_classes': joined_classes,
        'assignments': assignments,
        'teachers': teachers,
        'performance': performance,
        'form': form,
        'classroom': classroom,
        'teacher_id': teacher_id,
        'student_id': student_id,
    }

    return render(request, 'student_profile.html', context)

@login_required
def teacher_dashboard(request, class_id=None):
    """Teacher's Dashboard: Displays student performance for a selected class."""
    teacher = get_object_or_404(TeacherProfile, teacher=request.user)

    classes = Classroom.objects.filter(teacher=teacher)  # Get all teacher's classes

    # ✅ Ensure `class_id` is an integer
    class_id = request.GET.get('class_id')  # Get class ID from URL
    if class_id:
        current_class = get_object_or_404(Classroom, id=int(class_id))
    else:
        current_class = classes.first()  # Default to first class

    # ✅ Ensure class_id is always an integer
    class_id = current_class.id if current_class else None

    # ✅ Get students in the selected class
    students = StudentProfile.objects.filter(joined_classes__id=class_id)

    # ✅ Debug: Print retrieved students
    print("DEBUG: Students in class:", students)  # <-- Check if this prints students in console

    # ✅ Get assignments for this class
    assignments = Assignment.objects.filter(joined_classes__id=class_id, teacher=teacher)  # ✅ FIXED
    submissions = Submission.objects.filter(assignment__joined_classes__id=class_id)  # ✅ FIXED

    # ✅ Collect performance data
    performance_data = defaultdict(list)
    for submission in submissions:
        performance_data[submission.student.student.email].append({
            "assignment": submission.assignment.title,
            "marks": submission.total_marks,
            "date": submission.submitted_at.strftime('%Y-%m-%d')
        })

    # ✅ Get top 3 students based on performance
    top_students = Performance.objects.filter(student__joined_classes__id=class_id).order_by('-average_score')[:3]

    return render(request, 'teacher_dashboard.html', {
        'classes': classes,
        'current_class': current_class,
        'students': students,  # ✅ Pass students to template
        'assignments': assignments,
        'performance_data': dict(performance_data),
        'top_students': top_students
    })


@login_required
def student_dashboard(request,class_id =None):
    """Student's Dashboard: Shows personal & class performance trends."""
    student = get_object_or_404(StudentProfile, student=request.user)
    submissions = Submission.objects.filter(student=student).order_by('-submitted_at')

    # ✅ Personal performance trend (line chart data)
    student_performance = []
    for s in submissions:
        student_performance.append({
            "assignment": s.assignment.title,
            "marks": s.total_marks,
            "grade": s.grade,  # ✅ Include grade
            "feedback": s.feedback          })

    # ✅ Class average performance trend
    all_students = StudentProfile.objects.filter(joined_classes__in=student.joined_classes.all())
    class_performance = defaultdict(list)

    for s in all_students:
        sub = Submission.objects.filter(student=s).order_by('-submitted_at')
        for subm in sub:
            class_performance[subm.assignment.title].append(subm.total_marks)

    # ✅ Compute average marks for each assignment (avoid division by zero)
    avg_class_performance = {assignment: (sum(marks) / len(marks)) if marks else 0 for assignment, marks in class_performance.items()}

    # ✅ Get Top 3 performers in the class
    student_scores = []
    for s in all_students:
        total_marks = Submission.objects.filter(student=s).aggregate(total=models.Sum('total_marks'))['total'] or 0
        student_scores.append({"student_name":f"{s.student.first_name} {s.student.last_name}".strip(), "overall_score": total_marks})

    top_performers = sorted(student_scores, key=lambda x: x['overall_score'], reverse=True)[:3]

    return render(request, 'student_dashboard.html', {
        'submissions': submissions,
        'student_performance_json': json.dumps(student_performance),
        'avg_class_performance_json': json.dumps(avg_class_performance),
        'top_performers': top_performers
    })


#ADMIN VIEWS (Optional)   
@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    teachers = CustomUser.objects.filter(role='teacher')
    students = CustomUser.objects.filter(role='student')
    classes = Classroom.objects.all()

    return render(request, 'admin_dashboard.html', {
        'teachers': teachers,
        'students': students,
        'classes': classes
    })


@login_required
@user_passes_test(is_teacher)
def create_class(request):
    if request.method == "POST":
        form = ClassForm(request.POST)
        if form.is_valid():
            new_class = form.save(commit=False)
            teacher_profile = TeacherProfile.objects.get(teacher=request.user)
            new_class.teacher = teacher_profile
            new_class.save()
            messages.success(request, "Class created successfully!")
            return redirect('teacher_dashboard',class_id=new_class.id)

    else:
        form = ClassForm()

    return render(request, 'create_class.html', {'form': form})


@login_required
@user_passes_test(is_teacher)
def teacher_classes(request):
    teacher_profile = get_object_or_404(TeacherProfile, teacher=request.user)
    classes = Classroom.objects.filter(teacher=teacher_profile)
    context = {
        'classes': classes
    }

    return render(request, 'teacher_classes.html', context)


@login_required
@user_passes_test(is_student)
def enroll_students(request, class_id):
    print("DEBUG: Is user authenticated?", request.user.is_authenticated)
    print("DEBUG: Logged-in user:", request.user)
    print("DEBUG: User groups:", request.user.groups.all())

    if request.method == "POST":
        reference_id = request.POST.get("reference_id")
        class_id = request.POST.get("selected_class")

        teacher = TeacherProfile.objects.filter(reference_id=reference_id).first()
        if not teacher:
            messages.error(request, "Invalid Teacher Reference ID.")
            return redirect('enroll_student')

        selected_class = Classroom.objects.filter(id=class_id, teacher=teacher).first()
        if not selected_class:
            messages.error(request, "Invalid Class Selection.")
            return redirect('enroll_student')

        student_profile = get_object_or_404(StudentProfile, student=request.user)

        if selected_class in student_profile.joined_classes.all():
            messages.warning(request, "You are already enrolled in this class.")
        else:
            student_profile.joined_classes.add(selected_class)
            messages.success(request, f"Successfully enrolled in {selected_class.name}.")

        return redirect('student_dashboard')

    return render(request, 'enroll_student.html')

@login_required
@user_passes_test(is_teacher)
def view_enrolled_students(request, class_id):
    classroom = get_object_or_404(Classroom, id=class_id, teacher__teacher=request.user)
    students = classroom.joined_students.all()  # ✅ Correct way to get enrolled students

    return render(request, 'view_students.html', {'classroom': classroom, 'students': students})


def teacher_list(request):
    teachers = CustomUser.objects.filter(role="teacher")
    return render(request, "teacher_list.html", {"teachers": teachers})

@login_required
def add_teacher(request):
    if request.method == 'POST':
        teacher_reference_id = request.POST.get('teacher_reference_id')
        joined_classes_id = request.POST.get('joined_classes')

        if not teacher_reference_id or not joined_classes_id:
            messages.error(request, "Please enter both Teacher Reference ID and select a class.")
            return redirect('student_profile')

        try:
            # Get class by assigned_class_id
            classroom = Classroom.objects.get(id=joined_classes_id, teacher__reference_id=teacher_reference_id)

            # Get student profile
            student_profile = request.user.student_profile

            # Add the class to the student’s profile (ManyToManyField)
            student_profile.joined_classes.add(classroom)

            messages.success(request, f"You have successfully joined {classroom.name}!")
            return redirect('student_profile')

        except Classroom.DoesNotExist:
            messages.error(request, "Classroom not found for the given reference ID.")
            return redirect('student_profile')

    else:
        return redirect('student_profile')

def get_teacher_classes(request):
    reference_id = request.GET.get('reference_id')

    if not reference_id:
        return JsonResponse({'error': 'No reference ID provided'}, status=400)

    try:
        teacher = get_object_or_404(TeacherProfile, reference_id=reference_id)
        classes = Classroom.objects.filter(teacher=teacher)

        class_list = [
            {'id': cls.id, 'name': cls.name}
            for cls in classes
        ]

        return JsonResponse({'classes': class_list})

    except TeacherProfile.DoesNotExist:
        return JsonResponse({'classes': []})


def join_class(request):
    if request.method == 'POST':
        teacher_reference_id = request.POST.get('teacher_reference_id')
        joined_classes_id = request.POST.get('joined_classes')

        print("Received POST Data:", request.POST)  # Debugging output

        if not teacher_reference_id or not joined_classes_id:
            messages.error(request, "Please enter both Teacher Reference ID and select a class.")
            return redirect('join_class')  # Redirect back to the form
        
        try:
            teacher = TeacherProfile.objects.get(reference_id=teacher_reference_id)
            classroom = Classroom.objects.get(id=joined_classes_id)

            student_profile, created = StudentProfile.objects.get_or_create(student=request.user)
            if classroom in student_profile.joined_classes.all():
                messages.warning(request, 'You have already joined this class.')
                return redirect('student_profile')

            student_profile.joined_classes.add(classroom)
            student_profile.save()

            messages.success(request, 'Successfully joined the class!')
            return redirect('student_profile')

        except TeacherProfile.DoesNotExist:
            messages.error(request, 'Teacher not found.')
        except Classroom.DoesNotExist:
            messages.error(request, 'Class not found.')
        except Exception as e:
            messages.error(request, f"Unexpected error: {e}")
            print(f"Unexpected error: {e}")  # Print error for debugging

    return redirect('join_class')


@login_required
@user_passes_test(is_teacher)
def delete_class(request, class_id):
    class_obj = get_object_or_404(Classroom, id=class_id, teacher=request.user)

    if request.method == "POST":
        class_obj.delete()
        messages.success(request, "Class deleted successfully!")

    return redirect("teacher_dashboard")

@login_required
@user_passes_test(is_teacher)
def give_assignment(request, class_id):
    teacher_profile = get_object_or_404(TeacherProfile, teacher=request.user)

    classroom = get_object_or_404(Classroom, id=class_id)

    if request.method == "POST":
        form = AssignmentForm(request.POST)
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.teacher = teacher_profile  # ✅ Now it's the correct object type
            assignment.joined_classes = classroom  # ✅ Assign class based on class_id
            assignment.save()
            messages.success(request, "Assignment given successfully!")
            return redirect('teacher_dashboard', class_id=class_id)
    else:
        form = AssignmentForm()

    # Optional: fetch existing assignments for the class
    given_assignments = Assignment.objects.filter(teacher=teacher_profile)

    paginator = Paginator(given_assignments, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'give_assignment.html', {
        'form': form,
        'page_obj': page_obj
    })


@login_required
def given_assignment(request, class_id):
    class_obj = get_object_or_404(Classroom, id=class_id)
    assignments = Assignment.objects.filter(joined_classes=class_obj)

    return render(request, "given_assignment.html", {
        "assignments": assignments,
        "class_obj": class_obj
    })


@login_required
@user_passes_test(is_teacher)
def view_submissions(request, classroom_id=None, student_id=None):
    teacher_profile = get_object_or_404(TeacherProfile, teacher=request.user)
    submissions = Submission.objects.filter(assignment__teacher=teacher_profile)

    classroom = None  # Initialize classroom as None

    if classroom_id:
        classroom = get_object_or_404(Classroom, id=classroom_id)  # ✅ Fetch classroom object
        submissions = submissions.filter(assignment__joined_classes__id=classroom_id)

    if student_id:
        submissions = submissions.filter(student_id=student_id)

    context = {
        'submissions': submissions,
        'classroom': classroom,  # ✅ Pass classroom to template
        'classroom_id': classroom_id,
        'student_id': student_id,
    }

    return render(request, 'view_submissions.html', context)

@login_required
@user_passes_test(is_student)
def submit_assignment(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)

    # Get student's joined classes
    student_profile = request.user.student_profile
    student_classes = student_profile.joined_classes.all()

    # Ensure the assignment belongs to a class the student is part of
    if not assignment.joined_classes in student_classes:
        messages.error(request, "You are not enrolled in this class.")
        return redirect('student_dashboard')

    # Fetch assignments for pagination (optional)
    query = request.GET.get('q')
    assignments = Assignment.objects.filter(joined_classes__in=student_classes)

    if query:
        assignments = assignments.filter(title__icontains=query)

    paginator = Paginator(assignments, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    if request.method == 'POST':
        form = SubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            submission = form.save(commit=False)
            submission.student = student_profile  # ✅ Use StudentProfile
            submission.assignment = assignment
            submission.save()

            messages.success(request, 'Assignment submitted successfully!')
            return redirect('student_dashboard', class_id=assignment.joined_classes.id)
    else:
        form = SubmissionForm()

    return render(request, 'submit_assignment.html', {
        'form': form,
        'assignment': assignment,
        'assignments': assignments,
        'page_obj': page_obj,
        'query': query
    })


# Ensure NLTK stopwords are downloaded
nltk.download('stopwords')
nltk.download('punkt')

logger = logging.getLogger(__name__)
PLAGIARISM_THRESHOLD = 50 

def extract_text(submission):
    """Extracts text from uploaded file based on its type."""
    filename = submission.file.name.lower()
    try:
        submission.file.open()
        if filename.endswith('.pdf'):
            return extract_text_from_pdf(submission.file)
        elif filename.endswith('.txt'):
            return extract_text_from_txt(submission.file)
        elif filename.endswith('.docx'):
            return extract_text_from_docx(submission.file)
        else:
            logger.warning(f"Unsupported file type: {filename}")
            return ""
    except Exception as e:
        logger.error(f"❌ Error extracting text: {e}")
        return ""
    finally:
        submission.file.close()

def extract_text_from_pdf(pdf_file):
    """Extract text from a PDF file."""
    try:
        reader = PyPDF2.PdfReader(pdf_file)
        return " ".join([page.extract_text() for page in reader.pages if page.extract_text()])
    except Exception as e:
        logger.error(f"Error reading PDF: {e}")
        return ""

def extract_text_from_txt(txt_file):
    """Extract text from a TXT file."""
    try:
        return txt_file.read().decode('utf-8')
    except Exception as e:
        logger.error(f"Error reading TXT file: {e}")
        return ""

def extract_text_from_docx(docx_file):
    """Extract text from a DOCX file."""
    try:
        doc = docx.Document(docx_file)
        return " ".join([para.text for para in doc.paragraphs])
    except Exception as e:
        logger.error(f"Error reading DOCX file: {e}")
        return ""


def extract_keywords(text):
    """Extracts keywords from a given text, removing stopwords."""
    words = word_tokenize(text.lower())
    stop_words = set(stopwords.words('english'))
    return {word for word in words if word.isalnum() and word not in stop_words}

def calculate_keyword_match(student_text, teacher_keywords):
    """Calculate percentage of teacher's keywords present in student's submission."""
    teacher_words = set(teacher_keywords.lower().split())
    student_words = set(word_tokenize(student_text.lower()))
    matched_keywords = teacher_words.intersection(student_words)
    match_percentage = (len(matched_keywords) / len(teacher_words) * 100) if teacher_words else 0
    logger.info(f"🔍 Matched Keywords: {matched_keywords}")
    return match_percentage, matched_keywords

def calculate_grammar_score(text):
    """Evaluates grammar and spelling mistakes using TextBlob."""
    blob = TextBlob(text)
    num_errors = sum(1 for word in blob.words if word != word.correct()) + len(blob.correct().split()) - len(blob.words)
    
    # Assigning scores based on error count
    if num_errors == 0:
        return 20  # Perfect grammar
    elif num_errors <= 3:
        return 10  # Minor errors
    else:
        return 5  # Many errors

def calculate_submission_time_score(submission_time, deadline):
    """Assigns scores based on submission time."""
    return 20 if submission_time <= deadline else 10  # Deduct for late submissions

def check_student_to_student_plagiarism(submission, other_submissions, teacher_email):
    """Compares a student's submission with past student submissions to detect plagiarism."""
    submission_text = submission.submitted_text.strip()
    if not submission_text:
        return 0  # No text submitted

    # Find highest similarity percentage among past submissions
    highest_similarity = max(
        SequenceMatcher(None, submission_text, past.submitted_text.strip()).ratio() * 100
        for past in other_submissions.iterator()
    ) if other_submissions.exists() else 0

    # If similarity crosses threshold, notify teacher and student
    if highest_similarity >= PLAGIARISM_THRESHOLD:
        notify_teacher_and_student(submission, teacher_email, highest_similarity)

    return highest_similarity

def notify_teacher_and_student(submission, teacher_email, plagiarism_score):
    """Sends an alert email to the teacher and student about plagiarism detection."""
    message = (
        f"Hello,\n\nA submission from {submission.student.student.email} has a plagiarism score of {plagiarism_score:.2f}%.\n"
        f"Assignment: {submission.assignment.title}\n\nPlease review it.\n\nBest regards,\nSubmitTech"
    )
    send_mail(
        "⚠️ Plagiarism Alert: High Similarity Detected!",
        message,
        'noreply@submittech.com',
        [teacher_email, submission.student.student.email]
    )

def calculate_total_grade(submission):
    """Calculates the final grade based on keyword match, grammar, and submission time."""
    assignment = submission.assignment
    teacher_keywords = assignment.keywords if assignment.keywords else ""

    # Compute individual scores
    keyword_match_score, matched_keywords = calculate_keyword_match(submission.submitted_text, teacher_keywords)
    grammar_score = calculate_grammar_score(submission.submitted_text)
    submission_time_score = calculate_submission_time_score(submission.submitted_at, assignment.due_date)

    # Calculate total marks
    total_marks = keyword_match_score * 0.5 + grammar_score + submission_time_score  # Weighting
    submission.keyword_match = keyword_match_score
    submission.grammar_score = grammar_score
    submission.submission_time_score = submission_time_score
    submission.total_marks = round(total_marks, 2)
    submission.save()

    logger.info(f"✅ Submission {submission.id} graded: {submission.total_marks} marks.")
    return total_marks

def assign_grades():
    """Assigns grades and feedback based on the total marks."""
    grade_mapping = [
        (91, "A1", "Outstanding performance! Keep up the hard work."),
        (81, "A2", "Great job! A little more effort can take you to the top."),
        (71, "B1", "Impressive work! Keep focusing and improving."),
        (61, "B2", "You're on the right track! Practice more to excel."),
        (51, "C1", "Decent effort, but there's room for improvement."),
        (41, "C2", "You're making progress, but consistent practice is key."),
        (33, "D", "You need to put in more effort. Study hard."),
        (0, "E", "Serious attention needed! Seek help and study harder."),
    ]
    for submission in Submission.objects.all():
        # Calculate total marks
        submission.total_marks = (
            submission.keyword_match * 0.4 +  # 40% weightage
            submission.grammar_score * 0.3 +  # 30% weightage
            (20 if submission.plagiarism_score < 30 else 5)  # 30% weightage
        )

        # Assign grade based on total marks
        for threshold, grade, feedback in grade_mapping:
            if submission.total_marks >= threshold:
                submission.grade, submission.feedback = grade, feedback
                break
        
        submission.save()
    
    return "Grades and feedback assigned successfully."

def send_notifications():
    """Sends reminder emails to students who haven't submitted their assignments."""
    pending_students = CustomUser.objects.filter(role="student", submission__isnull=True).distinct()
    for student in pending_students:
        send_mail(
            '⏳ Assignment Reminder',
            '📌 You have pending assignments. Please submit before the deadline.',
            'admin@submittech.com',
            [student.email],
            fail_silently=True)


def progress_view(request, assignment_title):
    student_profile = get_object_or_404(StudentProfile, student=request.user)
    assignment = get_object_or_404(Assignment, title=assignment_title)

    # Get the student's marks for this assignment
    student_submission = Submission.objects.filter(student=student_profile, assignment=assignment).first()
    student_marks = student_submission.total_marks if student_submission else 0

    # Get all students' marks for this assignment (for comparison)
    all_submissions = Submission.objects.filter(assignment=assignment).select_related('student')

    student_marks_list = [
        {
            "id": sub.student.student.id,  # ✅ Corrected to access the User's ID
            "name": sub.student.student.first_name,
            "marks": sub.total_marks
        }
        for sub in all_submissions if sub.student != student_profile  # Exclude self
    ]

    context = {
        "assignment_title": assignment.title,
        "student_marks": student_marks,
        "student_name": student_profile.name,
        "student_marks_list": student_marks_list,  # Classmates' data
    }
    return render(request, "progress_chart.html", context)

@login_required
def grade_assignment(request, assignment_id):
    """Grades an assignment manually from the teacher panel."""
    assignment = get_object_or_404(Assignment, id=assignment_id)
    if request.method == "POST":
        grade = request.POST.get("grade")
        feedback = request.POST.get("feedback")
        submission = Submission.objects.filter(assignment=assignment).first()
        if submission:
            submission.grade, submission.feedback = grade, feedback
            submission.save()
            messages.success(request, "✅ Assignment graded successfully!")
        else:
            messages.error(request, "⚠️ No submission found for this assignment.")
        return redirect('teacher_dashboard')
    return render(request, "grade_assignment.html", {"assignment": assignment})


@login_required
def query1to1_view(request, teacher_id, student_id):
    teacher = get_object_or_404(TeacherProfile, teacher__id=teacher_id)
    student = get_object_or_404(StudentProfile, student__id=student_id)

    context = {
        'teacher': teacher,
        'student': student,
        'teacher_id': teacher_id,
        'student_id': student_id,
    }
    return render(request, 'query1to1.html', context)  # ✅ Ensure correct template path

def queryclassroom_view(request, class_id):
    classroom = get_object_or_404(Classroom, id=class_id)
    return render(request, "queryclassroom.html", {"classroom": classroom})