from django.core.management.base import BaseCommand
from django.db import transaction
from authentication.models import AdminUser
from accommodation.models import Hostel, Student, AccommodationApplication

class Command(BaseCommand):
    help = 'Seed demo data'

    def handle(self, *args, **options):
        with transaction.atomic():
            self._admins()
            self._hostels()
            self._students()
        self.stdout.write(self.style.SUCCESS('\n✅  Demo data loaded!\n'))

    def _admins(self):
        for e, n, r, p in [
            ('accom@mtc.ac.zw',    'Mrs. T. Chikwanda', 'accommodation', 'accom123'),
            ('dining@mtc.ac.zw',   'Mr. P. Gweshe',     'dining',        'dining123'),
            ('security@mtc.ac.zw', 'Cst. B. Makoni',    'security',      'security123'),
        ]:
            u, created = AdminUser.objects.get_or_create(email=e, defaults={'full_name':n,'role':r,'is_staff':True})
            if created:
                u.set_password(p); u.save()
            self.stdout.write(f"  {'✓' if created else '–'} {e}")

    def _hostels(self):
        for name, gender, loc, beds in [
            ('Tsitsi',  'Female Only', 'North Wing', 500),
            ('Munyati', 'Male Only',   'South Wing', 300),
        ]:
            h, c = Hostel.objects.get_or_create(name=name, defaults={'gender_type':gender,'location':loc,'total_beds':beds,'available_beds':beds})
            self.stdout.write(f"  {'✓' if c else '–'} Hostel: {name}")

    def _students(self):
        tsitsi  = Hostel.objects.get(name='Tsitsi')
        munyati = Hostel.objects.get(name='Munyati')
        for stdno, name, phone, gender, cond, home, hostel, st in [
            ('MTC/2024/001','Chido Moyo',      '0771234567','Female','None',              'Sakubva, Mutare',    tsitsi,  'pending'),
            ('MTC/2024/002','Takudzwa Nhamo',  '0772345678','Male',  'Physical Disability','Dangamvura, Mutare', munyati, 'pending'),
            ('MTC/2024/003','Rudo Chimwemwe',  '0773456789','Female','None',              'Hobhouse, Mutare',   tsitsi,  'approved'),
            ('MTC/2024/004','Farai Mupfumira', '0774567890','Male',  'None',              'Masvingo Town',      munyati, 'approved'),
        ]:
            student, c = Student.objects.get_or_create(student_number=stdno, defaults={'full_name':name,'phone_number':phone,'gender':gender,'condition':cond,'home_address':home})
            if not AccommodationApplication.objects.filter(student=student).exists():
                app = AccommodationApplication.objects.create(student=student, hostel=hostel, status=st)
                if st == 'approved':
                    hostel.available_beds = max(0, hostel.available_beds - 1)
                    hostel.save(update_fields=['available_beds'])
            self.stdout.write(f"  {'✓' if c else '–'} {stdno} {name} ({st})")
