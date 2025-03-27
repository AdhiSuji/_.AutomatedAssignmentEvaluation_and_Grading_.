from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from io import BytesIO
from django.utils import timezone
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.core.mail import send_mail
from collections import Counter
import nltk
import string
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from django.http import JsonResponse
from django.db.models import Q
from django.core.paginator import Paginator
from .models import (CustomUser, Classroom, Assignment, Submission,Performance,  StudentProfile, TeacherProfile)
from .forms import (UserRegistrationForm, AssignmentForm, SubmissionForm,LoginForm, ClassForm,StudentProfileForm)
from PyPDF2 import PdfReader
from docx import Document
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
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

    context = {
        'student_profile': student_profile,
        'joined_classes': joined_classes,
        'assignments': assignments,
        'teachers': teachers,
        'performance': performance,
        'form': form
    }

    return render(request, 'student_profile.html', context)

@login_required
@user_passes_test(is_teacher)
def teacher_dashboard(request, class_id):
    teacher_profile, created = TeacherProfile.objects.get_or_create(teacher=request.user)

    # ✅ All classes by this teacher
    classes = Classroom.objects.filter(teacher=teacher_profile)

    # ✅ Get current classroom or redirect
    try:
        classroom = Classroom.objects.get(id=class_id, teacher=teacher_profile)
    except Classroom.DoesNotExist:
        messages.error(request, "Classroom not found.")
        return redirect('teacher_dashboard', class_id=classes.first().id if classes.exists() else None)

    # ✅ Assignments and submissions for this classroom
    assignments = Assignment.objects.filter(teacher=teacher_profile, joined_classes=classroom)
    submissions = Submission.objects.filter(assignment__teacher=teacher_profile, assignment__joined_classes=classroom)

    query = request.GET.get('q')

    # ✅ Students who joined any of this teacher's classes
    students = StudentProfile.objects.filter(joined_classes__in=classes).distinct()

    if query:
        students = students.filter(
            Q(name__icontains=query) |
            Q(student__email__icontains=query)
        )

    paginator = Paginator(students, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # ✅ Queries from students in the current classroom
    #queries = Query.objects.filter(student__joined_classes=classroom).filter(answer__isnull=False).exclude(answer="")

    # ✅ Top students by performance in this classroom
    top_students = Performance.objects.filter(student__joined_classes=classroom).order_by('-average_score')[:3]

    return render(request, 'teacher_dashboard.html', {
        'classes': classes,
        'assignments': assignments,
        'submissions': submissions,
        'page_obj': page_obj,
        'top_students': top_students,
        'current_classroom': classroom
    })


@login_required
@user_passes_test(is_student)
def student_dashboard(request, class_id=None):
    student = request.user
    student_profile = get_object_or_404(StudentProfile, student=student)

    # If class_id is passed, use it; otherwise get the first joined_class (optional logic)
    if class_id:
        classroom = get_object_or_404(Classroom, id=class_id)
    else:
        # Grabbing the first class the student joined
        classroom = student_profile.joined_classes.first()

    if not classroom:
        # No class joined yet
        messages.warning(request, "You haven't joined any classes yet!")
        return redirect('somewhere_else')  # Update to an appropriate URL

    # ✅ Get assignments assigned to this classroom
    assignments = Assignment.objects.filter(joined_classes=classroom)

    # ✅ Get student's submissions
    submissions = Submission.objects.filter(student=student_profile)

    # ✅ Search for other students in the same classroom
    query = request.GET.get('q')
    all_students = classroom.joined_students.all()  # related_name='joined_students' in Classroom model

    if query:
        all_students = all_students.filter(
            Q(student__username__icontains=query) |
            Q(student__first_name__icontains=query)
        )

    # ✅ Paginate the list of students
    paginator = Paginator(all_students, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'student_dashboard.html', {
        'assignments': assignments,
        'submissions': submissions,
        'classroom': classroom,
        'page_obj': page_obj,
        'query': query,
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

# Define plagiarism threshold
PLAGIARISM_THRESHOLD = 40  # Similarity threshold for plagiarism


### 🟢 **Plagiarism Checking System** 🟢
def plagiarism_check(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)
    submissions = Submission.objects.filter(assignment=assignment)

    teacher_keywords = assignment.keywords.split(",")  # Extract teacher-set keywords
    teacher_email = assignment.teacher.teacher.email

    for submission in submissions:
        # Extract text from file
        submission_text = extract_text(submission.file)

        # Get unique keywords and their frequency
        extracted_keywords = extract_keywords(submission_text)

        # Store extracted content & keywords in the database
        submission.content = submission_text  # Save extracted text
        submission.keywords = str(extracted_keywords)  # Save keyword frequency
        submission.save()

        print(f"Submission {submission.student.student.email}:")
        print(f"Extracted Keywords: {extracted_keywords}\n")

        # Check for student-to-student plagiarism
        other_subs = submissions.exclude(id=submission.id)
        plagiarism_score = check_student_to_student_plagiarism(submission, other_subs, teacher_email)

        print(f"Checked submission {submission.student.student.email}: Plagiarism Score: {plagiarism_score}")

    messages.success(request, "Plagiarism checks complete with keyword extraction!")
    return redirect('submit_assignment', assignment_id=assignment.id)


### 🟢 **Extract Text from Files** 🟢
def extract_text(file_field):
    """Detect file type and extract text."""
    filename = file_field.name.lower()

    if filename.endswith('.pdf'):
        return extract_text_from_pdf(file_field)
    elif filename.endswith('.txt'):
        return extract_text_from_txt(file_field)
    elif filename.endswith('.docx'):
        return extract_text_from_docx(file_field)
    else:
        print(f"Unsupported file type: {filename}")
        return ""


def extract_text_from_pdf(file_field):
    """Extract text from a PDF file."""
    try:
        file_field.open()
        reader = PdfReader(file_field)
        text = "\n".join([page.extract_text() or "" for page in reader.pages])
        file_field.close()
        return text if text.strip() else "No readable text found in PDF."
    except Exception as e:
        print(f"PDF Extraction error: {str(e)}")
        return ""


def extract_text_from_txt(file_field):
    """Extract text from a TXT file."""
    try:
        file_field.open()
        content = file_field.read().decode('utf-8')  # Convert bytes to string
        file_field.close()
        return content
    except Exception as e:
        print(f"Error reading TXT file: {e}")
        return ""


def extract_text_from_docx(file_field):
    """Extract text from a DOCX file."""
    try:
        file_field.open()
        doc_file = BytesIO(file_field.read())  # Convert to BytesIO
        document = Document(doc_file)  # Load DOCX from BytesIO
        text = "\n".join([paragraph.text for paragraph in document.paragraphs])
        file_field.close()
        return text
    except Exception as e:
        print(f"Error reading DOCX file: {e}")
        return ""


### 🟢 **Extract Keywords & Count Frequency** 🟢
def extract_keywords(text):
    """Extract unique keywords and their frequency from text."""
    stop_words = set(stopwords.words('english'))
    text = text.lower().translate(str.maketrans("", "", string.punctuation))  # Lowercase & remove punctuation
    words = word_tokenize(text)  # Tokenize words
    filtered_words = [word for word in words if word not in stop_words and word.isalpha()]  # Remove stopwords & numbers

    keyword_counts = Counter(filtered_words)  # Count keyword frequency
    return dict(keyword_counts)


### 🟢 **Keyword Matching System** 🟢
def check_keyword_match(teacher_keywords, extracted_keywords):
    """Check how many teacher keywords match with extracted student keywords."""
    teacher_keywords = [kw.strip().lower() for kw in teacher_keywords]
    student_keywords = set(extracted_keywords.keys())  # Extract unique words

    matched = sum(1 for kw in teacher_keywords if kw in student_keywords)
    total_keywords = len(teacher_keywords)

    return (matched / total_keywords) * 100 if total_keywords > 0 else 0


### 🟢 **Student-to-Student Plagiarism Check** 🟢
def check_student_to_student_plagiarism(current_submission, other_submissions, teacher_email):
    """Check similarity between student submissions using TF-IDF & Cosine Similarity."""
    current_text = extract_text(current_submission.file)

    other_texts = []
    for sub in other_submissions:
        other_text = extract_text(sub.file)
        if other_text.strip():
            other_texts.append(other_text)

    if not other_texts:
        current_submission.plagiarism_score = 0.0
        current_submission.save()
        return 0.0

    # Compute TF-IDF vectors
    vectorizer = TfidfVectorizer().fit_transform([current_text] + other_texts)
    vectors = vectorizer.toarray()

    # Compute similarity scores
    similarities = cosine_similarity([vectors[0]], vectors[1:])[0]
    highest_similarity = max(similarities) * 100 if similarities.size > 0 else 0

    # Save plagiarism score
    if highest_similarity > 0:
        current_submission.plagiarism_score = round(highest_similarity, 2)
        current_submission.save()

    # Notify if plagiarism detected
    if highest_similarity > PLAGIARISM_THRESHOLD and not current_submission.notified:
        notify_teacher_and_student(current_submission, teacher_email)
        current_submission.notified = True
        current_submission.save()

    return highest_similarity

### 🟢 **Notify Teacher & Student** 🟢
def notify_teacher_and_student(submission, teacher_email):
    """Send notification if plagiarism is detected."""
    student_email = submission.student.student.email
    plagiarism_score = submission.plagiarism_score

    print(f"⚠️ Plagiarism Alert ⚠️")
    print(f"Student: {student_email}")
    print(f"Plagiarism Score: {plagiarism_score}%")
    print(f"Notification sent to: {teacher_email}")

    # Here, you can integrate email notifications if needed


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

    extracted_keywords = extract_keywords(submission_text)  # Extract keywords from student text
    keyword_match = check_keyword_match(keywords, extracted_keywords)
    results['keyword_match'] = keyword_match

    plagiarism_score = check_student_to_student_plagiarism(submission, other_submissions, teacher_email)
    results['plagiarism_score'] = plagiarism_score

    return results


@login_required
@user_passes_test(is_teacher)
def grade_assignment(request, assignment_id):  # Add assignment_id here
    assignment = get_object_or_404(Assignment, id=assignment_id)

    if request.method == "POST":
        grade = request.POST.get("grade")
        feedback = request.POST.get("feedback")

        submission = Submission.objects.filter(assignment=assignment).first()
        if submission:
            submission.grade = grade
            submission.feedback = feedback
            submission.save()
            messages.success(request, "Assignment graded successfully!")
        else:
            messages.error(request, "No submission found for this assignment.")

        return redirect('teacher_dashboard')

    return render(request, "grade_assignment.html", {"assignment": assignment})



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


def query_view(request, class_id):
    classroom = get_object_or_404(Classroom, id=class_id)
    return render(request, 'query.html', {'classroom': classroom})