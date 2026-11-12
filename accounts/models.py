from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("O e-mail é obrigatório.")
        email = self.normalize_email(email)
        user = self.model(email=email, username=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Role.MANAGER)
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        CLIENT = "CLIENT", "Cliente"
        STAFF = "STAFF", "Atendimento"
        MANAGER = "MANAGER", "Gerente"

    username = models.CharField(max_length=150, blank=True)
    email = models.EmailField(unique=True)
    cpf = models.CharField(
        "CPF",
        max_length=14,
        unique=True,
        null=True,
        blank=True,
        validators=[RegexValidator(r"^\d{3}\.?\d{3}\.?\d{3}-?\d{2}$", "Informe um CPF válido.")],
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CLIENT)
    email_confirmed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = UserManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["cpf"],
                condition=Q(cpf__isnull=False),
                name="accounts_unique_non_null_cpf",
            )
        ]

    def __str__(self):
        return self.get_full_name() or self.email

    @property
    def is_manager(self):
        return self.role == self.Role.MANAGER or self.is_superuser


class Address(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="addresses")
    label = models.CharField(max_length=60, default="Principal")
    recipient_name = models.CharField(max_length=120)
    postal_code = models.CharField(max_length=9)
    street = models.CharField(max_length=160)
    number = models.CharField(max_length=20)
    complement = models.CharField(max_length=120, blank=True)
    district = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=2)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_default", "label"]

    def __str__(self):
        return f"{self.label} - {self.street}, {self.number}"
