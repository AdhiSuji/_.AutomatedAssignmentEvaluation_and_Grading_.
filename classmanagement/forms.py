from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, Assignment, Submission, Query, Classroom, StudentProfile, TeacherProfile

# ---------------------------------------------------
# ✅ User Registration Form (For Teachers & Students)
# ---------------------------------------------------
class UserRegistrationForm(UserCreationForm):
    ROLE_CHOICES = (
        ('student', 'Student'),
        ('teacher', 'Teacher'),
    )

    role = forms.ChoiceField(
        choices=ROLE_CHOICES,
        required=True,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )

    reference_id = forms.CharField(
        required=False,
        label="Teacher Reference ID (Only for Students)",
        widget=forms.TextInput(attrs={'placeholder': 'Enter Teacher Reference ID'})
    )

    selected_class = forms.ModelChoiceField(
        queryset=Classroom.objects.none(),  # Dynamically populated
        required=False,
        label="Select Class (Only for Students)"
    )

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'password1', 'password2', 'role', 'reference_id', 'selected_class']

    def __init__(self, *args, **kwargs):
        super(UserRegistrationForm, self).__init__(*args, **kwargs)

        # Initialize selected_class queryset as empty
        self.fields['selected_class'].queryset = Classroom.objects.none()

        if 'reference_id' in self.data:
            reference_id = self.data.get('reference_id')
            try:
                teacher = CustomUser.objects.get(reference_id=reference_id, role='teacher')
                self.fields['selected_class'].queryset = Classroom.objects.filter(teacher=teacher)
            except CustomUser.DoesNotExist:
                self.fields['selected_class'].queryset = Classroom.objects.none()

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')

        if role == 'student':
            reference_id = cleaned_data.get('reference_id')
            selected_class = cleaned_data.get('selected_class')

            if not reference_id:
                raise forms.ValidationError("Students must enter a valid Teacher Reference ID.")
            if not selected_class:
                raise forms.ValidationError("Students must select a class.")

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = self.cleaned_data['role']

        if commit:
            user.save()
            if user.role == 'student':
                StudentProfile.objects.create(
                    student=user,
                    assigned_class=self.cleaned_data['selected_class']
                )
        return user

# -----------------------------------
# ✅ Login Form (Simple Auth)
# -----------------------------------
class LoginForm(forms.Form):
    username = forms.CharField(max_length=150)
    password = forms.CharField(widget=forms.PasswordInput)

# ---------------------------------------------------
# ✅ Class Creation Form (For Teachers)
# ---------------------------------------------------
class ClassCreationForm(forms.ModelForm):
    class Meta:
        model = Classroom
        fields = ['name']

    def __init__(self, *args, **kwargs):
        super(ClassCreationForm, self).__init__(*args, **kwargs)
        self.fields['name'].widget.attrs.update({'placeholder': 'Enter Class Name'})

# ---------------------------------------------------
# ✅ Student Profile Form (Optional Profile Update)
# ---------------------------------------------------
class StudentProfileForm(forms.Form):
    reference_id = forms.CharField(
        required=True,
        label="Teacher Reference ID",
        widget=forms.TextInput(attrs={"placeholder": "Enter Teacher Reference ID"})
    )

    class_id = forms.ModelChoiceField(
        queryset=Classroom.objects.none(),
        required=True,
        label="Select Class"
    )

    def __init__(self, *args, **kwargs):
        super(StudentProfileForm, self).__init__(*args, **kwargs)

        # If reference_id exists in data (after user types it)
        if 'reference_id' in self.data:
            reference_id = self.data.get('reference_id')
            try:
                teacher = TeacherProfile.objects.get(reference_id=reference_id)
                self.fields['class_id'].queryset = Classroom.objects.filter(teacher=teacher)
            except TeacherProfile.DoesNotExist:
                self.fields['class_id'].queryset = Classroom.objects.none()
        else:
            self.fields['class_id'].queryset = Classroom.objects.none()



# ---------------------------------------------------
# ✅ Assignment Creation Form (For Teachers)
# ---------------------------------------------------
class AssignmentForm(forms.ModelForm):
    class Meta:
        model = Assignment
        fields = ['title', 'description', 'due_date', 'keywords']

    def __init__(self, *args, **kwargs):
        super(AssignmentForm, self).__init__(*args, **kwargs)
        self.fields['title'].widget.attrs.update({'placeholder': 'Assignment Title'})

# ---------------------------------------------------
# ✅ Assignment Submission Form (For Students)
# ---------------------------------------------------
class SubmissionForm(forms.ModelForm):
    class Meta:
        model = Submission
        fields = ['assignment', 'file', 'comments']

# ---------------------------------------------------
# ✅ Query Form (For Students)
# ---------------------------------------------------
class QueryForm(forms.ModelForm):
    class Meta:
        model = Query
        fields = ['question']

# ---------------------------------------------------
# ✅ Query Response Form (For Teachers)
# ---------------------------------------------------
class QueryResponseForm(forms.ModelForm):
    class Meta:
        model = Query
        fields = ['response']

# ---------------------------------------------------
# ✅ Class Enrollment Form (For Students)
# ---------------------------------------------------
class EnrollmentForm(forms.Form):
    reference_id = forms.CharField(
        max_length=10,
        help_text="Enter teacher's reference ID"
    )
    selected_class = forms.ModelChoiceField(
        queryset=Classroom.objects.none(),
        label="Select Class"
    )

    def __init__(self, *args, **kwargs):
        super(EnrollmentForm, self).__init__(*args, **kwargs)

        if 'reference_id' in self.data:
            reference_id = self.data.get('reference_id')
            try:
                teacher = TeacherProfile.objects.get(reference_id=reference_id)
                self.fields['selected_class'].queryset = Classroom.objects.filter(teacher=teacher)
            except TeacherProfile.DoesNotExist:
                self.fields['selected_class'].queryset = Classroom.objects.none()

    def clean(self):
        cleaned_data = super().clean()
        reference_id = cleaned_data.get('reference_id')
        selected_class = cleaned_data.get('selected_class')

        if not reference_id:
            raise forms.ValidationError("You must enter a valid Teacher Reference ID.")

        if not selected_class:
            raise forms.ValidationError("You must select a class to enroll in.")

        return cleaned_data

    def save(self, student_user):
        selected_class = self.cleaned_data['selected_class']

        student_profile, created = StudentProfile.objects.get_or_create(student=student_user)

        if selected_class in student_profile.assigned_classes.all():
            raise forms.ValidationError("You are already enrolled in this class.")

        student_profile.assigned_classes.add(selected_class)
        return student_profile


class ClassForm(forms.ModelForm):
    class Meta:
        model = Classroom
        fields = ['name', 'subject', 'description']

class TeacherProfileForm(forms.ModelForm):
    class Meta:
        model = TeacherProfile
        fields = ['profile_pic', 'bio']


class StudentProfileForm(forms.ModelForm):
    class Meta:
        model = StudentProfile
        fields = ['profile_pic', 'bio']

        widgets = {
            'profile_pic': forms.FileInput(attrs={
                'class': 'form-control form-control-sm',
                'style': 'font-size: 0.75rem;'
            }),
            'bio': forms.Textarea(attrs={
                'class': 'form-control form-control-sm',
                'rows': 2,
                'style': 'font-size: 0.75rem; resize: none; max-width: 200px;'
            }),
        }
