from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.core.mail import send_mail
from django.http import JsonResponse
from django.db.models import Q
from django.core.paginator import Paginator
from .models import (CustomUser, Classroom, Assignment, Submission,Performance, Query, StudentProfile, TeacherProfile)
from .forms import (UserRegistrationForm, AssignmentForm, SubmissionForm,LoginForm, QueryForm, QueryResponseForm, ClassForm)
from PyPDF2 import PdfReader
from docx import Document
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
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
            assigned_classes = student_profile.assigned_classes.all()

            if assigned_classes.exists():
                first_class = assigned_classes.first()  # Grab the first class
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
    return 'default_folder/default_student.png'  # path inside media folder

def teacher_default_profile():
    return 'default_folder/default_teacher.png'  # path inside media folder

# ✅ Teacher Profile View
@login_required
@user_passes_test(is_teacher)
def teacher_profile(request):
    teacher_profile = get_object_or_404(TeacherProfile, teacher=request.user)

    # ✅ Fetch all classrooms assigned to this teacher
    classes = Classroom.objects.filter(teacher=teacher_profile)

    query = request.GET.get('q')

    # ✅ FIXED HERE: Filter students using the correct field
    students = StudentProfile.objects.filter(assigned_classes__in=classes).distinct()

    if query:
        students = students.filter(
            Q(student__username__icontains=query) |
            Q(student__first_name__icontains=query) |
            Q(student__last_name__icontains=query)
        )

    paginator = Paginator(students, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    if not classes.exists():
        messages.info(request, "You haven't created any classrooms yet.")

    return render(request, 'teacher_profile.html', {
        'teacher_profile': teacher_profile,
        'classes': classes,
        'page_obj': page_obj,
        'query': query,
    })





# ✅ Student Profile View
@login_required
@user_passes_test(is_student)
def student_profile(request):
    student_user = request.user

    # Fetch or create the StudentProfile for this user
    student_profile, created = StudentProfile.objects.get_or_create(student=student_user)

    if created:
        messages.info(request, "Welcome! Please join a class to get started.")

    # Get all classrooms this student has joined
    assigned_classes = student_profile.assigned_classes.all()

    if not assigned_classes.exists():
        messages.warning(request, "You are not enrolled in any classes yet.")

    # Fetch assignments related to the classes (optional filter for active assignments)
    assignments = Assignment.objects.filter(assigned_class__in=assigned_classes)

    # Get distinct teachers for the assigned classes
    teachers = TeacherProfile.objects.filter(classrooms__in=assigned_classes).distinct()

    # Get or create the performance record for the student
    performance, _ = Performance.objects.get_or_create(student=student_profile)

    # Render the student profile page
    return render(request, 'student_profile.html', {
        'student_profile': student_profile,
        'assigned_classes': assigned_classes,
        'assignments': assignments,
        'teachers': teachers,
        'performance': performance,
    })    


@login_required
@user_passes_test(is_teacher)
def teacher_dashboard(request, class_id):
    teacher_profile, created = TeacherProfile.objects.get_or_create(teacher=request.user)

    # ✅ All classes by this teacher
    classes = Classroom.objects.filter(teacher=teacher_profile)

    try:
        classroom = Classroom.objects.get(id=class_id, teacher=teacher_profile)
    except Classroom.DoesNotExist:
        messages.error(request, "Classroom not found.")
        return redirect('teacher_dashboard', class_id=classes.first().id if classes.exists() else None)

    # ✅ Assignments and submissions for this classroom
    assignments = Assignment.objects.filter(teacher=teacher_profile, assigned_class=classroom)
    submissions = Submission.objects.filter(assignment__teacher=teacher_profile, assignment__assigned_class=classroom)

    query = request.GET.get('q')

    # ✅ FIX: Use assigned_classes here
    students = StudentProfile.objects.filter(assigned_classes__in=classes).distinct()

    if query:
        students = students.filter(
            Q(student__username__icontains=query) |
            Q(student__first_name__icontains=query)
        )

    paginator = Paginator(students, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # ✅ FIX: Use assigned_classes for classroom filtering
    queries = Query.objects.filter(student__assigned_classes=classroom).filter(answer__isnull=False).exclude(answer="")

    top_students = Performance.objects.filter(student__assigned_classes=classroom).order_by('-average_score')[:3]

    return render(request, 'teacher_dashboard.html', {
        'classes': classes,
        'assignments': assignments,
        'submissions': submissions,
        'page_obj': page_obj,
        'queries': queries,
        'top_students': top_students,
        'current_classroom': classroom
    })


@login_required
@user_passes_test(is_student)
def student_dashboard(request, class_id=None):
    student = request.user
    student_profile = get_object_or_404(StudentProfile, student=student)

    if class_id:
        classroom = get_object_or_404(Classroom, id=class_id)
    else:
        # This assumes student belongs to ONE classroom; otherwise adjust logic.
        classroom = student_profile.classrooms.first()

    assignments = Assignment.objects.filter(assigned_class=classroom)
    submissions = Submission.objects.filter(student=student)

    # Searching for students (other students in same class)
    query = request.GET.get('q')

    # Get all students in the same classes (excluding self if needed)
    all_students = classroom.students.all()

    if query:
        all_students = all_students.filter(
            Q(student__username__icontains=query) |
            Q(student__first_name__icontains=query)
        )

    # Paginate the list of students
    paginator = Paginator(all_students, 10)  # Show 10 students per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'student_dashboard.html', {
        'assignments': assignments,
        'submissions': submissions,
        'classroom': classroom,
        'page_obj': page_obj,
        'query': query
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

def teacher_list(request):
    teachers = CustomUser.objects.filter(role="teacher")
    return render(request, "teacher_list.html", {"teachers": teachers})

@login_required
@user_passes_test(is_admin)
def add_teacher(request):
    if request.method == "POST":
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            teacher = form.save(commit=False)
            teacher.role = 'teacher'
            teacher.save()

            # Create a TeacherProfile
            TeacherProfile.objects.create(teacher=teacher)

            messages.success(request, "Teacher added successfully!")
            return redirect('admin_dashboard')

    else:
        form = UserRegistrationForm()

    return render(request, 'add_teacher.html', {'form': form})


def get_teacher_classes(request):
    reference_id = request.GET.get('reference_id')

    if not reference_id:
        return JsonResponse({'error': 'No reference ID provided'}, status=400)

    try:
        teacher = get_object_or_404(teacher, reference_id=reference_id)
        classes = Classroom.objects.filter(teachers=teacher)

        class_list = [
            {'id': cls.id, 'name': cls.name}
            for cls in classes
        ]

        return JsonResponse({'classes': class_list})
    
    except teacher.DoesNotExist:
        return JsonResponse({'classes': []})
    

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
    
    query = request.GET.get('q')
    given_assignments = Assignment.objects.filter(teacher=teacher_profile)

    if query:
        given_assignments = given_assignments.filter(
            Q(title__icontains=query) |
            Q(assigned_class__classname__icontains=query)
        )

    paginator = Paginator(given_assignments, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'give_assignment.html', {
        'page_obj': page_obj,
        'query': query,})

@login_required
def given_assignment(request, class_id):
    class_obj = get_object_or_404(Classroom, id=class_id)
    assignments = Assignment.objects.filter(assigned_class=class_obj)

    return render(request, "given_assignment.html", {
        "assignments": assignments,
        "class_obj": class_obj
    })


@login_required
@user_passes_test(is_teacher)
def view_submissions(request):
    submissions = Submission.objects.filter(assignment__teacher=request.user)
    return render(request, 'view_submissions.html', {'submissions': submissions})

@login_required
@user_passes_test(is_student)
def submit_assignment(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)
    query = request.GET.get('q')

    # Get assignments assigned to the student’s classes
    if query:
        assignment = assignment.filter(
            Q(title__icontains=query)
        )

    paginator = Paginator(assignment, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

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

    return render(request, 'submit_assignment.html', {
        'form': form,
        'assignment': assignment, 
        'page_obj': page_obj,
        'query': query})



def start_plagiarism_check(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)
    submissions = Submission.objects.filter(assignment=assignment)

    keywords = assignment.keywords.split(",")  # Assuming keywords are comma-separated
    teacher_email = assignment.teacher.teacher.email

    for submission in submissions:
        # Exclude current submission from others when checking plagiarism
        other_subs = submissions.exclude(id=submission.id)
        
        results = check_plagiarism_and_grade(submission, other_subs, keywords, teacher_email)
        
        print(f"Checked submission {submission.student.student.email}: {results}")

    messages.success(request, "Plagiarism checks complete!")
    return redirect('submitted_assignments', assignment_id=assignment.id)


PLAGIARISM_THRESHOLD = 40  # Student-to-student similarity threshold

def extract_text(file_field):
    # Detect file type and call appropriate function
    filename = file_field.name
    if filename.endswith('.pdf'):
        return extract_text_from_pdf(file_field)
    elif filename.endswith('.txt'):
        return extract_text_from_txt(file_field)
    elif filename.endswith('.docx'):
        return extract_text_from_docx(file_field)
    else:
        print("Unsupported file type!")
        return ""

def extract_text_from_pdf(file_field):
    try:
        file_field.open()
        reader = PdfReader(file_field)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text
        file_field.close()
        return text
    except Exception as e:
        print(f"PDF Extraction error: {str(e)}")
        return ""

def extract_text_from_txt(file_field):
    try:
        file_field.open('r')  # Open file in text mode
        content = file_field.read()
        file_field.close()
        return content
    except Exception as e:
        print(f"Error reading TXT file: {e}")
        return ""


def extract_text_from_docx(file_field):
    try:
        file_field.open('rb')  # Open file in binary mode
        document = Document(file_field)
        text = "\n".join([paragraph.text for paragraph in document.paragraphs])
        file_field.close()
        return text
    except Exception as e:
        print(f"Error reading DOCX file: {e}")
        return ""


def check_keyword_similarity(submission_text, keywords):
    keyword_matches = {}
    text_lower = submission_text.lower()
    for keyword in keywords:
        clean_keyword = keyword.strip().lower()
        count = text_lower.count(clean_keyword)
        keyword_matches[clean_keyword] = count
    return keyword_matches


def check_student_to_student_plagiarism(current_submission, other_submissions, teacher_email):
    current_text = extract_text_from_pdf(current_submission.file)

    other_texts = []
    for sub in other_submissions:
        other_text = extract_text_from_pdf(sub.file)
        if other_text.strip():
            other_texts.append(other_text)

    if not other_texts:
        current_submission.plagiarism_score = 0.0
        current_submission.save()
        return 0.0

    vectorizer = TfidfVectorizer().fit_transform([current_text] + other_texts)
    vectors = vectorizer.toarray()
    
    similarities = cosine_similarity([vectors[0]], vectors[1:])[0]
    highest_similarity = max(similarities) * 100 if similarities.size > 0 else 0
    
    current_submission.plagiarism_score = round(highest_similarity, 2)
    current_submission.save()

    if highest_similarity > PLAGIARISM_THRESHOLD and not current_submission.notified:
        notify_teacher_and_student(current_submission, teacher_email)
        current_submission.notified = True
        current_submission.save()

    return highest_similarity


def notify_teacher_and_student(submission, teacher_email):
    subject = "⚠️ Plagiarism Alert: High Similarity Detected!"
    message = (
        f"Hello,\n\n"
        f"A submission from {submission.student.student.email} has a plagiarism score "
        f"above {PLAGIARISM_THRESHOLD}%.\n"
        f"Assignment: {submission.assignment.title}\n"
        f"Plagiarism Score: {submission.plagiarism_score}%\n\n"
        f"Please review.\n\n"
        f"Regards,\nSubmitTech"
    )
    
    send_mail(subject, message, 'noreply@submittech.com', [teacher_email])
    send_mail(subject, message, 'noreply@submittech.com', [submission.student.student.email])

    print(f"Notifications sent to {teacher_email} and {submission.student.student.email}")
    print("Notification sent to teacher and student due to high similarity.")

def check_plagiarism_and_grade(submission, other_submissions, keywords, teacher_email):
    
    results = {}

    submission_text = extract_text_from_pdf(submission.file)

    keyword_match = check_keyword_similarity(submission_text, keywords)
    results['keyword_match'] = keyword_match

    plagiarism_score = check_student_to_student_plagiarism(submission, other_submissions, teacher_email)
    results['plagiarism_score'] = plagiarism_score

    return results


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
@user_passes_test(is_student)
def student_progress(request):
    student = request.user
    performance = Performance.objects.filter(student=student).first()

    return render(request, 'student_progress.html', {'performance': performance})


