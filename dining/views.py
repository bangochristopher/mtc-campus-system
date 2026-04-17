from django.utils import timezone
from datetime import timedelta
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import serializers

from .models import MealRegister
from accommodation.models import Student, AccommodationApplication
from authentication.models import AdminUser


class IsDiningAdmin(IsAuthenticated):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.role == AdminUser.Role.DINING


class MealRegisterSerializer(serializers.ModelSerializer):
    student_number = serializers.CharField(source='student.student_number', read_only=True, default=None)
    student_name   = serializers.CharField(source='student.full_name',      read_only=True, default=None)
    hostel = serializers.SerializerMethodField()
    class Meta:
        model  = MealRegister
        fields = ['id','student','student_number','student_name','hostel','meal_type','scan_status','scanned_barcode','scan_date','scan_time']
    def get_hostel(self, obj):
        try:
            return obj.student.application.hostel.name if obj.student else None
        except Exception:
            return None


class ScanView(APIView):
    permission_classes = [IsDiningAdmin]

    def post(self, request):
        barcode   = request.data.get('barcode', '').strip()
        meal_type = request.data.get('meal_type', '')
        today     = timezone.localdate()
        now       = timezone.now()

        if not barcode or not meal_type:
            return Response(
                {'error': 'barcode and meal_type are required.'},
                status=400
            )

        # ── DOUBLE SCAN GUARD ──────────────────────────────────────────────
        # If the exact same barcode was scanned less than 3 seconds ago,
        # it is a hardware double-scan — silently ignore it.
        three_seconds_ago = now - timedelta(seconds=3)
        recent = MealRegister.objects.filter(
            scanned_barcode__iexact=barcode,
            scan_date=today,
        ).filter(
            # created_at is within last 3 seconds
            id__in=MealRegister.objects.filter(
                scanned_barcode__iexact=barcode,
                scan_date=today,
            ).order_by('-id').values_list('id', flat=True)[:1]
        ).first()

        if recent:
            # Check if it was created within 3 seconds using scan_time
            from datetime import datetime, date
            import datetime as dt
            last_scan_datetime = datetime.combine(
                date.today(),
                recent.scan_time
            )
            last_scan_datetime = timezone.make_aware(last_scan_datetime)
            seconds_since = (now - last_scan_datetime).total_seconds()

            if seconds_since < 3:
                # This is a hardware double scan — return the same result
                # as the first scan without creating a new record
                return Response({
                    'access':  'double_scan_ignored',
                    'message': 'Double scan detected and ignored.',
                }, status=200)
        # ──────────────────────────────────────────────────────────────────

        # ── FIND STUDENT ───────────────────────────────────────────────────
        student = Student.objects.filter(
            student_number__iexact=barcode
        ).first()

        if not student:
            MealRegister.objects.create(
                student=None,
                meal_type=meal_type,
                scan_status='denied',
                scanned_barcode=barcode,
                scan_date=today
            )
            return Response({
                'access':  'denied',
                'reason':  'not_found',
                'message': f'Barcode "{barcode}" not found in the student database.'
            }, status=403)

        # ── CHECK ACCOMMODATION APPROVAL ───────────────────────────────────
        try:
            app = student.application
            if app.status != 'approved':
                MealRegister.objects.create(
                    student=student,
                    meal_type=meal_type,
                    scan_status='denied',
                    scanned_barcode=barcode,
                    scan_date=today
                )
                return Response({
                    'access':  'denied',
                    'reason':  'not_approved',
                    'message': f'{student.full_name} does not have an approved accommodation application.'
                }, status=403)
        except AccommodationApplication.DoesNotExist:
            MealRegister.objects.create(
                student=student,
                meal_type=meal_type,
                scan_status='denied',
                scanned_barcode=barcode,
                scan_date=today
            )
            return Response({
                'access':  'denied',
                'reason':  'no_application',
                'message': f'{student.full_name} has no accommodation application.'
            }, status=403)

        # ── CHECK DUPLICATE MEAL (same meal period today) ──────────────────
        already = MealRegister.objects.filter(
            student=student,
            meal_type=meal_type,
            scan_date=today,
            scan_status='served'
        ).first()

        if already:
            MealRegister.objects.create(
                student=student,
                meal_type=meal_type,
                scan_status='duplicate',
                scanned_barcode=barcode,
                scan_date=today
            )
            return Response({
                'access':      'duplicate',
                'message':     f'{student.full_name} was already served {meal_type} today at {str(already.scan_time)[:5]}.',
                'served_at':   str(already.scan_time)[:5],
                'student': {
                    'name':   student.full_name,
                    'number': student.student_number,
                }
            }, status=409)

        # ── SERVE THE MEAL ─────────────────────────────────────────────────
        record = MealRegister.objects.create(
            student=student,
            meal_type=meal_type,
            scan_status='served',
            scanned_barcode=barcode,
            scan_date=today
        )
        return Response({
            'access':  'granted',
            'message': f'{student.full_name} — {meal_type} served.',
            'student': {
                'name':    student.full_name,
                'number':  student.student_number,
                'hostel':  app.hostel.name if app.hostel else None,
                'gender':  student.gender,
                'condition': student.condition,
            },
            'record': MealRegisterSerializer(record).data
        })


class RegisterListView(generics.ListAPIView):
    serializer_class   = MealRegisterSerializer
    permission_classes = [IsDiningAdmin]

    def get_queryset(self):
        qs = MealRegister.objects.select_related('student', 'student__application__hostel')
        if d := self.request.query_params.get('date'):   qs = qs.filter(scan_date=d)
        if m := self.request.query_params.get('meal'):   qs = qs.filter(meal_type=m)
        if s := self.request.query_params.get('status'): qs = qs.filter(scan_status=s)
        return qs


class DashboardView(APIView):
    permission_classes = [IsDiningAdmin]

    def get(self, request):
        today    = timezone.localdate()
        records  = MealRegister.objects.filter(scan_date=today)
        served   = records.filter(scan_status='served')
        eligible = AccommodationApplication.objects.filter(status='approved').count()
        return Response({
            'today':              str(today),
            'eligible_students':  eligible,
            'today_breakfast':    served.filter(meal_type='Breakfast').count(),
            'today_lunch':        served.filter(meal_type='Lunch').count(),
            'today_supper':       served.filter(meal_type='Supper').count(),
            'today_total_served': served.count(),
            'today_denied':       records.filter(scan_status='denied').count(),
            'today_duplicates':   records.filter(scan_status='duplicate').count(),
            'recent_scans':       MealRegisterSerializer(
                records.order_by('-created_at')[:15], many=True
            ).data,
        })


class EligibleView(APIView):
    permission_classes = [IsDiningAdmin]

    def get(self, request):
        apps = AccommodationApplication.objects.filter(
            status='approved'
        ).select_related('student', 'hostel')
        students = [{
            'student_number': a.student.student_number,
            'full_name':      a.student.full_name,
            'hostel':         a.hostel.name if a.hostel else None,
            'gender':         a.student.gender,
            'barcode_id':     a.student.barcode_id,
        } for a in apps]
        return Response({'count': len(students), 'students': students})


class NewTermView(APIView):
    permission_classes = [IsDiningAdmin]

    def post(self, request):
        if request.data.get('confirm') != 'NEW TERM':
            return Response(
                {'error': 'Send { "confirm": "NEW TERM" } to proceed.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        count = MealRegister.objects.count()
        MealRegister.objects.all().delete()
        return Response({
            'message':         'New term reset complete. All meal records deleted.',
            'records_deleted': count,
        })
