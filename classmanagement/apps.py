from django.apps import AppConfig

class ClassmanagementConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'classmanagement'
    
    def ready(self):
        import classmanagement.signals
        print("Signals imported successfully")
