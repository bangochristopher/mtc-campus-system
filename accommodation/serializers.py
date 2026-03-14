from rest_framework import serializers
from .models import Hostel, Student, AccommodationApplication


class HostelSerializer(serializers.ModelSerializer):
    # Computed fields — use SerializerMethodField so they never crash on creation
    occupied_beds     = serializers.SerializerMethodField()
    occupancy_percent = serializers.SerializerMethodField()
    is_full           = serializers.SerializerMethodField()

    class Meta:
        model  = Hostel
        fields = [
            'id', 'name', 'location', 'gender_type',
            'total_beds', 'available_beds',
            'occupied_beds', 'occupancy_percent', 'is_full',
        ]
        read_only_fields = ['id', 'available_beds']

    def get_occupied_beds(self, obj):
        return obj.total_beds - obj.available_beds

    def get_occupancy_percent(self, obj):
        if not obj.total_beds:
            return 0
        return round(((obj.total_beds - obj.available_beds) / obj.total_beds) * 100)

    def get_is_full(self, obj):
        return obj.available_beds == 0


class StudentSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Student
        fields = [
            'id', 'student_number', 'full_name', 'phone_number',
            'gender', 'condition', 'home_address', 'barcode_id',
        ]


class ApplicationSerializer(serializers.ModelSerializer):
    student           = StudentSerializer(read_only=True)
    hostel_name       = serializers.SerializerMethodField()
    processed_by_name = serializers.SerializerMethodField()

    class Meta:
        model  = AccommodationApplication
        fields = [
            'id', 'reference_number', 'student',
            'hostel', 'hostel_name',
            'special_requirements', 'notes', 'status',
            'date_applied', 'date_processed',
            'processed_by', 'processed_by_name',
        ]
        read_only_fields = ['id', 'reference_number', 'date_applied']

    def get_hostel_name(self, obj):
        try:
            return obj.hostel.name if obj.hostel else None
        except Exception:
            return None

    def get_processed_by_name(self, obj):
        try:
            return obj.processed_by.full_name if obj.processed_by else None
        except Exception:
            return None


class ApplySerializer(serializers.Serializer):
    student_number       = serializers.CharField(max_length=30)
    full_name            = serializers.CharField(max_length=120)
    phone_number         = serializers.CharField(max_length=20)
    gender               = serializers.ChoiceField(choices=['Male', 'Female'])
    condition            = serializers.CharField(required=False, default='None')
    home_address         = serializers.CharField(max_length=200)
    hostel_id            = serializers.IntegerField(required=False, allow_null=True)
    special_requirements = serializers.CharField(required=False, allow_blank=True, default='')
    notes                = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_student_number(self, value):
        if Student.objects.filter(student_number=value).exists():
            raise serializers.ValidationError(
                'An application already exists for this student number.'
            )
        return value

    def validate(self, data):
        hid = data.get('hostel_id')
        if hid:
            try:
                h = Hostel.objects.get(pk=hid)
            except Hostel.DoesNotExist:
                raise serializers.ValidationError({'hostel_id': 'Hostel does not exist.'})
            g = data.get('gender')
            if h.gender_type == 'Female Only' and g == 'Male':
                raise serializers.ValidationError(
                    {'hostel_id': 'This hostel is for female students only.'}
                )
            if h.gender_type == 'Male Only' and g == 'Female':
                raise serializers.ValidationError(
                    {'hostel_id': 'This hostel is for male students only.'}
                )
            if h.available_beds == 0:
                raise serializers.ValidationError({'hostel_id': f'{h.name} is full.'})
            data['hostel'] = h
        return data

    def create(self, validated_data):
        hostel = validated_data.pop('hostel', None)
        validated_data.pop('hostel_id', None)
        student = Student.objects.create(
            student_number=validated_data['student_number'],
            full_name=validated_data['full_name'],
            phone_number=validated_data['phone_number'],
            gender=validated_data['gender'],
            condition=validated_data.get('condition', 'None'),
            home_address=validated_data['home_address'],
        )
        return AccommodationApplication.objects.create(
            student=student,
            hostel=hostel,
            special_requirements=validated_data.get('special_requirements', ''),
            notes=validated_data.get('notes', ''),
        )


class StatusSerializer(serializers.ModelSerializer):
    student_number = serializers.CharField(source='student.student_number')
    full_name      = serializers.CharField(source='student.full_name')
    phone_number   = serializers.CharField(source='student.phone_number')
    gender         = serializers.CharField(source='student.gender')
    condition      = serializers.CharField(source='student.condition')
    home_address   = serializers.CharField(source='student.home_address')
    hostel_name    = serializers.SerializerMethodField()

    class Meta:
        model  = AccommodationApplication
        fields = [
            'reference_number', 'student_number', 'full_name',
            'phone_number', 'gender', 'condition', 'home_address',
            'hostel_name', 'special_requirements',
            'status', 'date_applied', 'date_processed',
        ]

    def get_hostel_name(self, obj):
        try:
            return obj.hostel.name if obj.hostel else None
        except Exception:
            return None