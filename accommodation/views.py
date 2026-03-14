from django.utils import timezone
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny

from .models import Hostel, Student, AccommodationApplication
from .serializers import (
    HostelSerializer, ApplicationSerializer,
    ApplySerializer, StatusSerializer,
)
from authentication.models import AdminUser


class IsAccomAdmin(IsAuthenticated):
    def has_permission(self, request, view):
        return (
            super().has_permission(request, view)
            and request.user.role == AdminUser.Role.ACCOMMODATION
        )


# ── Public ─────────────────────────────────────────────────

class HostelListCreateView(generics.ListCreateAPIView):
    queryset         = Hostel.objects.all()
    serializer_class = HostelSerializer

    def get_permissions(self):
        return [AllowAny()] if self.request.method == 'GET' else [IsAccomAdmin()]


class HostelDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset         = Hostel.objects.all()
    serializer_class = HostelSerializer

    def get_permissions(self):
        return [AllowAny()] if self.request.method == 'GET' else [IsAccomAdmin()]

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        hostel  = self.get_object()
        old_total = hostel.total_beds
        serializer = self.get_serializer(hostel, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        new_total = serializer.validated_data.get('total_beds', old_total)
        if new_total != old_total:
            occupied = old_total - hostel.available_beds
            serializer.validated_data['available_beds'] = max(0, new_total - occupied)
        self.perform_update(serializer)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        hostel = self.get_object()
        active = AccommodationApplication.objects.filter(hostel=hostel, status='approved').count()
        if active:
            return Response(
                {'error': f'Cannot delete "{hostel.name}" — it has {active} approved resident(s). Reject or move them first.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        name = hostel.name
        hostel.delete()
        return Response({'message': f'"{name}" deleted successfully.'})


class ApplyView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        s = ApplySerializer(data=request.data)
        if s.is_valid():
            with transaction.atomic():
                app = s.save()
            return Response(
                {'message': 'Application submitted.', 'reference_number': app.reference_number, 'status': app.status},
                status=status.HTTP_201_CREATED,
            )
        return Response(s.errors, status=status.HTTP_400_BAD_REQUEST)


class StatusView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        q = request.query_params.get('q', '').strip()
        if not q:
            return Response({'error': 'Please provide a student number or reference number.'}, status=400)
        app = (
            AccommodationApplication.objects.select_related('student', 'hostel')
            .filter(student__student_number__iexact=q).first()
            or
            AccommodationApplication.objects.select_related('student', 'hostel')
            .filter(reference_number__iexact=q).first()
        )
        if not app:
            return Response({'error': 'No application found.'}, status=404)
        return Response(StatusSerializer(app).data)


# ── Admin ───────────────────────────────────────────────────

class AdminAppListView(generics.ListAPIView):
    serializer_class   = ApplicationSerializer
    permission_classes = [IsAccomAdmin]

    def get_queryset(self):
        qs = AccommodationApplication.objects.select_related('student', 'hostel', 'processed_by')
        s  = self.request.query_params.get('status')
        return qs.filter(status=s) if s else qs


class ApproveView(APIView):
    permission_classes = [IsAccomAdmin]

    def post(self, request, pk):
        with transaction.atomic():
            app = get_object_or_404(
                AccommodationApplication.objects.select_related('hostel'),
                pk=pk,
            )
            if app.status == 'approved':
                return Response({'error': 'Already approved.'}, status=400)
            if not app.hostel:
                return Response({'error': 'No hostel assigned to this application.'}, status=400)
            if app.hostel.available_beds < 1:
                return Response({'error': f'{app.hostel.name} is full.'}, status=400)

            # Decrement bed count
            app.hostel.available_beds -= 1
            app.hostel.save()   # full save — no update_fields

            # Approve the application — full save, no update_fields restriction
            app.status         = 'approved'
            app.date_processed = timezone.now().date()
            app.processed_by   = request.user
            app.save()

        return Response({
            'message': f'Approved. {app.hostel.name} now has {app.hostel.available_beds} beds left.',
            'reference_number': app.reference_number,
        })


class RejectView(APIView):
    permission_classes = [IsAccomAdmin]

    def post(self, request, pk):
        with transaction.atomic():
            app = get_object_or_404(
                AccommodationApplication.objects.select_related('hostel'),
                pk=pk,
            )
            if app.status == 'rejected':
                return Response({'error': 'Already rejected.'}, status=400)

            # If previously approved, restore the bed
            if app.status == 'approved' and app.hostel:
                app.hostel.available_beds += 1
                app.hostel.save()   # full save

            app.status         = 'rejected'
            app.date_processed = timezone.now().date()
            app.processed_by   = request.user
            app.save()   # full save

        return Response({'message': 'Application rejected.', 'reference_number': app.reference_number})


class ResidentListView(generics.ListAPIView):
    serializer_class   = ApplicationSerializer
    permission_classes = [IsAccomAdmin]

    def get_queryset(self):
        return AccommodationApplication.objects.filter(status='approved').select_related('student', 'hostel')


class DashboardView(APIView):
    permission_classes = [IsAccomAdmin]

    def get(self, request):
        hostels = Hostel.objects.all()
        apps    = AccommodationApplication.objects.all()
        total   = sum(h.total_beds for h in hostels)
        avail   = sum(h.available_beds for h in hostels)
        return Response({
            'total_beds':            total,
            'available_beds':        avail,
            'occupied_beds':         total - avail,
            'pending_count':         apps.filter(status='pending').count(),
            'total_applications':    apps.count(),
            'approved_applications': apps.filter(status='approved').count(),
            'rejected_applications': apps.filter(status='rejected').count(),
            'hostels':               HostelSerializer(hostels, many=True).data,
        })


class NewSemesterView(APIView):
    permission_classes = [IsAccomAdmin]

    def post(self, request):
        if request.data.get('confirm') != 'NEW SEMESTER':
            return Response(
                {'error': 'Send { "confirm": "NEW SEMESTER" } to proceed.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        with transaction.atomic():
            app_count     = AccommodationApplication.objects.count()
            student_count = Student.objects.count()
            AccommodationApplication.objects.all().delete()
            Student.objects.all().delete()
            for hostel in Hostel.objects.all():
                hostel.available_beds = hostel.total_beds
                hostel.save()
        return Response({
            'message':              'New semester reset complete.',
            'applications_deleted': app_count,
            'students_deleted':     student_count,
            'hostels_reset':        Hostel.objects.count(),
        })