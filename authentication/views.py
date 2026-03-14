from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import LoginSerializer
from .models import AdminUser

class LoginView(TokenObtainPairView):
    permission_classes = [AllowAny]
    serializer_class   = LoginSerializer

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        try:
            RefreshToken(request.data.get('refresh')).blacklist()
        except Exception:
            pass
        return Response({'detail': 'Logged out.'})

class MeView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        u = request.user
        return Response({'id': u.id, 'full_name': u.full_name, 'email': u.email, 'role': u.role})
