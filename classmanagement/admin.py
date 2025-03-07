from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ('username', 'email', 'role', 'is_staff', 'is_active')
    fieldsets = UserAdmin.fieldsets + ((None, {'fields': ('role', 'teacher_reference_id')}),)

admin.site.register(CustomUser, CustomUserAdmin)
