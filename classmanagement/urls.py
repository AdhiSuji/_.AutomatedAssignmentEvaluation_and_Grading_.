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
    path('teacher/view-submissions/', views.view_submissions, name='view_submissions_all'),
    path('teacher/class/<int:classroom_id>/view-submissions/', views.view_submissions, name='view_submissions_by_classroom'),
    path('teacher/class/<int:classroom_id>/student/<int:student_id>/view-submissions/', views.view_submissions, name='view_submissions_by_student'),
    path('assignments/grade/<int:assignment_id>/', views.grade_assignment, name='grade_assignment'),

    # Performance & Queries
    path('progress/<str:assignment_title>/', views.progress_view, name='progress_chart'),
    path("private-chat/<int:teacher_id>/<int:student_id>/", views.query1to1_view, name="private_query"),
    path("classroom-chat/<int:class_id>/", views.queryclassroom_view, name="class_query"),

    # Class & Teacher Management
    path('teacher/add/', views.add_teacher, name='add_teacher'),
    path('create_class/', views.create_class, name='teacher_create_class'),
    path('teacher/class/<int:class_id>/enroll-students/', views.enroll_students, name='enroll_students'),
    path('teacher/class/<int:class_id>/students/', views.view_enrolled_students, name='view_students'),
    path('student/join-class/', views.join_class, name='join_class'),
    path("delete_class/<int:class_id>/", views.delete_class, name="delete_class"),
    path('get_teacher_classes/', views.get_teacher_classes, name='get_teacher_classes'),

    # Notifications
    path('notifications/send/', views.send_notifications, name='send_notifications'),
    
    #dashboard

    path("teacher/dashboard/", views.teacher_dashboard, name="teacher_dashboard"),
    path("teacher/dashboard/<int:class_id>/", views.teacher_dashboard, name="teacher_dashboard"),
    path("student/dashboard/", views.student_dashboard, name="student_dashboard"),
    path("student/dashboard/<int:class_id>/", views.student_dashboard, name="student_dashboard"),
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
]    