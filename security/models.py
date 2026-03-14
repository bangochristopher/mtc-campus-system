## security/models.py
from django.db import models
from accommodation.models import Student

class GateLog(models.Model):
    student         = models.ForeignKey(Student, on_delete=models.SET_NULL, null=True, blank=True, related_name='gate_logs')
    scanned_barcode = models.CharField(max_length=50)
    direction       = models.CharField(max_length=3, choices=[('IN','IN'),('OUT','OUT')])
    is_flagged      = models.BooleanField(default=False)
    flag_reason     = models.CharField(max_length=200, blank=True)
    log_date        = models.DateField()
    log_time        = models.TimeField(auto_now_add=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'gate_log'
        ordering = ['-created_at']
        indexes  = [models.Index(fields=['log_date']), models.Index(fields=['student','log_date'])]
