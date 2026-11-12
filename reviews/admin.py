from django.contrib import admin

from .models import Review, StoreFeedback


@admin.register(StoreFeedback)
class StoreFeedbackAdmin(admin.ModelAdmin):
    list_display = ["user", "rating", "is_public", "created_at"]
    list_filter = ["is_public", "rating"]
    search_fields = ["user__first_name", "user__email", "comment"]
    list_editable = ["is_public"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["user", "order", "product", "rating", "created_at"]
    list_filter = ["rating", "created_at"]
    search_fields = ["user__email", "order__number", "comment"]
    autocomplete_fields = ["user", "order", "product"]
