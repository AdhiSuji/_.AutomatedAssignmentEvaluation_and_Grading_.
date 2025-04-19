from django.apps import AppConfig

# apps.py
class ClassManagementConfig(AppConfig):
    name = 'classmanagement'

    def ready(self):
        import classmanagement.signals  # Ensure this doesn't import anything that causes setup

