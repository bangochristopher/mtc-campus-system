from django.utils import timezone
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import generics, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny

from .models import Hostel, Student, AccommodationApplication, Floor, Room
from .serializers import (
    HostelSerializer, ApplicationSerializer,
    ApplySerializer, StatusSerializer,
    FloorSerializer, RoomSerializer,
)
from authentication.models import AdminUser


class IsAccomAdmin(IsAuthenticated):
    def has_permission(self, request, view):
        # TEMPORARY: Allow all requests for development
        # TODO: Re-enable authentication for production
        return True
        # Original authentication check:
        # return (
        #     super().has_permission(request, view)
        #     and request.user.role == AdminUser.Role.ACCOMMODATION
        # )


# ── Public ─────────────────────────────────────────────────

class HostelListCreateView(generics.ListCreateAPIView):
    queryset         = Hostel.objects.all()
    serializer_class = HostelSerializer

    def get_permissions(self):
        return [AllowAny()] if self.request.method == 'GET' else [IsAccomAdmin()]
    
    def perform_create(self, serializer):
        """Create hostel with 0 beds initially - beds will be added when rooms are created."""
        hostel = serializer.save()
        # Reset beds to 0 - they will be calculated from rooms
        hostel.total_beds = 0
        hostel.available_beds = 0
        hostel.save()


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


class RoomReservationsView(APIView):
    """Public endpoint to get room reservation status with effective availability."""
    permission_classes = [AllowAny]
    
    def get(self, request):
        from .serializers import RoomSerializer
        
        # Get all rooms with their hostels and floors
        rooms = Room.objects.select_related('hostel', 'floor').all()
        
        # Get all pending and approved applications
        reservations = AccommodationApplication.objects.filter(
            status__in=['pending', 'approved'],
            room__isnull=False
        ).values('room_id', 'status')
        
        # Group by room_id
        reservation_counts = {}
        for res in reservations:
            room_id = res['room_id']
            if room_id not in reservation_counts:
                reservation_counts[room_id] = {'pending': 0, 'approved': 0}
            if res['status'] == 'pending':
                reservation_counts[room_id]['pending'] += 1
            elif res['status'] == 'approved':
                reservation_counts[room_id]['approved'] += 1
        
        # Build response with effective availability
        room_data = []
        for room in rooms:
            counts = reservation_counts.get(room.id, {'pending': 0, 'approved': 0})
            
            # Calculate effective availability
            effective_available = max(0, room.capacity - counts['approved'] - counts['pending'])
            effective_occupied = room.capacity - effective_available
            is_full = effective_available == 0
            is_empty = effective_occupied == 0
            
            room_data.append({
                'id': room.id,
                'hostel_id': room.hostel_id,
                'floor_id': room.floor_id,
                'room_number': room.room_number,
                'capacity': room.capacity,
                'occupied': room.occupied,  # Database count (approved only)
                'pending_reservations': counts['pending'],
                'approved_reservations': counts['approved'],
                'effective_occupied': effective_occupied,
                'effective_available': effective_available,
                'is_full': is_full,
                'is_empty': is_empty,
            })
        
        return Response(room_data)


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
                AccommodationApplication.objects.select_related('hostel', 'room'),
                pk=pk,
            )
            if app.status == 'approved':
                return Response({'error': 'Already approved.'}, status=400)
            if not app.hostel:
                return Response({'error': 'No hostel assigned to this application.'}, status=400)
            
            # Check if student selected a specific room during application
            if app.room:
                # Use the student's selected room
                selected_room = app.room
                
                # Check if room is still available
                if selected_room.occupied >= selected_room.capacity:
                    return Response({
                        'error': f'Room {selected_room.room_number} is now full. Please select another room.'
                    }, status=400)
                
                # Assign room number from the selected room
                room_number = selected_room.room_number
                floor_assigned = selected_room.floor.name if selected_room.floor else 'ground'
                
                # Increment room occupancy
                selected_room.occupied += 1
                selected_room.save()
                
                # Update floor available beds
                if selected_room.floor:
                    selected_room.floor.available_beds = max(0, selected_room.floor.available_beds - 1)
                    selected_room.floor.save()
            else:
                # Auto-generate room number (legacy behavior for applications without room selection)
                if app.hostel.available_beds < 1:
                    return Response({'error': f'{app.hostel.name} is full.'}, status=400)
                
                floor_pref = 'G'  # Default ground floor
                if hasattr(app, 'floor_preference'):
                    floor_map = {'ground': 'G', 'first': 'F', 'second': 'S'}
                    floor_pref = floor_map.get(app.floor_preference, 'G')
                
                # Generate next available room number for this hostel
                approved_in_hostel = AccommodationApplication.objects.filter(
                    hostel=app.hostel,
                    status='approved',
                    room_number__isnull=False
                ).order_by('-room_number').first()
                
                if approved_in_hostel and approved_in_hostel.room_number:
                    try:
                        last_num = int(approved_in_hostel.room_number[1:])
                        new_num = last_num + 1
                    except:
                        new_num = 1
                else:
                    new_num = 1
                
                room_number = f'{floor_pref}{new_num:02d}'
                floor_assigned = app.floor_preference if hasattr(app, 'floor_preference') else 'ground'
                
                # Decrement hostel bed count (only for auto-assigned rooms)
                app.hostel.available_beds -= 1
                app.hostel.save()

            # Approve the application with room assignment
            app.status         = 'approved'
            app.room_number    = room_number
            app.floor_assigned = floor_assigned
            app.date_processed = timezone.now().date()
            
            # Set processed_by only if user is authenticated (not anonymous)
            if request.user.is_authenticated and hasattr(request.user, 'role'):
                app.processed_by = request.user
            
            app.save()

        return Response({
            'message': f'Approved. Room {room_number} assigned at {app.hostel.name}. {app.hostel.name} now has {app.hostel.available_beds} beds left.',
            'reference_number': app.reference_number,
            'room_number': room_number,
        })


