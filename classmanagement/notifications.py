from django.core.mail import send_mail
from django.conf import settings

def notify_teacher_and_student(submission, teacher_email):
    """
    Sends an email notification to the teacher and student if plagiarism is detected.
    """
    student_email = submission.student.student.email
    subject = "⚠️ Plagiarism Alert: Assignment Submission"
    
    message = (
        f"Dear Teacher,\n\n"
        f"A plagiarism check was performed for assignment '{submission.assignment.title}'.\n"
        f"Student: {student_email}\n"
        f"Plagiarism Score: {submission.plagiarism_score}%\n\n"
        f"Please review the submission and take necessary action.\n\n"
        f"Best Regards,\nYour Assignment System"
    )

    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [teacher_email])

    # Notify Student
    student_message = (
        f"Dear {submission.student.student.first_name},\n\n"
        f"Your submission for '{submission.assignment.title}' has been flagged for plagiarism.\n"
        f"Plagiarism Score: {submission.plagiarism_score}%\n"
        f"Please ensure originality in your work.\n\n"
        f"Best Regards,\nYour Assignment System"
    )

    send_mail(subject, student_message, settings.DEFAULT_FROM_EMAIL, [student_email])

    print(f"📧 Notification sent to {teacher_email} and {student_email}")
