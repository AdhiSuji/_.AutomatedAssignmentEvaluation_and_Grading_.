from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, Assignment, Submission, Query, Class, StudentProfile


class UserRegistrationForm(UserCreationForm):
    ROLE_CHOICES = (
        ('student', 'Student'),
        ('teacher', 'Teacher'),
    )

    role = forms.ChoiceField(choices=ROLE_CHOICES, required=True, widget=forms.RadioSelect)
    selected_class = forms.ModelChoiceField(
        queryset=Class.objects.all(),
        empty_label="Select Class (Only for Students)",
        required=False  # Teachers don't need this field
    )

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'password1', 'password2', 'role', 'selected_class']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = self.cleaned_data['role']  # Set user role based on selection
        
        if commit:
            user.save()
            if user.role == 'student':
                StudentProfile.objects.create(student=user, assigned_class=self.cleaned_data['selected_class'])
        return user


class LoginForm(forms.Form):
    username = forms.CharField(max_length=150)
    password = forms.CharField(widget=forms.PasswordInput)


class ClassForm(forms.ModelForm):
    class Meta:
        model = Class
        fields = ['name']
        

# Assignment Creation Form (For Teachers)
class AssignmentForm(forms.ModelForm):
    class Meta:
        model = Assignment
        fields = ['title', 'description', 'due_date', 'keywords']

# Assignment Submission Form (For Students)
class SubmissionForm(forms.ModelForm):
    class Meta:
        model = Submission
        fields = ['assignment', 'file', 'comments']

# Query Form (For Students)
class QueryForm(forms.ModelForm):
    class Meta:
        model = Query
        fields = ['question']

# Response Form (For Teachers)
class QueryResponseForm(forms.ModelForm):
    class Meta:
        model = Query
        fields = ['response']

# Class Creation Form (For Teachers)
class ClassCreationForm(forms.ModelForm):
    class Meta:
        model = Class
        fields = ['name']

# Class Enrollment Form (For Students)
class EnrollmentForm(forms.Form):
    reference_id = forms.CharField(max_length=10, help_text="Enter teacher's reference ID")
    selected_class = forms.ModelChoiceField(queryset=Class.objects.none())

    def __init__(self, *args, **kwargs):
        teacher = kwargs.pop('teacher', None)
        super(EnrollmentForm, self).__init__(*args, **kwargs)
        if teacher:
            self.fields['selected_class'].queryset = Class.objects.filter(teacher=teacher)

