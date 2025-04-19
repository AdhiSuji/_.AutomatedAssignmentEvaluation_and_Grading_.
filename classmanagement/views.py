#View Handling & Auth
from django.shortcuts import render, redirect, get_object_or_404  
from django.contrib.auth.decorators import login_required, user_passes_test  
from django.contrib.auth import authenticate, login, logout, get_user_model  
from django.contrib import messages  
from .evaluate_submission import evaluate_submission,extract_text_from_pdf, extract_images_from_pdf


#Email
from django.core.mail import send_mail  
#Logging & JSON
import json
#Database & Time  
from django.utils.timezone import now  
from django.utils import timezone  
#Data processing
from collections import defaultdict, Counter 
#HTTP & Queries 
from django.http import JsonResponse  
from django.db.models import Q  
#Pagination
from django.core.paginator import Paginator  
#MOdels & Forms
from .models import ( CustomUser, Classroom, Assignment, Submission, Enrollment, Performance, StudentProfile, TeacherProfile, PrivateMessage, QueryMessage , Notification )  
from .forms import ( AssignmentForm, SubmissionForm, ClassForm, StudentProfileForm, TeacherProfileForm  )  
#Notifications 
from .notifications import notify_teacher_and_student  
from collections import Counter


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

    # Fetch all classrooms assigned to this teacher
    created_classes = Classroom.objects.filter(teacher=teacher_profile)

    # Initialize search query
    query = request.GET.get('q')

    # Fetch all students assigned to this teacher's classes
    students = StudentProfile.objects.filter(joined_classes__in=created_classes).distinct()

    if query:
        students = students.filter(
            Q(name__icontains=query) |
            Q(student__email__icontains=query)
        )

    # Paginate the students list
    paginator = Paginator(students, 10)  # Show 10 students per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # If no classrooms are created, show a message
    if not created_classes.exists():
        messages.info(request, "You haven't created any classrooms yet.")

    # Prepare the form for editing teacher profile (if needed)
    form = TeacherProfileForm(instance=teacher_profile)

    return render(request, 'teacher_profile.html', {
        'teacher_profile': teacher_profile,
        'created_classes': created_classes,
        'page_obj': page_obj,
        'query': query,
        'form': form,  # Ensure form is passed if editing is required
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
def teacher_dashboard(request, class_id):
    """Teacher's Dashboard: Displays student performance for a selected class."""
    
    teacher = get_object_or_404(TeacherProfile, teacher=request.user)

    # ✅ Get all classes of this teacher
    classes = Classroom.objects.filter(teacher=teacher)

    # ✅ Fetch the currently selected class
    current_class = get_object_or_404(Classroom, id=class_id, teacher=teacher)

    # ✅ Fetch students in this class
    students = StudentProfile.objects.filter(joined_classes=current_class)

    # ✅ Fetch assignments only from this class
    assignments = Assignment.objects.filter(joined_classes=current_class)

    # ✅ Fetch submissions only from this class
    submissions = Submission.objects.filter(assignment__joined_classes=current_class)

    performance_data = []
    student_performance_list = []
    class_avg_performance = {}

    for student in students:
        student_performance = {
            "student": student,
            "assignments": [],
            "total_score": 0
        }

        # ✅ Fetch submissions only for this student in this class
        student_submissions = submissions.filter(student=student)
        for submission in student_submissions:
            student_performance["assignments"].append({
                "assignment": submission.assignment,
                "marks": submission.total_marks,
                "is_late": submission.is_late,
                "plagiarism_score": submission.plagiarism_score,
                "grade": submission.grade,
                "feedback": submission.feedback,
                "text_similarity_score": submission.text_similarity_score,
                "image_similarity_score": submission.image_similarity_score,
            })

            student_performance_list.append({
                "student": student.student.username,  # Use full name if needed
                "assignment": submission.assignment.title,
                "marks": submission.total_marks
            })

            student_performance["total_score"] += submission.total_marks

            # ✅ Compute class average per assignment
            if submission.assignment.title not in class_avg_performance:
                class_avg_performance[submission.assignment.title] = []
            class_avg_performance[submission.assignment.title].append(submission.total_marks)

        performance_data.append(student_performance)

    # ✅ Compute class averages
    for assignment in class_avg_performance:
        scores = class_avg_performance[assignment]
        class_avg_performance[assignment] = sum(scores) / len(scores) if scores else 0

    # ✅ Fetch top 3 students based on performance
        # ✅ Sort students based on total score and get top 3
    sorted_performance_data = sorted(performance_data, key=lambda x: x["total_score"], reverse=True)
    top_students = sorted_performance_data[:3]

    # ✅ Convert data to JSON for JavaScript charts
    student_performance_json = json.dumps(student_performance_list)
    avg_class_performance_json = json.dumps(class_avg_performance)

    return render(request, 'teacher_dashboard.html', {
        'classes': classes,
        'current_class': current_class,
        'students': students,
        'assignments': assignments,
        'performance_data': performance_data,
        'top_students': top_students,
        'student_performance_json': student_performance_json,
        'avg_class_performance_json': avg_class_performance_json
    })


@login_required
def student_dashboard(request, class_id=None):
    # Fetch the student's profile
    student_profile = get_object_or_404(StudentProfile, student=request.user)
    
    # Fetch the classroom by ID
    classroom = get_object_or_404(Classroom, id=class_id)

    # ✅ Get all submissions for the student in this classroom
    submissions = Submission.objects.filter(
        student=student_profile,
        assignment__joined_classes=classroom  # Ensure that 'joined_classes' is used correctly
    ).order_by('-submitted_at')

    # ✅ Student's performance data (personal)
    student_performance = [{
        "assignment": s.assignment.title,
        "marks": s.total_marks,
        "grade": s.grade,
        "feedback": s.feedback
    } for s in submissions]

    # ✅ Get all students enrolled in this classroom
    student_enrollments = Enrollment.objects.filter(classroom=classroom, role='student')
    all_students = [enrollment.student for enrollment in student_enrollments]

    # ✅ Class performance calculation (aggregate marks for each assignment)
    class_performance = defaultdict(list)
    student_scores = {}

    # Efficient query to fetch all students' submissions at once
    submissions_for_class = Submission.objects.filter(
        assignment__joined_classes=classroom  # Using 'joined_classes' in the filter
    ).select_related('student', 'assignment')

    # Group submissions by assignment title and calculate the score for each student
    for sub in submissions_for_class:
        class_performance[sub.assignment.title].append(sub.total_marks)
        
        # Add total marks to the student's score
        student_name = f"{sub.student.student.first_name} {sub.student.student.last_name}".strip()
        if student_name in student_scores:
            student_scores[student_name]['overall_score'] += sub.total_marks
        else:
            student_scores[student_name] = {
                "student_name": student_name,
                "overall_score": sub.total_marks
            }

    

    # ✅ Sort students by their overall score to get the top 3 performers
    top_performers = sorted(student_scores.values(), key=lambda x: x['overall_score'], reverse=True)[:3]

    # Pass the context to the template
    return render(request, 'student_dashboard.html', {
        'submissions': submissions,
        'student_performance_json': json.dumps(student_performance),
        'top_performers': top_performers,
        'current_class': classroom,
        'student': student_profile, 
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
        form = AssignmentForm(request.POST,request.FILES)
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



# Create assignment view
def create_assignment(request):
    if request.method == 'POST':
        form = AssignmentForm(request.POST, request.FILES)
        if form.is_valid():
            assignment = form.save()

            file_path = assignment.model_answer_file.path
            print(f"Assignment file saved at: {file_path}")
            text = ""

            # ✅ TEXT Extraction
            try:
                text = extract_text_from_pdf(file_path)  # Calls the function to extract text
                assignment.extracted_text = text  # Save the extracted text
                assignment.save(update_fields=['extracted_text'])
            except Exception as e:
                print("Text Extraction Failed:", e)

            print("Extracted Text:\n", text)

            # ✅ IMAGE Extraction (PDF only)
            try:
                if file_path.endswith('.pdf'):
                    image_paths = extract_images_from_pdf(file_path, assignment.id)  # Extract images from PDF
                    # Optionally save the first image as the preview
                    if image_paths:
                        assignment.extracted_image.name = image_paths[0]  # Save first image as the extracted image
                        assignment.save(update_fields=['extracted_image'])
            except Exception as e:
                print("Diagram Extraction Failed:", e)

            messages.success(request, "Assignment uploaded and model answer processed.")
            return redirect('teacher_dashboard')
    else:
        form = AssignmentForm()

    return render(request, 'give_assignment.html', {'form': form})




# Notify teacher and student in case of plagiarism
def notify_teacher_and_student(submission, teacher_email, plagiarism_score):
    """Sends an alert email to the teacher and student about plagiarism detection."""
    message = (
        f"Hello,\n\nA submission from {submission.student.student.email} has a plagiarism score of {plagiarism_score:.2f}%.\n"
        f"Assignment: {submission.assignment.title}\n\nPlease review it.\n\nBest regards,\nSubmitTech"
    )
    send_mail(
        "⚠️ Plagiarism Alert: High Similarity Detected!",
        message,
        'noreply@submitech.com',
        [teacher_email, submission.student.student.email]
    )



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


@login_required
@user_passes_test(is_student)
def submit_assignment(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)
    student_profile = request.user.student_profile
    student_classes = student_profile.joined_classes.all()

    if not student_classes.filter(id__in=assignment.joined_classes.values_list('id', flat=True)).exists():
        messages.error(request, "You are not enrolled in this class.")
        return redirect('student_dashboard')

    query = request.GET.get('q')
    assignments = Assignment.objects.filter(joined_classes__in=student_classes).distinct()
    if query:
        assignments = assignments.filter(title__icontains=query)

    paginator = Paginator(assignments, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    if request.method == 'POST':
        form = SubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            submission = form.save(commit=False)
            submission.student = student_profile
            submission.assignment = assignment
            submission.submitted_at = timezone.now()
            submission.is_late = timezone.now() > assignment.due_date
            submission.save()

            evaluate_submission(submission.id)

            messages.success(request, 'Assignment submitted and evaluated successfully!')
            return redirect('student_dashboard')
    else:
        form = SubmissionForm()

    return render(request, 'submit_assignment.html', {
        'form': form,
        'assignment': assignment,
        'assignments': assignments,
        'page_obj': page_obj,
        'query': query
    })


@login_required
def progress_view(request, student_id, assignment_id):
    # Get the student profile using the related user ID
    student_profile = get_object_or_404(StudentProfile, student__id=student_id)

    # Get the assignment
    assignment = get_object_or_404(Assignment, id=assignment_id)

    # Get the student's submission
    student_submission = Submission.objects.filter(student=student_profile, assignment=assignment).first()
    student_marks = student_submission.total_marks if student_submission else 0

    # Get all submissions for this assignment
    all_submissions = Submission.objects.filter(assignment=assignment).select_related('student', 'student__student')

    # Prepare list of other students’ marks
    student_marks_list = [
        {
            "id": sub.student.student.id,  # Accessing the related User model's ID
            "name": f"{sub.student.student.first_name} {sub.student.student.last_name}",
            "marks": sub.total_marks
        }
        for sub in all_submissions if sub.student.student.id != student_id
    ]

    context = {
        "assignment_title": assignment.title,
        "student_marks": student_marks,
        "student_name": f"{student_profile.student.first_name} {student_profile.student.last_name}",
        "student_marks_list": student_marks_list,
    }

    return render(request, "progress_chart.html", context)


@login_required
def query1to1_view(request, teacher_id, student_id):
    teacher = get_object_or_404(TeacherProfile, teacher__id=teacher_id)
    student = get_object_or_404(StudentProfile, student__id=student_id)

    if request.method == "POST":
        message = request.POST.get("message")
        if message:
            PrivateMessage.objects.create(
                sender=request.user,
                message=message,
                receiver = teacher.teacher if request.user == student.student.student else student.student.student,
                timestamp=now()
            )
        return redirect("query1to1", teacher_id=teacher_id, student_id=student_id)  # Redirect after saving

    messages = PrivateMessage.objects.filter(
        sender__in=[teacher.teacher, student.student],
        receiver__in=[teacher.teacher, student.student]
    ).order_by("-timestamp")  # Get messages between the two users

    return render(request, "query1to1.html", {"teacher": teacher, "student": student, "messages": messages})


@login_required
def queryclassroom_view(request, class_id):
    classroom = get_object_or_404(Classroom, id=class_id)

    if request.method == "POST":
        message = request.POST.get("message")
        print(f"DEBUG: Received message: {message}")  # ✅ Check if message is received

        if message:  # Ensure message is not empty
            query = QueryMessage.objects.create(
                classroom=classroom,
                sender=request.user,
                message=message,
                timestamp=now()
            )
            print(f"DEBUG: Query saved: {query}")  # ✅ Check if query is saved

        return redirect("class_query", class_id=class_id)  # Redirect after saving

    queries = QueryMessage.objects.filter(classroom=classroom).order_by("-timestamp")
    print(f"DEBUG: Queries in DB: {queries}")  # ✅ Check if queries exist

    return render(request, "queryclassroom.html", {"classroom": classroom, "queries": queries})

# Function to notify students of a new assignment
def notify_students_of_new_assignment(assignment_id):
    """Send notifications to students who haven't submitted their assignment yet."""
    assignment = Assignment.objects.get(id=assignment_id)
    students = StudentProfile.objects.all()  # Fetch all students (StudentProfile)

    for student in students:
        # Check if the student has submitted the assignment
        submission = Submission.objects.filter(assignment=assignment, student=student).first()

        # If no submission or not submitted, send a notification
        if not submission or not submission.submitted:
            message = f"You have a new assignment: '{assignment.title}'. Please submit it before the due date."
            create_notification(student, message)  # Create a notification instance

# Function to create a new notification
def create_notification(student, message):
    """Create a notification entry in the database."""
    Notification.objects.create(student=student, message=message)

# Function to get unread notifications for a student
def get_notifications(student):
    """Get all unread notifications for a student."""
    return Notification.objects.filter(student=student, is_read=False)

# Function to mark a notification as read
def mark_notification_as_read(notification_id):
    """Mark a notification as read."""
    notification = Notification.objects.get(id=notification_id)
    notification.is_read = True
    notification.save()