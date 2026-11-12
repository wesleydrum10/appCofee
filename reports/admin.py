from django.contrib import admin

from .models import Expense


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ["description", "amount", "paid_on", "created_by"]
    list_filter = ["paid_on"]
    search_fields = ["description"]
    readonly_fields = ["created_by"]

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
