from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.core.mail import send_mail
from django.http import JsonResponse

from .models import (CustomUser, Classroom, Assignment, Submission,Performance, Query, StudentProfile, TeacherProfile)
from .forms import (UserRegistrationForm, AssignmentForm, SubmissionForm,LoginForm, QueryForm, QueryResponseForm, ClassForm)

User = get_user_model()

#UTILS             

def is_admin(user):
    return user.is_authenticated and user.role == 'admin'

def is_teacher(user):
    return user.is_authenticated and user.role == 'teacher'

def is_student(user):
    return user.is_authenticated and user.role == 'student'


 #VIEWS             

def home_view(request):
    return render(request, 'home.html')


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

        if user.role == "student":
            student_profile, _ = StudentProfile.objects.get_or_create(student=user)
            if student_profile.assigned_class:
                return redirect("student_dashboard", class_id=student_profile.assigned_class.id)
            else:
                messages.warning(request, "No class assigned! Contact your teacher.")
                return redirect("student_profile")

        elif user.role == "teacher":
            return redirect("teacher_dashboard")

        elif user.role == "admin":
            return redirect("admin_dashboard")

        messages.error(request, "Invalid role! Contact admin.")
        return redirect("login")

    return render(request, "login.html")


def user_logout(request):
    logout(request)
    return redirect('login')


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

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email is already registered!")
            return render(request, "register.html", {"form_data": request.POST})

        user = User.objects.create_user(
            username=email,
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=password,
            role=role
        )

        login(request, user)

        if role == "student":
            StudentProfile.objects.create(student=user)
            return redirect("student_profile")

        elif role == "teacher":
            TeacherProfile.objects.create(teacher=user)
            return redirect("teacher_profile")

    return render(request, "register.html")


#STUDENT VIEWS           

@login_required
@user_passes_test(is_student)
def student_profile(request):
    student = request.user
    student_profile = get_object_or_404(StudentProfile, student=student)
    assigned_class = student_profile.assigned_class

    assignments = Assignment.objects.filter(assigned_class=assigned_class)
    teachers = assigned_class.teacher.all() if assigned_class else []

    performance, _ = Performance.objects.get_or_create(student=student)

    return render(request, 'student_profile.html', {
        'assignments': assignments,
        'performance': performance,
        'class_id': assigned_class.id if assigned_class else None,
        'teachers': teachers
    })


@login_required
@user_passes_test(is_student)
def enroll_student(request):
    if request.method == "POST":
        reference_id = request.POST.get("reference_id")
        class_id = request.POST.get("selected_class")

        try:
            teacher = CustomUser.objects.get(reference_id=reference_id, role='teacher')
            selected_class = Classroom.objects.get(id=class_id, teacher=teacher)

            student_profile = get_object_or_404(StudentProfile, student=request.user)
            student_profile.assigned_class = selected_class
            student_profile.save()

            messages.success(request, "Successfully enrolled in class.")
            return redirect('student_dashboard', class_id=selected_class.id)

        except CustomUser.DoesNotExist:
            messages.error(request, "Invalid Teacher Reference ID.")
        except Classroom.DoesNotExist:
            messages.error(request, "Invalid Class Selection.")

    classes = Classroom.objects.all()
    return render(request, 'enroll_student.html', {'classes': classes})


@login_required
@user_passes_test(is_student)
def student_dashboard(request, class_id=None):
    student = request.user
    student_profile = get_object_or_404(StudentProfile, student=student)

    if class_id:
        classroom = get_object_or_404(Classroom, id=class_id)
    else:
        classroom = student_profile.assigned_class

    assignments = Assignment.objects.filter(assigned_class=classroom)
    submissions = Submission.objects.filter(student=student)

    progress = Performance.objects.filter(student=student).first()

    return render(request, 'student_dashboard.html', {
        'assignments': assignments,
        'submissions': submissions,
        'progress': progress,
        'classroom': classroom
    })


@login_required
@user_passes_test(is_student)
def student_progress(request):
    student = request.user
    performance = Performance.objects.filter(student=student).first()

    return render(request, 'student_progress.html', {'performance': performance})


@login_required
@user_passes_test(is_student)
def ask_query(request):
    if request.method == "POST":
        form = QueryForm(request.POST)
        if form.is_valid():
            query = form.save(commit=False)
            query.student = request.user
            query.save()
            messages.success(request, "Query sent successfully!")
            return redirect('student_dashboard', class_id=request.user.studentprofile.assigned_class.id)
    else:
        form = QueryForm()

    return render(request, 'ask_query.html', {'form': form})


#TEACHER VIEWS           

@login_required
@user_passes_test(is_teacher)
def teacher_profile(request):
    teacher = request.user
    classes = Classroom.objects.filter(teacher=teacher)
    return render(request, 'teacher_profile.html', {'classes': classes})


