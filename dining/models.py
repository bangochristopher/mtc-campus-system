## dining/models.py
from django.db import models
from accommodation.models import Student

class MealRegister(models.Model):
    class MealType(models.TextChoices):
        BREAKFAST = 'Breakfast'
        LUNCH     = 'Lunch'
        SUPPER    = 'Supper'
    class ScanStatus(models.TextChoices):
        SERVED    = 'served'
        DENIED    = 'denied'
        DUPLICATE = 'duplicate'

    student         = models.ForeignKey(Student, on_delete=models.CASCADE, null=True, blank=True, related_name='meal_records')
    meal_type       = models.CharField(max_length=10, choices=MealType.choices)
    scan_status     = models.CharField(max_length=10, choices=ScanStatus.choices)
    scanned_barcode = models.CharField(max_length=50)
    scan_date       = models.DateField()
    scan_time       = models.TimeField(auto_now_add=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'meal_register'
        ordering = ['-created_at']
        indexes  = [models.Index(fields=['student','meal_type','scan_date']), models.Index(fields=['scan_date'])]
