# serializers.py
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import AdminUser

class LoginSerializer(TokenObtainPairSerializer):
    role = serializers.CharField(write_only=True)

    def validate(self, attrs):
        role = attrs.pop('role', None)
        data = super().validate(attrs)
        user = self.user
        if role and user.role != role:
            raise serializers.ValidationError({'detail': 'Your credentials do not match the selected role.'})
        data['user'] = {'id': user.id, 'full_name': user.full_name, 'email': user.email, 'role': user.role}
        return data

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['role']      = user.role
        token['full_name'] = user.full_name
        return token
