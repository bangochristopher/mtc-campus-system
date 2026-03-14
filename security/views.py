from django.utils import timezone
from django.db.models import Q
from rest_framework import generics, serializers
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from .models import GateLog
from accommodation.models import Student
from authentication.models import AdminUser


class IsSecurityAdmin(IsAuthenticated):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.role == AdminUser.Role.SECURITY


class GateLogSerializer(serializers.ModelSerializer):
    student_number = serializers.CharField(source='student.student_number', read_only=True, default=None)
    student_name   = serializers.CharField(source='student.full_name',      read_only=True, default=None)
    hostel = serializers.SerializerMethodField()
    class Meta:
        model  = GateLog
        fields = ['id','student','student_number','student_name','hostel','scanned_barcode','direction','is_flagged','flag_reason','log_date','log_time']
    def get_hostel(self, obj):
        try:
            return obj.student.application.hostel.name if obj.student else None
        except Exception:
            return None


class ScanView(APIView):
    permission_classes = [IsSecurityAdmin]

    def post(self, request):
        barcode   = request.data.get('barcode','').strip()
        direction = request.data.get('direction','IN')
        today     = timezone.localdate()

        if not barcode:
            return Response({'error': 'barcode is required.'}, status=400)

        student = (Student.objects.filter(barcode_id__iexact=barcode).first()
                   or Student.objects.filter(student_number__iexact=barcode).first())

        if student:
            log = GateLog.objects.create(student=student, scanned_barcode=barcode, direction=direction, is_flagged=False, log_date=today)
            try:
                hostel = student.application.hostel.name if student.application.hostel else None
            except Exception:
                hostel = None
            return Response({'result':'logged','direction':direction,'message':f'{student.full_name} — {direction} logged.','student':{'name':student.full_name,'number':student.student_number,'hostel':hostel},'log':GateLogSerializer(log).data})
        else:
            log = GateLog.objects.create(student=None, scanned_barcode=barcode, direction=direction, is_flagged=True, flag_reason=f'Unknown barcode "{barcode}"', log_date=today)
            return Response({'result':'flagged','direction':direction,'message':f'Unknown barcode "{barcode}" — flagged as security incident.','log':GateLogSerializer(log).data})


class LogListView(generics.ListAPIView):
    serializer_class   = GateLogSerializer
    permission_classes = [IsSecurityAdmin]
    def get_queryset(self):
        qs = GateLog.objects.select_related('student','student__application__hostel')
        if d := self.request.query_params.get('date'):     qs = qs.filter(log_date=d)
        if dr := self.request.query_params.get('direction'): qs = qs.filter(direction=dr)
        if f := self.request.query_params.get('flagged'):  qs = qs.filter(is_flagged=True) if f=='true' else qs
        if q := self.request.query_params.get('student'):  qs = qs.filter(Q(student__student_number__icontains=q)|Q(student__full_name__icontains=q))
        return qs


class OnCampusView(APIView):
    permission_classes = [IsSecurityAdmin]
    def get(self, request):
        today = timezone.localdate()
        logs  = GateLog.objects.filter(log_date=today, is_flagged=False, student__isnull=False).select_related('student','student__application__hostel')
        counts = {}
        for l in logs:
            sid = l.student_id
            if sid not in counts:
                counts[sid] = {'student':l.student,'in':0,'out':0,'last_in':None}
            if l.direction == 'IN':
                counts[sid]['in'] += 1; counts[sid]['last_in'] = str(l.log_time)[:5]
            else:
                counts[sid]['out'] += 1
        on_campus = [{'student_number':v['student'].student_number,'full_name':v['student'].full_name,'hostel':None,'entry_time':v['last_in']} for v in counts.values() if v['in'] > v['out']]
        return Response({'count':len(on_campus),'students':on_campus})


class IncidentListView(generics.ListAPIView):
    serializer_class   = GateLogSerializer
    permission_classes = [IsSecurityAdmin]
    def get_queryset(self):
        return GateLog.objects.filter(is_flagged=True).order_by('-created_at')


class DashboardView(APIView):
    permission_classes = [IsSecurityAdmin]
    def get(self, request):
        today = timezone.localdate()
        logs  = GateLog.objects.filter(log_date=today)
        counts = {}
        for l in GateLog.objects.filter(log_date=today, is_flagged=False, student__isnull=False):
            sid = l.student_id
            if sid not in counts: counts[sid] = {'in':0,'out':0}
            counts[sid]['in' if l.direction=='IN' else 'out'] += 1
        on_campus = sum(1 for v in counts.values() if v['in'] > v['out'])
        return Response({
            'today': str(today),
            'on_campus':        on_campus,
            'today_entries':    logs.filter(direction='IN').count(),
            'today_exits':      logs.filter(direction='OUT').count(),
            'today_incidents':  logs.filter(is_flagged=True).count(),
            'total_incidents':  GateLog.objects.filter(is_flagged=True).count(),
            'recent_logs':      GateLogSerializer(logs.select_related('student').order_by('-created_at')[:15], many=True).data,
        })


class NewTermView(APIView):
    permission_classes = [IsSecurityAdmin]

    def post(self, request):
        if request.data.get('confirm') != 'NEW TERM':
            return Response(
                {'error': 'Send { "confirm": "NEW TERM" } to proceed.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        count = GateLog.objects.count()
        GateLog.objects.all().delete()
        return Response({
            'message':         'New term reset complete. All gate log records deleted.',
            'records_deleted': count,
        })