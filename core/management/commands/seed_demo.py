from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import Address
from catalog.models import Addon, Allergen, Category, Ingredient, Product, ProductAddon, ProductAllergen, ProductIngredient
from coupons.models import Coupon
from inventory.models import InventoryItem


class Command(BaseCommand):
    help = "Cria dados demonstrativos para desenvolvimento."

    def handle(self, *args, **options):
        User = get_user_model()
        client, _ = User.objects.get_or_create(
            email="cliente@demo.com",
            defaults={"first_name": "Cliente", "cpf": "11122233344", "role": User.Role.CLIENT},
        )
        client.set_password("123456")
        client.save()

        staff, _ = User.objects.get_or_create(
            email="staff@demo.com",
            defaults={"first_name": "Atendimento", "cpf": "22233344455", "role": User.Role.STAFF, "is_staff": True},
        )
        staff.set_password("123456")
        staff.save()

        manager, _ = User.objects.get_or_create(
            email="gerente@demo.com",
            defaults={"first_name": "Gerente", "cpf": "33344455566", "role": User.Role.MANAGER, "is_staff": True},
        )
        manager.set_password("123456")
        manager.save()

        Address.objects.get_or_create(
            user=client,
            label="Casa",
            defaults={
                "recipient_name": "Cliente Demo",
                "postal_code": "01001-000",
                "street": "Praça da Sé",
                "number": "100",
                "district": "Sé",
                "city": "São Paulo",
                "state": "SP",
                "is_default": True,
            },
        )

        cafes, _ = Category.objects.get_or_create(name="Cafés", defaults={"description": "Bebidas especiais"})
        cupcakes, _ = Category.objects.get_or_create(name="Cupcakes", defaults={"description": "Cupcakes artesanais"})

        gluten, _ = Allergen.objects.get_or_create(name="Glúten", defaults={"is_highlighted": True})
        lactose, _ = Allergen.objects.get_or_create(name="Lactose", defaults={"is_highlighted": True})
        cafe = Ingredient.objects.get_or_create(name="Café especial", defaults={"is_essential": True})[0]
        farinha = Ingredient.objects.get_or_create(name="Farinha de trigo", defaults={"is_essential": True})[0]
        leite = Ingredient.objects.get_or_create(name="Leite", defaults={"is_essential": True})[0]

        products = [
            (cafes, "Cappuccino Cremoso", Decimal("12.90"), "Café espresso com leite vaporizado e espuma cremosa.", [cafe, leite], [lactose]),
            (cafes, "Cold Brew da Casa", Decimal("14.90"), "Café extraído a frio, leve e refrescante.", [cafe], []),
            (cupcakes, "Cupcake Red Velvet", Decimal("13.50"), "Massa aveludada com cobertura de cream cheese.", [farinha, leite], [gluten, lactose]),
            (cupcakes, "Cupcake Chocolate Intenso", Decimal("12.50"), "Massa de cacau com recheio cremoso.", [farinha, leite], [gluten, lactose]),
        ]
        created_products = []
        for category, name, price, description, ingredients, allergens in products:
            product, _ = Product.objects.get_or_create(
                name=name,
                defaults={"category": category, "price": price, "description": description, "is_available": True},
            )
            created_products.append(product)
            for ingredient in ingredients:
                ProductIngredient.objects.get_or_create(product=product, ingredient=ingredient)
            for allergen in allergens:
                ProductAllergen.objects.get_or_create(product=product, allergen=allergen)

        addons = [
            Addon.objects.get_or_create(name="Ganache", kind=Addon.Kind.TOPPING, defaults={"price": Decimal("3.00")})[0],
            Addon.objects.get_or_create(name="Doce de leite", kind=Addon.Kind.FILLING, defaults={"price": Decimal("3.50")})[0],
            Addon.objects.get_or_create(name="Confeitos", kind=Addon.Kind.EXTRA, defaults={"price": Decimal("1.50")})[0],
        ]
        for product in created_products:
            if product.category == cupcakes:
                for addon in addons:
                    ProductAddon.objects.get_or_create(product=product, addon=addon)

        for ingredient in [cafe, farinha, leite]:
            InventoryItem.objects.get_or_create(
                ingredient=ingredient,
                defaults={"sku": f"INS-{ingredient.id:03d}", "unit": "kg", "quantity_on_hand": Decimal("10.000")},
            )

        Coupon.objects.get_or_create(
            code="CUPOM10",
            defaults={
                "description": "Desconto demonstrativo",
                "discount_type": Coupon.DiscountType.PERCENT,
                "value": Decimal("10.00"),
                "minimum_order_value": Decimal("20.00"),
                "starts_at": timezone.now() - timedelta(days=1),
                "expires_at": timezone.now() + timedelta(days=30),
                "usage_limit": 100,
                "usage_limit_per_user": 1,
            },
        )
        self.stdout.write(self.style.SUCCESS("Dados demonstrativos criados."))
