import json

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from catalog.models import (
    Addon, Allergen, Category, Ingredient, Product,
    ProductAddon, ProductAllergen, ProductIngredient,
)


class Command(BaseCommand):
    help = "Adiciona o catálogo versionado com imagens, sem criar usuários nem sobrescrever produtos existentes."

    @transaction.atomic
    def handle(self, *args, **options):
        data = json.loads((settings.BASE_DIR / "catalog/data/catalog.json").read_text(encoding="utf-8"))
        categories = {}
        for row in data["categories"]:
            fields = dict(row)
            slug = fields.pop("slug")
            # seed_demo pode já ter criado a categoria pelo nome.
            category = Category.objects.filter(slug=slug).first()
            if category is None:
                category, _ = Category.objects.get_or_create(name=fields.pop("name"), defaults={"slug": slug, **fields})
            categories[slug] = category
        ingredients = {}
        for row in data["ingredients"]:
            fields = dict(row)
            name = fields.pop("name")
            ingredients[name], _ = Ingredient.objects.get_or_create(name=name, defaults=fields)
        allergens = {}
        for row in data["allergens"]:
            fields = dict(row)
            slug = fields.pop("slug")
            allergen = Allergen.objects.filter(slug=slug).first()
            if allergen is None:
                allergen, _ = Allergen.objects.get_or_create(name=fields.pop("name"), defaults={"slug": slug, **fields})
            allergens[slug] = allergen
        addons = {}
        for row in data["addons"]:
            fields = dict(row)
            name, kind = fields.pop("name"), fields.pop("kind")
            addons[(name, kind)], _ = Addon.objects.get_or_create(name=name, kind=kind, defaults=fields)

        created_count = image_count = 0
        for row in data["products"]:
            fields = dict(row)
            slug = fields.pop("slug")
            product_ingredients = fields.pop("ingredients")
            product_allergens = fields.pop("allergens")
            product_addons = fields.pop("addons")
            fields["category"] = categories[fields["category"]]
            product, created = Product.objects.get_or_create(slug=slug, defaults=fields)
            if created:
                created_count += 1
            elif not product.image and fields["image"]:
                # Associa um arquivo fixo; não grava upload no disco efêmero.
                product.image = fields["image"]
                product.save(update_fields=["image", "updated_at"])
                image_count += 1
            # Relações de produtos existentes são mantidas integralmente.
            if not created:
                continue
            for item in product_ingredients:
                ProductIngredient.objects.create(
                    product=product, ingredient=ingredients[item["ingredient__name"]], quantity=item["quantity"],
                )
            for slug in product_allergens:
                ProductAllergen.objects.create(product=product, allergen=allergens[slug])
            for item in product_addons:
                ProductAddon.objects.create(product=product, addon=addons[(item["name"], item["kind"])])
        self.stdout.write(self.style.SUCCESS(
            f"Catálogo carregado: {created_count} produtos criados, {image_count} imagens preenchidas. "
            f"{len(data['products'])} produtos no catálogo versionado."
        ))
