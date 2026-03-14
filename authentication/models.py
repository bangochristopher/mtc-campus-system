from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models

class AdminUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra):
        email = self.normalize_email(email)
        user  = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user
    def create_superuser(self, email, password=None, **extra):
        extra.setdefault('is_staff', True)
        extra.setdefault('is_superuser', True)
        extra.setdefault('role', AdminUser.Role.ACCOMMODATION)
        return self.create_user(email, password, **extra)

class AdminUser(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        ACCOMMODATION = 'accommodation', 'Accommodation Admin'
        DINING        = 'dining',        'Dining Admin'
        SECURITY      = 'security',      'Security Admin'
    email     = models.EmailField(unique=True)
    full_name = models.CharField(max_length=120)
    role      = models.CharField(max_length=20, choices=Role.choices)
    is_active = models.BooleanField(default=True)
    is_staff  = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = AdminUserManager()
    USERNAME_FIELD  = 'email'
    REQUIRED_FIELDS = ['full_name', 'role']

    class Meta:
        db_table = 'admin_users'

    def __str__(self):
        return f'{self.full_name} ({self.role})'
