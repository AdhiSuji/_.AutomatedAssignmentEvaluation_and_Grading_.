from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout, get_user_model
from .models import CustomUser, Classroom, Assignment, Submission, Performance, Query,  StudentProfile, TeacherProfile 
from .forms import UserRegistrationForm, AssignmentForm, SubmissionForm, LoginForm, QueryForm, QueryResponseForm, ClassForm
from django.core.mail import send_mail
from django.http import JsonResponse


# Home View
def home_view(request):
    return render(request, 'home.html')


def user_login(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        # Authenticate using email
        user = authenticate(request, email=email, password=password)

        if user is None:
            messages.error(request, "Invalid email or password! Please try again.")
            return redirect("login")

        # Log in the user
        login(request, user)
        messages.success(request, "Login successful!")

        if user.role == "student":
            student_profile, created = StudentProfile.objects.get_or_create(student=user)

            # ✅ Ensure student has an assigned class before redirecting
            if student_profile.assigned_class:
                return redirect("student_dashboard", class_id=student_profile.assigned_class.id)
            else:
                messages.error(request, "No class assigned! Contact your teacher.")
                return redirect("student_profile")

        elif user.role == "teacher":
            TeacherProfile.objects.get_or_create(teacher=user)
            
            # ✅ Redirect to Teacher Profile instead of hardcoded dashboard
            return redirect("teacher_profile")

        else:
            messages.error(request, "Invalid role! Contact admin.")
            return redirect("login")

    return render(request, "login.html")

def user_logout(request):
    logout(request)
    return redirect('login') 


User = get_user_model()  # Use the correct user model

def register(request):
    if request.method == "POST":
        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        email = request.POST.get("email")
        role = request.POST.get("role")
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")

        # Ensure passwords match
        if password != confirm_password:
            messages.error(request, "Passwords do not match!")
            return render(request, "register.html", {"form_data": request.POST})

        # Check if email already exists
        if User.objects.filter(email=email).exists():
            messages.error(request, "Email is already registered!")
            return render(request, "register.html", {"form_data": request.POST})

        # Create user using CustomUser model (assuming email is the username)
        user = User.objects.create_user(
            username=email,  #
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=password,
            role=role  
        )

        # Log in the user immediately after registration
        login(request, user)

        # Redirect based on role
        if role == "student":
            StudentProfile.objects.create(student=user)
            return redirect("student_profile") 
        else:
            TeacherProfile.objects.create(teacher=user)
            return redirect("teacher_profile") 
    return render(request, "register.html")


# Student Profile
@login_required
def student_profile(request):
    student = request.user
    student_profile = get_object_or_404(StudentProfile, student=student)
    assignments = Assignment.objects.filter(assigned_class=student_profile.assigned_class)
    performance, created = Performance.objects.get_or_create(student=student)
    
    return render(request, 'student_profile.html', {
        'assignments': assignments,
        'performance': performance,
        'class_id': student_profile.assigned_class.id if student_profile.assigned_class else None,
    })

def get_teacher_classes(request):
    reference_id = request.GET.get("reference_id", None)
    
    if reference_id:
        try:
            teacher = User.objects.get(reference_id=reference_id, role="teacher")
            classes = Classroom.objects.filter(teacher=teacher).values("id", "name")
            return JsonResponse({"classes": list(classes)}, safe=False)
        except User.DoesNotExist:
            return JsonResponse({"error": "Invalid Teacher Reference ID!"}, status=400)
    
    return JsonResponse({"error": "No reference ID provided!"}, status=400)

# Teacher Profile
@login_required
def teacher_profile(request):
    teacher = request.user
    classes = Classroom.objects.filter(teacher=teacher)
    return render(request, 'teacher_profile.html', {'classes': classes})

@login_required
def create_class(request):
    if request.user.role != 'teacher':  
        return redirect('dashboard')  # Only teachers can create a class

    if request.method == "POST":
        form = ClassForm(request.POST)
        if form.is_valid():
            class_instance = form.save(commit=False)
            class_instance.teacher = request.user  # Assign the logged-in teacher
            class_instance.save()
            return redirect('teacher_profile')  # Redirect after creation
    else:
        form = ClassForm()

    return render(request, 'create_class.html', {'form': form})

def delete_class(request, class_id):
    class_obj = get_object_or_404(Classroom, id=class_id, teacher=request.user)

    if request.method == "POST":
        class_obj.delete()
        messages.success(request, "Class deleted successfully!")

    return redirect("teacher_profile")


@login_required
def enroll_student(request):
    if request.user.role != 'student':  
        return redirect('dashboard')  # Only students can enroll

    if request.method == "POST":
        reference_id = request.POST.get("reference_id")
        class_id = request.POST.get("selected_class")

        try:
            teacher = CustomUser.objects.get(reference_id=reference_id, role='teacher')
            selected_class = Classroom.objects.get(id=class_id, teacher=teacher)
            student_profile = get_object_or_404(StudentProfile, student=request.user)
            student_profile.assigned_class = selected_class
            student_profile.save()

            messages.success(request, "You have successfully enrolled in the class.")
            return redirect('student_dashboard')
        except CustomUser.DoesNotExist:
            messages.error(request, "Invalid Teacher Reference ID.")
        except Classroom.DoesNotExist:
            messages.error(request, "Invalid Class Selection.")

    classes = Classroom.objects.all()
    return render(request, 'enroll_student.html', {'classes': classes})


@login_required
def add_teacher(request):
    if request.user.role != 'admin':
        student = request.user  # Assuming user is a student
        if student.assigned_class:
            return redirect('student_dashboard', class_id=student.assigned_class.id)
        else:
            return redirect('student_profile')  # Safe fallback

    if request.method == "POST":
        form =UserRegistrationForm(request.POST)
        if form.is_valid():
            teacher = form.save(commit=False)
            teacher.role = 'teacher'  # Ensure role is set to Teacher
            teacher.save()
            return redirect('admin_dashboard')  # Redirect after successful registration
    else:
        form = UserRegistrationForm()

    return render(request, 'add_teacher.html', {'form': form})

@login_required
def give_assignment(request):
    if request.method == "POST":
        form = AssignmentForm(request.POST)
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.teacher = request.user  # Assign the current logged-in teacher
            assignment.save()
            return redirect('teacher_dashboard')  # Redirect to teacher dashboard after creation
    else:
        form = AssignmentForm()
    
    return render(request, 'give_assignment.html', {'form': form})


def given_assignment(request, class_id):
    class_obj = get_object_or_404(Classroom, id=class_id)
    assignments = Assignment.objects.filter(class_assigned=class_obj)  # Adjust field name if different

    return render(request, "given_assignment.html", {"assignments": assignments, "class_obj": class_obj})

@login_required
def view_submissions(request):
    if request.user.role != 'teacher':  # Ensure only teachers can view submissions
        return redirect('dashboard')

    submissions = Submission.objects.filter(assignment__teacher=request.user)  # Get submissions for the logged-in teacher's assignments
    return render(request, 'view_submissions.html', {'submissions': submissions})

# Assignment Submission
@login_required
def submit_assignment(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)
    if request.method == 'POST':
        form = SubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            submission = form.save(commit=False)
            submission.student = request.user
            submission.assignment = assignment
            submission.save()
            messages.success(request, 'Assignment submitted successfully!')
            return redirect('student_profile')
    else:
        form = SubmissionForm()
    return render(request, 'submit_assignment.html', {'form': form})

# Assignment Grading
@login_required
def grade_assignment(request, submission_id):
    submission = get_object_or_404(Submission, id=submission_id)
    if request.method == 'POST':
        submission.grade = request.POST.get('grade')
        submission.feedback = request.POST.get('feedback')
        submission.graded = True
        submission.save()
        submission.student.performance.update_performance()
        messages.success(request, 'Assignment graded successfully!')
        return redirect('teacher_profile')
    return render(request, 'grade_assignment.html', {'submission': submission})

@login_required
def student_performance(request):
    if request.user.role != 'student':  # Ensure only students can access this page
        return redirect('dashboard')

    try:
        performance = Performance.objects.get(student=request.user)
    except Performance.DoesNotExist:
        performance = None  # If no performance record exists, set it to None

    return render(request, 'student_performance.html', {'performance': performance})

@login_required
def student_progress(request, student_id):
    student = get_object_or_404(CustomUser, id=student_id, role='student')

    try:
        performance = Performance.objects.get(student=student)
    except Performance.DoesNotExist:
        performance = None  # Handle case where no performance data exists

    return render(request, 'student_progress.html', {'student': student, 'performance': performance})

# Notification for Pending Submissions
def send_notifications():
    pending_students = CustomUser.objects.filter(role="student", submission__graded=False).distinct()
    for student in pending_students:
        send_mail(
            'Assignment Reminder',
            'You have pending assignments. Please submit before the deadline.',
            'admin@example.com',
            [student.email],
            fail_silently=True,
        )

@login_required
def ask_query(request):
    if request.method == "POST":
        form = QueryForm(request.POST)
        if form.is_valid():
            query = form.save(commit=False)
            query.student = request.user  # Assign the logged-in student
            query.save()
            return redirect('student_dashboard')  # Redirect to student dashboard
    else:
        form = QueryForm()
    
    return render(request, 'ask_query.html', {'form': form})

@login_required
def respond_query(request, query_id):
    if request.user.role != 'teacher':
        return redirect('dashboard')  # Only teachers can respond

    query = get_object_or_404(Query, id=query_id)

    if request.method == "POST":
        form = QueryResponseForm(request.POST, instance=query)
        if form.is_valid():
            query.response = form.cleaned_data['response']
            query.save()
            return redirect('teacher_dashboard')  # Redirect teacher after response
    else:
        form = QueryResponseForm(instance=query)

    return render(request, 'respond_query.html', {'form': form, 'query': query})


def teacher_dashboard(request):
    return render(request, "teacher_dashboard.html")

@login_required
def student_dashboard(request, class_id):
    student_profile = get_object_or_404(StudentProfile, student=request.user)

    if student_profile.assigned_class is None:
        messages.error(request, "You are not enrolled in any class yet!")
        return redirect("student_profile")  

    # Fetch assignments related to the class
    assignments = Assignment.objects.filter(assigned_class_id=class_id)
    
    return render(request, "student_dashboard.html", {"assignments": assignments})
