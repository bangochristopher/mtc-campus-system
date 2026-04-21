from django.utils import timezone
from datetime import timedelta, datetime, date
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

        if not barcode or not meal_type:
            return Response(
                {'error': 'barcode and meal_type are required.'},
                status=400
            )

        # ── FIND STUDENT ───────────────────────────────────────────────────
        student = Student.objects.filter(
            student_number__iexact=barcode
        ).first()

        # Student not in database
        if not student:
            MealRegister.objects.create(
                student=None,
                meal_type=meal_type,
                scan_status='denied',
                scanned_barcode=barcode,
                scan_date=today
            )
            return Response({
                'access': 'denied',
                'message': 'Student not found, access denied'
            }, status=403)

        # ── CHECK ACCOMMODATION APPROVAL ───────────────────────────────────
        try:
            app = student.application
        except AccommodationApplication.DoesNotExist:
            app = None
        
        if app is None or app.status != 'approved':
            MealRegister.objects.create(
                student=student,
                meal_type=meal_type,
                scan_status='denied',
                scanned_barcode=barcode,
                scan_date=today
            )
            return Response({
                'access': 'denied',
                'message': 'Student not approved for meals'
            }, status=403)

        # ── CHECK DUPLICATE MEAL ──────────────────────────────────────────
        already = MealRegister.objects.filter(
            student=student,
            meal_type=meal_type,
            scan_date=today,
            scan_status='served'
        ).first()

        # Already ate
        if already:
            MealRegister.objects.create(
                student=student,
                meal_type=meal_type,
                scan_status='duplicate',
                scanned_barcode=barcode,
                scan_date=today
            )
            return Response({
                'access': 'denied',
                'message': 'Student already ate'
            }, status=403)

        # ── SERVE THE MEAL ─────────────────────────────────────────────────
        record = MealRegister.objects.create(
            student=student,
            meal_type=meal_type,
            scan_status='served',
            scanned_barcode=barcode,
            scan_date=today
        )
        return Response({
            'access': 'granted',
            'message': 'Access granted'
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
