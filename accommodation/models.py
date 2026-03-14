from django.db import models


class Hostel(models.Model):
    class GenderType(models.TextChoices):
        FEMALE = 'Female Only', 'Female Only'
        MALE   = 'Male Only',   'Male Only'
        MIXED  = 'Mixed',       'Mixed'

    name           = models.CharField(max_length=100, unique=True)
    location       = models.CharField(max_length=100, blank=True)
    gender_type    = models.CharField(max_length=20, choices=GenderType.choices, default=GenderType.MIXED)
    total_beds     = models.PositiveIntegerField()
    available_beds = models.PositiveIntegerField(default=0)
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hostels'
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.pk:
            self.available_beds = self.total_beds
        super().save(*args, **kwargs)

    @property
    def occupied_beds(self):
        return self.total_beds - self.available_beds

    @property
    def occupancy_percent(self):
        return round((self.occupied_beds / self.total_beds) * 100) if self.total_beds else 0

    @property
    def is_full(self):
        return self.available_beds == 0


class Student(models.Model):
    student_number = models.CharField(max_length=30, unique=True)
    full_name      = models.CharField(max_length=120)
    phone_number   = models.CharField(max_length=20)
    gender         = models.CharField(max_length=10)
    condition      = models.CharField(max_length=30, default='None')
    home_address   = models.CharField(max_length=200)
    barcode_id     = models.CharField(max_length=50, unique=True, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'students'
        ordering = ['student_number']

    def __str__(self):
        return f'{self.student_number} — {self.full_name}'

    def save(self, *args, **kwargs):
        # barcode_id is always the student's own student number
        if not self.barcode_id:
            self.barcode_id = self.student_number
        super().save(*args, **kwargs)


class AccommodationApplication(models.Model):
    class Status(models.TextChoices):
        PENDING  = 'pending',  'Pending'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'

    reference_number     = models.CharField(max_length=20, unique=True, blank=True)
    student              = models.OneToOneField(Student, on_delete=models.CASCADE, related_name='application')
    hostel               = models.ForeignKey(Hostel, on_delete=models.SET_NULL, null=True, blank=True, related_name='applications')
    special_requirements = models.TextField(blank=True)
    notes                = models.TextField(blank=True)
    status               = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    date_applied         = models.DateField(auto_now_add=True)
    date_processed       = models.DateField(null=True, blank=True)
    processed_by         = models.ForeignKey(
        'authentication.AdminUser',
        on_delete=models.SET_NULL,
        null=True, blank=True,
    )

    class Meta:
        db_table = 'accommodation_applications'
        ordering = ['-date_applied']

    def __str__(self):
        return f'{self.reference_number} ({self.status})'

    def save(self, *args, **kwargs):
        if not self.reference_number:
            import datetime
            from django.db.models import Max
            year     = str(datetime.date.today().year)[2:]
            result   = AccommodationApplication.objects.aggregate(max_id=Max('id'))
            next_num = (result['max_id'] or 0) + 1
            self.reference_number = f'MM{year}{next_num:05d}'
        super().save(*args, **kwargs)