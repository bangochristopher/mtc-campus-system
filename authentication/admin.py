from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import AdminUser
@admin.register(AdminUser)
class AdminUserAdmin(UserAdmin):
    model = AdminUser
    list_display = ['email','full_name','role','is_active']
    list_filter  = ['role']
    search_fields= ['email','full_name']
    ordering     = ['email']
    fieldsets = (
        (None,           {'fields': ('email','password')}),
        ('Personal',     {'fields': ('full_name','role')}),
        ('Permissions',  {'fields': ('is_active','is_staff','is_superuser')}),
    )
    add_fieldsets = ((None,{'classes':('wide',),'fields':('email','full_name','role','password1','password2','is_active','is_staff')}),)
