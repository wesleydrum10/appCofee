from django.contrib import admin

from .models import Addon, Allergen, Category, Ingredient, Product, ProductAddon, ProductAllergen, ProductIngredient


class ProductIngredientInline(admin.TabularInline):
    model = ProductIngredient
    extra = 1
    autocomplete_fields = ["ingredient"]


class ProductAllergenInline(admin.TabularInline):
    model = ProductAllergen
    extra = 1
    autocomplete_fields = ["allergen"]


class ProductAddonInline(admin.TabularInline):
    model = ProductAddon
    extra = 1
    autocomplete_fields = ["addon"]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "price", "stock_quantity", "minimum_stock", "is_available", "is_active", "created_at"]
    list_filter = ["category", "is_available", "is_active", "allergens"]
    search_fields = ["name", "description"]
    prepopulated_fields = {"slug": ("name",)}
    autocomplete_fields = ["category"]
    inlines = [ProductIngredientInline, ProductAllergenInline, ProductAddonInline]


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "is_active"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    search_fields = ["name"]
    list_display = ["name", "is_essential"]


@admin.register(Allergen)
class AllergenAdmin(admin.ModelAdmin):
    search_fields = ["name"]
    list_display = ["name", "is_highlighted"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Addon)
class AddonAdmin(admin.ModelAdmin):
    list_display = ["name", "kind", "price", "is_active"]
    list_filter = ["kind", "is_active"]
    search_fields = ["name"]