class RejectView(APIView):
    permission_classes = [IsAccomAdmin]

    def post(self, request, pk):
        with transaction.atomic():
            app = get_object_or_404(
                AccommodationApplication.objects.select_related('hostel', 'room'),
                pk=pk,
            )
            if app.status == 'rejected':
                return Response({'error': 'Already rejected.'}, status=400)

            # If previously approved, restore the bed/room occupancy
            if app.status == 'approved':
                # If student was assigned to a specific room, decrement room occupancy
                if app.room:
                    app.room.occupied = max(0, app.room.occupied - 1)
                    app.room.save()
                    
                    # Update floor counts
                    if app.room.floor:
                        app.room.floor.available_beds += 1
                        app.room.floor.save()
                # If auto-assigned (legacy), restore hostel bed
                elif app.hostel:
                    app.hostel.available_beds += 1
                    app.hostel.save()

            app.status         = 'rejected'
            app.date_processed = timezone.now().date()
            
            # Set processed_by only if user is authenticated (not anonymous)
            if request.user.is_authenticated and hasattr(request.user, 'role'):
                app.processed_by = request.user
            
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
        try:
            hostels = Hostel.objects.all()
            apps    = AccommodationApplication.objects.all()
            total   = sum(h.total_beds for h in hostels)
            avail   = sum(h.available_beds for h in hostels)
            
            # Serialize hostels with error handling
            try:
                hostels_data = HostelSerializer(hostels, many=True).data
            except Exception as e:
                print(f"❌ Error serializing hostels: {e}")
                import traceback
                traceback.print_exc()
                # Return hostels without floors if serialization fails
                hostels_data = []
                for h in hostels:
                    hostels_data.append({
                        'id': h.id,
                        'name': h.name,
                        'location': h.location,
                        'gender_type': h.gender_type,
                        'total_beds': h.total_beds,
                        'available_beds': h.available_beds,
                        'occupied_beds': h.total_beds - h.available_beds,
                        'occupancy_percent': round(((h.total_beds - h.available_beds) / h.total_beds) * 100) if h.total_beds > 0 else 0,
                        'is_full': h.available_beds == 0,
                        'floors': []
                    })
            
            return Response({
                'total_beds':            total,
                'available_beds':        avail,
                'occupied_beds':         total - avail,
                'pending_count':         apps.filter(status='pending').count(),
                'total_applications':    apps.count(),
                'approved_applications': apps.filter(status='approved').count(),
                'rejected_applications': apps.filter(status='rejected').count(),
                'hostels':               hostels_data,
            })
        except Exception as e:
            print(f"❌ DashboardView error: {e}")
            import traceback
            traceback.print_exc()
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class NewSemesterView(APIView):
    permission_classes = [IsAccomAdmin]

    def post(self, request):
        if request.data.get('confirm') != 'NEW SEMESTER':
            return Response(
                {'error': 'Send { "confirm": "NEW SEMESTER" } to proceed.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        with transaction.atomic():
            # Count records before deletion
            app_count     = AccommodationApplication.objects.count()
            student_count = Student.objects.count()
            room_count    = Room.objects.count()
            floor_count   = Floor.objects.count()
            
            # Delete all applications and students
            AccommodationApplication.objects.all().delete()
            Student.objects.all().delete()
            
            # Reset all room occupancy to 0
            Room.objects.update(occupied=0)
            
            # Reset all floor bed counts
            for floor in Floor.objects.all():
                floor.available_beds = floor.total_beds
                floor.save()
            
            # Reset all hostel bed counts
            for hostel in Hostel.objects.all():
                hostel.available_beds = hostel.total_beds
                hostel.save()
                
        return Response({
            'message':              'New semester reset complete.',
            'applications_deleted': app_count,
            'students_deleted':     student_count,
            'rooms_reset':          room_count,
            'floors_reset':         floor_count,
            'hostels_reset':        Hostel.objects.count(),
        })


class RecalculateBedsView(APIView):
    """Recalculate all bed counts from rooms to fix any inconsistencies."""
    permission_classes = [IsAccomAdmin]
    
    def post(self, request):
        with transaction.atomic():
            results = []
            
            for hostel in Hostel.objects.all():
                # Calculate from rooms
                rooms = Room.objects.filter(hostel=hostel)
                total_beds = sum(room.capacity for room in rooms)
                occupied_beds = sum(room.occupied for room in rooms)
                available_beds = total_beds - occupied_beds
                
                # Update hostel
                old_total = hostel.total_beds
                old_avail = hostel.available_beds
                hostel.total_beds = total_beds
                hostel.available_beds = max(0, available_beds)
                hostel.save()
                
                # Update each floor
                for floor in Floor.objects.filter(hostel=hostel):
                    floor_rooms = Room.objects.filter(floor=floor)
                    floor.total_beds = sum(room.capacity for room in floor_rooms)
                    floor_occupied = sum(room.occupied for room in floor_rooms)
                    floor.available_beds = max(0, floor.total_beds - floor_occupied)
                    floor.save()
                
                results.append({
                    'hostel': hostel.name,
                    'old_beds': old_total,
                    'new_beds': total_beds,
                    'occupied': occupied_beds,
                    'available': hostel.available_beds
                })
        
        return Response({
            'message': 'Bed counts recalculated successfully.',
            'hostels': results
        })


# ── Floor Management ────────────────────────────────────────

class FloorListCreateView(generics.ListCreateAPIView):
    serializer_class   = FloorSerializer
    permission_classes = [IsAccomAdmin]

    def get_queryset(self):
        hostel_id = self.request.query_params.get('hostel_id')
        qs = Floor.objects.select_related('hostel').prefetch_related('rooms')
        if hostel_id:
            qs = qs.filter(hostel_id=hostel_id)
        return qs

    def perform_create(self, serializer):
        hostel_id = self.request.data.get('hostel')
        if not hostel_id:
            raise serializers.ValidationError({'hostel': 'Hostel ID is required.'})
        
        with transaction.atomic():
            floor = serializer.save()
            # Don't update hostel beds here - beds are counted from rooms, not floors
            # Floor beds will be calculated from its rooms


class FloorDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset         = Floor.objects.select_related('hostel').prefetch_related('rooms')
    serializer_class = FloorSerializer
    permission_classes = [IsAccomAdmin]

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        floor = self.get_object()
        old_total = floor.total_beds
        
        serializer = self.get_serializer(floor, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        
        # Don't update hostel beds here - only rooms should affect bed counts
        self.perform_update(serializer)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        floor = self.get_object()
        # Check if floor has any approved applications
        approved = AccommodationApplication.objects.filter(
            hostel=floor.hostel,
            floor_assigned=floor.name,
            status='approved'
        ).count()
        
        if approved:
            return Response(
                {'error': f'Cannot delete floor with {approved} approved resident(s).'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Don't update hostel beds - rooms will handle this when deleted
        floor.delete()
        
        return Response({'message': 'Floor deleted successfully.'})


# ── Room Management ─────────────────────────────────────────

class RoomListCreateView(generics.ListCreateAPIView):
    serializer_class   = RoomSerializer
    permission_classes = [IsAccomAdmin]

    def get_queryset(self):
        hostel_id = self.request.query_params.get('hostel_id')
        floor_id = self.request.query_params.get('floor_id')
        qs = Room.objects.select_related('hostel', 'floor')
        
        if hostel_id:
            qs = qs.filter(hostel_id=hostel_id)
        if floor_id:
            qs = qs.filter(floor_id=floor_id)
        
        return qs

    def perform_create(self, serializer):
        with transaction.atomic():
            # Check for duplicate room number in the same hostel
            hostel = serializer.validated_data.get('hostel')
            room_number = serializer.validated_data.get('room_number')
            
            existing_room = Room.objects.filter(
                hostel=hostel,
                room_number=room_number
            ).exists()
            
            if existing_room:
                raise serializers.ValidationError({
                    'room_number': f'Room {room_number} already exists in {hostel.name}. Please use a different room number.'
                })
            
            room = serializer.save()
            
            # Update floor bed count from room capacity
            room.floor.total_beds += room.capacity
            room.floor.available_beds += room.capacity
            room.floor.save()
            
            # Update hostel bed count from room capacity
            room.hostel.total_beds += room.capacity
            room.hostel.available_beds += room.capacity
            room.hostel.save()


class RoomDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset         = Room.objects.select_related('hostel', 'floor')
    serializer_class = RoomSerializer
    permission_classes = [IsAccomAdmin]

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        room = self.get_object()
        old_capacity = room.capacity
        
        serializer = self.get_serializer(room, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        
        new_capacity = serializer.validated_data.get('capacity', old_capacity)
        if new_capacity != old_capacity:
            diff = new_capacity - old_capacity
            # Update floor
            room.floor.total_beds += diff
            room.floor.available_beds = max(0, room.floor.available_beds + diff)
            room.floor.save()
            
            # Update hostel
            room.hostel.total_beds += diff
            room.hostel.available_beds = max(0, room.hostel.available_beds + diff)
            room.hostel.save()
        
        self.perform_update(serializer)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        room = self.get_object()
        
        if room.occupied > 0:
            return Response(
                {'error': f'Cannot delete room with {room.occupied} occupant(s).'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        with transaction.atomic():
            # Update floor and hostel
            room.floor.total_beds -= room.capacity
            room.floor.available_beds = max(0, room.floor.available_beds - room.capacity)
            room.floor.save()
            
            room.hostel.total_beds -= room.capacity
            room.hostel.available_beds = max(0, room.hostel.available_beds - room.capacity)
            room.hostel.save()
            
            room.delete()
        
        return Response({'message': 'Room deleted successfully.'})