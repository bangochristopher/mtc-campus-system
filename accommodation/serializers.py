from rest_framework import serializers
from .models import Hostel, Student, AccommodationApplication, Floor, Room


class RoomSerializer(serializers.ModelSerializer):
    available_beds = serializers.SerializerMethodField()
    is_full = serializers.SerializerMethodField()
    is_empty = serializers.SerializerMethodField()
    hostel_name = serializers.SerializerMethodField()
    floor_name = serializers.SerializerMethodField()

    class Meta:
        model = Room
        fields = [
            'id', 'hostel', 'floor', 'room_number', 'capacity', 'occupied', 
            'available_beds', 'status', 'is_full', 'is_empty', 'hostel_name', 'floor_name'
        ]
        read_only_fields = ['id', 'occupied']

    def validate_hostel(self, value):
        """Ensure hostel exists and return the Hostel instance."""
        from .models import Hostel
        
        if value is None:
            raise serializers.ValidationError("Hostel is required.")
        
        # If it's already a Hostel instance, return it
        if isinstance(value, Hostel):
            return value
        
        # Convert to int if it's a string
        if isinstance(value, str):
            try:
                value = int(value)
            except (ValueError, TypeError):
                raise serializers.ValidationError(
                    f"Invalid hostel ID: '{value}'. Expected a number."
                )
        
        # Get and return the Hostel instance
        try:
            hostel = Hostel.objects.get(pk=value)
            return hostel
        except Hostel.DoesNotExist:
            raise serializers.ValidationError(
                f"Hostel with ID {value} does not exist."
            )

    def validate_floor(self, value):
        """Ensure floor exists and return the Floor instance."""
        from .models import Floor
        
        if value is None:
            raise serializers.ValidationError("Floor is required.")
        
        # If it's already a Floor instance, return it
        if isinstance(value, Floor):
            return value
        
        # Convert to int if it's a string
        if isinstance(value, str):
            try:
                value = int(value)
            except (ValueError, TypeError):
                raise serializers.ValidationError(
                    f"Invalid floor ID: '{value}'. Expected a number."
                )
        
        # Get and return the Floor instance
        try:
            floor = Floor.objects.get(pk=value)
            return floor
        except Floor.DoesNotExist:
            raise serializers.ValidationError(
                f"Floor with ID {value} does not exist."
            )

    def validate(self, data):
        """Ensure room number is unique for this hostel."""
        hostel = data.get('hostel')
        room_number = data.get('room_number')
        
        if hostel and room_number:
            existing = Room.objects.filter(hostel=hostel, room_number=room_number)
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise serializers.ValidationError({
                    'room_number': f'A room with number {room_number} already exists in this hostel.'
                })
        
        return data

    def get_available_beds(self, obj):
        return obj.capacity - obj.occupied

    def get_is_full(self, obj):
        return obj.occupied >= obj.capacity

    def get_is_empty(self, obj):
        return obj.occupied == 0

    def get_hostel_name(self, obj):
        try:
            return obj.hostel.name if obj.hostel else None
        except Exception:
            return None

    def get_floor_name(self, obj):
        try:
            floor_names = {
                'ground': 'Ground Floor',
                'first': 'First Floor',
                'second': 'Second Floor',
                'third': 'Third Floor'
            }
            return floor_names.get(obj.floor.name, obj.floor.name) if obj.floor else None
        except Exception:
            return None


class FloorSerializer(serializers.ModelSerializer):
    rooms = RoomSerializer(many=True, read_only=True)

    class Meta:
        model = Floor
        fields = [
            'id', 'hostel', 'name', 'total_beds', 'available_beds', 
            'occupied_beds', 'rooms'
        ]
        read_only_fields = ['id', 'available_beds', 'occupied_beds']

    def validate_hostel(self, value):
        """Ensure hostel exists and return the Hostel instance."""
        from .models import Hostel
        
        if value is None:
            raise serializers.ValidationError("Hostel is required.")
        
        # If it's already a Hostel instance, validate it exists
        if isinstance(value, Hostel):
            return value
        
        # Convert to int if it's a string
        if isinstance(value, str):
            try:
                value = int(value)
            except (ValueError, TypeError):
                raise serializers.ValidationError(
                    f"Invalid hostel ID: '{value}'. Expected a number."
                )
        
        # Get and return the Hostel instance
        try:
            hostel = Hostel.objects.get(pk=value)
            return hostel  # Return the instance, not the ID
        except Hostel.DoesNotExist:
            raise serializers.ValidationError(
                f"Hostel with ID {value} does not exist. Please select a valid hostel."
            )

    def validate(self, data):
        """Ensure floor name is unique for this hostel."""
        hostel = data.get('hostel')
        name = data.get('name')
        
        if hostel and name:
            # Check for existing floor with same name in this hostel
            existing = Floor.objects.filter(hostel=hostel, name=name)
            if self.instance:
                # Updating - exclude current instance
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise serializers.ValidationError({
                    'name': f'A floor with this name already exists in this hostel.'
                })
        
        return data


class HostelSerializer(serializers.ModelSerializer):
    # Computed fields — use SerializerMethodField so they never crash on creation
    occupied_beds     = serializers.SerializerMethodField()
    occupancy_percent = serializers.SerializerMethodField()
    is_full           = serializers.SerializerMethodField()
    floors            = FloorSerializer(many=True, read_only=True)

    class Meta:
        model  = Hostel
        fields = [
            'id', 'name', 'location', 'gender_type',
            'total_beds', 'available_beds',
            'occupied_beds', 'occupancy_percent', 'is_full',
            'floors',
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
            'gender', 'national_id', 'date_of_birth', 'year_of_study',
            'department', 'is_src', 'work_for_fees', 'sponsored',
            'organisation_name', 'condition', 'home_address',
            'emergency_contact', 'barcode_id',
        ]


