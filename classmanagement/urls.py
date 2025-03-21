from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Home Page
    path('', views.home_view, name='home'),

    # Authentication
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),


    # Profiles
    path('student/profile/', views.student_profile, name='student_profile'),
    path('teacher/profile/', views.teacher_profile, name='teacher_profile'),

    # Assignments
    path('assignments/give/<int:class_id>/', views.give_assignment, name='give_assignment'),
    path("assignments/given/<int:class_id>/", views.given_assignment, name="given_assignment"),
    path('assignments/submit/submit/<int:assignment_id>/', views.submit_assignment, name='submit_assignment'),
    path('assignments/view/<int:assignment_id>/', views.view_submissions, name='view_submissions'),
    path('assignments/grade/', views.grade_assignment, name='grade_assignment'),

    # Performance & Queries
    path('student/performance/', views.student_performance, name='student_performance'),
    path('student-progress/<int:student_id>/', views.student_progress, name='student_progress'),
    path('queries/', views.ask_query, name='ask_query'),
    path('queries/respond/', views.respond_query, name='respond_query'),

    # Class & Teacher Management
    path('teacher/add/', views.add_teacher, name='add_teacher'),
    path('create_class/', views.create_class, name='teacher_create_class'),
    path('class/enroll/', views.enroll_student, name='enroll_student'),
    path('student/join-class/', views.join_class, name='join_class'),
    path("delete_class/<int:class_id>/", views.delete_class, name="delete_class"),
    path('get_teacher_classes/', views.get_teacher_classes, name='get_teacher_classes'),
    path('teacher/plagiarism_check/<int:assignment_id>/', views.start_plagiarism_check, name='start_plagiarism_check'),

    # Notifications
    path('notifications/send/', views.send_notifications, name='send_notifications'),
    
    #dashboard
    path("teacher/dashboard/<int:class_id>/", views.teacher_dashboard, name="teacher_dashboard"),
    path("student/dashboard/<int:class_id>/", views.student_dashboard, name="student_dashboard"),

]    