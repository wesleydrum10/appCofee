from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Address, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ["email", "first_name", "cpf", "role", "is_active", "is_staff"]
    list_filter = ["role", "is_active", "is_staff"]
    search_fields = ["email", "first_name", "last_name", "cpf"]
    ordering = ["email"]
    fieldsets = UserAdmin.fieldsets + (("Cafeteria", {"fields": ("cpf", "role", "email_confirmed")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("Cafeteria", {"fields": ("email", "cpf", "role")}),)


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ["user", "label", "city", "state", "is_default"]
    list_filter = ["state", "is_default"]
    search_fields = ["user__email", "street", "postal_code", "city"]