@login_required
@user_passes_test(is_teacher)
def teacher_dashboard(request):
    teacher = request.user
    classes = Classroom.objects.filter(teacher=teacher)
    assignments = Assignment.objects.filter(teacher=teacher)
    submissions = Submission.objects.filter(assignment__teacher=teacher)
    queries = Query.objects.filter(student__studentprofile__assigned_class__teacher=teacher, responded=False)

    top_students = Performance.objects.filter(student__studentprofile__assigned_class__teacher=teacher).order_by('-average_grade')[:3]

    return render(request, 'teacher_dashboard.html', {
        'classes': classes,
        'assignments': assignments,
        'submissions': submissions,
        'queries': queries,
        'top_students': top_students
    })


@login_required
@user_passes_test(is_teacher)
def create_class(request):
    if request.method == "POST":
        form = ClassForm(request.POST)
        if form.is_valid():
            new_class = form.save(commit=False)
            new_class.teacher = request.user
            new_class.save()
            messages.success(request, "Class created successfully!")
            return redirect('teacher_dashboard')

    else:
        form = ClassForm()

    return render(request, 'create_class.html', {'form': form})


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
def give_assignment(request):
    if request.method == "POST":
        form = AssignmentForm(request.POST)
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.teacher = request.user
            assignment.save()
            messages.success(request, "Assignment given successfully!")
            return redirect('teacher_dashboard')

    else:
        form = AssignmentForm()

    return render(request, 'give_assignment.html', {'form': form})


@login_required
@user_passes_test(is_teacher)
def view_submissions(request):
    submissions = Submission.objects.filter(assignment__teacher=request.user)
    return render(request, 'view_submissions.html', {'submissions': submissions})


@login_required
@user_passes_test(is_teacher)
def grade_assignment(request, submission_id):
    submission = get_object_or_404(Submission, id=submission_id)

    if request.method == 'POST':
        grade = request.POST.get('grade')
        feedback = request.POST.get('feedback')

        submission.grade = grade
        submission.feedback = feedback
        submission.graded = True
        submission.save()

        submission.student.performance.update_performance()

        messages.success(request, 'Assignment graded successfully!')
        return redirect('teacher_dashboard')

    return render(request, 'grade_assignment.html', {'submission': submission})


@login_required
@user_passes_test(is_teacher)
def respond_query(request, query_id):
    query = get_object_or_404(Query, id=query_id)

    if request.method == "POST":
        form = QueryResponseForm(request.POST, instance=query)
        if form.is_valid():
            response = form.save(commit=False)
            response.responded = True
            response.save()
            messages.success(request, "Query responded successfully!")
            return redirect('teacher_dashboard')

    else:
        form = QueryResponseForm(instance=query)

    return render(request, 'respond_query.html', {'form': form, 'query': query})


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
@user_passes_test(is_admin)
def add_teacher(request):
    if request.method == "POST":
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            teacher = form.save(commit=False)
            teacher.role = 'teacher'
            teacher.save()
            TeacherProfile.objects.create(teacher=teacher)
            messages.success(request, "Teacher added successfully!")
            return redirect('admin_dashboard')

    else:
        form = UserRegistrationForm()

    return render(request, 'add_teacher.html', {'form': form})


#ASSIGNMENT HANDLING        

@login_required
@user_passes_test(is_student)
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
            return redirect('student_dashboard', class_id=request.user.studentprofile.assigned_class.id)

    else:
        form = SubmissionForm()

    return render(request, 'submit_assignment.html', {'form': form, 'assignment': assignment})


@login_required
def given_assignment(request, class_id):
    class_obj = get_object_or_404(Classroom, id=class_id)
    assignments = Assignment.objects.filter(assigned_class=class_obj)

    return render(request, "given_assignment.html", {
        "assignments": assignments,
        "class_obj": class_obj
    })


#NOTIFICATIONS            

def send_notifications():
    pending_students = CustomUser.objects.filter(
        role="student",
        submission__graded=False
    ).distinct()

    for student in pending_students:
        send_mail(
            'Assignment Reminder',
            'You have pending assignments. Please submit before the deadline.',
            'admin@example.com',
            [student.email],
            fail_silently=True
        )


#SUPPORTING VIEWS         

def teacher_list(request):
    teachers = CustomUser.objects.filter(role="teacher")
    return render(request, "teacher_list.html", {"teachers": teachers})


def get_teacher_classes(request):
    reference_id = request.GET.get("reference_id")

    if reference_id:
        try:
            teacher = CustomUser.objects.get(reference_id=reference_id, role="teacher")
            classes = Classroom.objects.filter(teacher=teacher).values("id", "name")
            return JsonResponse({"classes": list(classes)})

        except CustomUser.DoesNotExist:
            return JsonResponse({"error": "Invalid Teacher Reference ID!"}, status=400)

    return JsonResponse({"error": "No reference ID provided!"}, status=400)

