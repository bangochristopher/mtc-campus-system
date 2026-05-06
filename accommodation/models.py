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


class Floor(models.Model):
    class FloorName(models.TextChoices):
        GROUND = 'ground', 'Ground Floor'
        FIRST  = 'first',  'First Floor'
        SECOND = 'second', 'Second Floor'
        THIRD  = 'third',  'Third Floor'

    hostel = models.ForeignKey(Hostel, on_delete=models.CASCADE, related_name='floors')
    name   = models.CharField(max_length=20, choices=FloorName.choices)
    total_beds = models.PositiveIntegerField(default=0)
    available_beds = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'floors'
        unique_together = ['hostel', 'name']
        ordering = ['hostel', 'name']

    def __str__(self):
        return f'{self.hostel.name} - {self.get_name_display()}'

    def save(self, *args, **kwargs):
        if not self.pk:
            self.available_beds = self.total_beds
        super().save(*args, **kwargs)

    @property
    def occupied_beds(self):
        return self.total_beds - self.available_beds


class Room(models.Model):
    class RoomStatus(models.TextChoices):
        ACTIVE       = 'active',       'Active'
        MAINTENANCE  = 'maintenance',  'Under Maintenance'
        RESERVED     = 'reserved',     'Reserved'

    hostel      = models.ForeignKey(Hostel, on_delete=models.CASCADE, related_name='rooms')
    floor       = models.ForeignKey(Floor, on_delete=models.CASCADE, related_name='rooms')
    room_number = models.CharField(max_length=10)
    capacity    = models.PositiveIntegerField(default=2)
    occupied    = models.PositiveIntegerField(default=0)
    status      = models.CharField(max_length=20, choices=RoomStatus.choices, default=RoomStatus.ACTIVE)

    class Meta:
        db_table = 'rooms'
        unique_together = ['hostel', 'room_number']
        ordering = ['hostel', 'room_number']

    def __str__(self):
        return f'{self.room_number} ({self.hostel.name})'

    @property
    def available_beds(self):
        return self.capacity - self.occupied

    @property
    def is_full(self):
        return self.occupied >= self.capacity

    @property
    def is_empty(self):
        return self.occupied == 0


class Student(models.Model):
    student_number = models.CharField(max_length=30, unique=True)
    full_name      = models.CharField(max_length=120)
    phone_number   = models.CharField(max_length=20)
    gender         = models.CharField(max_length=10)
    national_id    = models.CharField(max_length=50, blank=True)
    date_of_birth  = models.DateField(null=True, blank=True)
    year_of_study  = models.CharField(max_length=10, blank=True)
    department     = models.CharField(max_length=100, blank=True)
    is_src         = models.BooleanField(default=False)
    work_for_fees  = models.BooleanField(default=False)
    sponsored      = models.BooleanField(default=False)
    organisation_name = models.CharField(max_length=100, blank=True)
    condition      = models.CharField(max_length=30, default='None')
    home_address   = models.CharField(max_length=200)
    emergency_contact = models.CharField(max_length=100, blank=True)
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
    room                 = models.ForeignKey('Room', on_delete=models.SET_NULL, null=True, blank=True, related_name='applications')
    room_number          = models.CharField(max_length=20, blank=True, null=True)
    floor_assigned       = models.CharField(max_length=50, blank=True, null=True)
    floor_preference     = models.CharField(max_length=50, blank=True, null=True)
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