from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import CustomUser, TeacherProfile

@receiver(post_save, sender=CustomUser)
def sync_teacher_reference_id(sender, instance, **kwargs):
    """Ensure TeacherProfile.reference_id matches CustomUser.reference_id."""
    if instance.role == 'teacher':
        TeacherProfile.objects.update_or_create(
            teacher=instance,  # Find the teacher's profile
            defaults={'reference_id': instance.reference_id}  # Update reference_id
        )
