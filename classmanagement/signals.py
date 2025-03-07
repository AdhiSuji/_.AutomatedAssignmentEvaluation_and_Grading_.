from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import CustomUser, StudentProfile

@receiver(post_save, sender=CustomUser)
def create_student_profile(sender, instance, created, **kwargs):
    if created and instance.role == "student":  # Create profile only for students
        StudentProfile.objects.create(user=instance)

@receiver(post_save, sender=CustomUser)
def save_student_profile(sender, instance, created, **kwargs):
    if created and instance.is_student:
        StudentProfile.objects.create(user=instance)
    instance.student_profile.save()  #