class ApplicationSerializer(serializers.ModelSerializer):
    student           = StudentSerializer(read_only=True)
    hostel_name       = serializers.SerializerMethodField()
    processed_by_name = serializers.SerializerMethodField()
    room_number       = serializers.CharField(read_only=True)
    floor_assigned    = serializers.CharField(read_only=True)
    room_details      = serializers.SerializerMethodField()

    class Meta:
        model  = AccommodationApplication
        fields = [
            'id', 'reference_number', 'student',
            'hostel', 'hostel_name',
            'room', 'room_number', 'floor_assigned', 'room_details',
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
    
    def get_room_details(self, obj):
        try:
            if obj.room:
                return {
                    'id': obj.room.id,
                    'room_number': obj.room.room_number,
                    'floor': obj.room.floor.name if obj.room.floor else None,
                    'capacity': obj.room.capacity,
                    'occupied': obj.room.occupied,
                }
            return None
        except Exception:
            return None


class ApplySerializer(serializers.Serializer):
    student_number       = serializers.CharField(max_length=30)
    full_name            = serializers.CharField(max_length=120)
    phone_number         = serializers.CharField(max_length=20)
    gender               = serializers.ChoiceField(choices=['Male', 'Female'])
    national_id          = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    date_of_birth        = serializers.DateField(required=False, allow_null=True)
    address              = serializers.CharField(max_length=200, required=False, allow_blank=True, allow_null=True)
    emergency_contact    = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    year                 = serializers.CharField(max_length=10, required=False, allow_blank=True, allow_null=True)
    department           = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    type                 = serializers.ChoiceField(choices=['student', 'worker'], required=False, default='student')
    badges               = serializers.JSONField(required=False, default=dict)
    condition            = serializers.CharField(required=False, allow_blank=True, allow_null=True, default='None')
    home_address         = serializers.CharField(max_length=200)
    hostel_id            = serializers.IntegerField(required=False, allow_null=True)
    room_id              = serializers.IntegerField(required=False, allow_null=True)
    floor_preference     = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    special_requirements = serializers.CharField(required=False, allow_blank=True, allow_null=True, default='')
    notes                = serializers.CharField(required=False, allow_blank=True, allow_null=True, default='')

    def validate_student_number(self, value):
        if Student.objects.filter(student_number=value).exists():
            raise serializers.ValidationError(
                'An application already exists for this student number.'
            )
        return value

    def validate(self, data):
        hid = data.get('hostel_id')
        room_id = data.get('room_id')
        
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
        
        # Validate room selection if provided
        if room_id:
            from .models import Room
            try:
                room = Room.objects.select_related('hostel', 'floor').get(pk=room_id)
                # Check if room has available beds
                if room.occupied >= room.capacity:
                    raise serializers.ValidationError({
                        'room_id': f'Room {room.room_number} is full. Please select another room.'
                    })
                # Check if room belongs to selected hostel
                if hid and room.hostel_id != hid:
                    raise serializers.ValidationError({
                        'room_id': 'Selected room does not belong to the selected hostel.'
                    })
                data['room'] = room
                # Set floor preference from room's floor
                data['floor_preference'] = room.floor.name
            except Room.DoesNotExist:
                raise serializers.ValidationError({'room_id': 'Selected room does not exist.'})
        
        return data

    def create(self, validated_data):
        hostel = validated_data.pop('hostel', None)
        room = validated_data.pop('room', None)
        floor_pref = validated_data.pop('floor_preference', None)
        validated_data.pop('hostel_id', None)
        validated_data.pop('room_id', None)
        badges = validated_data.pop('badges', {})
        validated_data.pop('type', None)
        year = validated_data.pop('year', '')
        department = validated_data.pop('department', '')
        national_id = validated_data.pop('national_id', '')
        date_of_birth = validated_data.pop('date_of_birth', None)
        address = validated_data.pop('address', '')
        emergency_contact = validated_data.pop('emergency_contact', '')
        
        student = Student.objects.create(
            student_number=validated_data['student_number'],
            full_name=validated_data['full_name'],
            phone_number=validated_data['phone_number'],
            gender=validated_data['gender'],
            national_id=national_id,
            date_of_birth=date_of_birth,
            year_of_study=year,
            department=department,
            is_src=badges.get('src', False),
            work_for_fees=badges.get('fees', False),
            sponsored=badges.get('org', False),
            organisation_name=badges.get('organisation_name') or '',  # Convert null to empty string
            condition=validated_data.get('condition', 'None'),
            home_address=validated_data['home_address'],
            emergency_contact=emergency_contact,
        )
        return AccommodationApplication.objects.create(
            student=student,
            hostel=hostel,
            room=room,  # Save the selected room
            floor_preference=floor_pref,
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
    room_number    = serializers.CharField()
    floor          = serializers.CharField(source='floor_assigned')

    class Meta:
        model  = AccommodationApplication
        fields = [
            'reference_number', 'student_number', 'full_name',
            'phone_number', 'gender', 'condition', 'home_address',
            'hostel_name', 'special_requirements',
            'status', 'date_applied', 'date_processed',
            'room_number', 'floor',
        ]

    def get_hostel_name(self, obj):
        try:
            return obj.hostel.name if obj.hostel else None
        except Exception:
            return None