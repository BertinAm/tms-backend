import random
import datetime
from django.shortcuts import get_object_or_404
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.models import User
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
import os

from .security import create_token, decrypt_token
from .auth_serializers import (
    UserRegistrationSerializer, 
    UserLoginSerializer, 
    ForgotPasswordSerializer, 
    CheckOTPSerializer,
    ResetPasswordSerializer,
    UserProfileSerializer,
    ChangePasswordSerializer
)
from .models import UserProfile


class UserRegistrationView(GenericAPIView):
    serializer_class = UserRegistrationSerializer
    
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = serializer.save()
        
        # Generate OTP for email verification
        otp = str(random.randint(100000, 999999))
        payload = {
            'user_id': user.id,
            'email': user.email,
            'otp': otp,
            'type': 'registration',
            'exp': datetime.datetime.now() + datetime.timedelta(minutes=10)
        }
        token = create_token(payload)
        
        # Send OTP email
        self.send_otp_email(user.email, otp, user.first_name or user.username, 'registration')
        
        return Response({
            'message': 'Registration successful. Please verify your email with the OTP sent.',
            'token': token,
            'user_id': user.id
        }, status=status.HTTP_201_CREATED)
    
    def send_otp_email(self, email, otp, name, type_msg):
        subject = 'Verify Your TMS Account'
        context = {
            'name': name,
            'otp': otp,
            'type': type_msg,
            'company_name': 'TMS - Ticket Management System'
        }
        
        html_message = render_to_string('emails/otp_email.html', context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject,
            plain_message,
            settings.EMAIL_HOST_USER,
            [email],
            html_message=html_message,
            fail_silently=False,
        )


@method_decorator(csrf_exempt, name='dispatch')
class UserLoginView(APIView):
    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        if serializer.is_valid():
            user = authenticate(
                username=serializer.validated_data['username'],
                password=serializer.validated_data['password']
            )
            
            if user:
                if user.is_active:
                    refresh = RefreshToken.for_user(user)
                    profile, created = UserProfile.objects.get_or_create(user=user)
                    
                    return Response({
                        'message': 'Login successful',
                        'access_token': str(refresh.access_token),
                        'refresh_token': str(refresh),
                        'user': {
                            'id': user.id,
                            'username': user.username,
                            'email': user.email,
                            'first_name': user.first_name,
                            'last_name': user.last_name,
                            'profile_picture': profile.get_profile_picture_url()
                        }
                    })
                else:
                    return Response({'error': 'Account is disabled'}, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({'error': 'Invalid credentials'}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ForgotPasswordView(GenericAPIView):
    serializer_class = ForgotPasswordSerializer
    
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        user = get_object_or_404(User, email=email)
        otp = str(random.randint(100000, 999999))
        
        payload = {
            'user_id': user.id,
            'email': user.email,
            'otp': otp,
            'type': 'password_reset',
            'exp': datetime.datetime.now() + datetime.timedelta(minutes=10)
        }
        token = create_token(payload)
        
        # Send OTP email
        self.send_otp_email(user.email, otp, user.first_name or user.username)
        
        return Response({
            'message': 'OTP has been sent to your email address.',
            'token': token
        }, status=status.HTTP_200_OK)
    
    def send_otp_email(self, email, otp, name):
        subject = 'Reset Your TMS Password'
        context = {
            'name': name,
            'otp': otp,
            'type': 'password_reset',
            'company_name': 'TMS - Ticket Management System'
        }
        
        html_message = render_to_string('emails/otp_email.html', context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject,
            plain_message,
            settings.EMAIL_HOST_USER,
            [email],
            html_message=html_message,
            fail_silently=False,
        )


class CheckOTPView(GenericAPIView):
    serializer_class = CheckOTPSerializer
    
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        otp = serializer.validated_data['otp']
        enc_token = serializer.validated_data['token']
        
        data = decrypt_token(enc_token)
        if data['status']:
            payload = data['payload']
            otp_real = payload['otp']
            
            if otp == otp_real:
                email = payload['email']
                user = User.objects.get(email=email)
                otp_type = payload.get('type', 'registration')
                
                if otp_type == 'registration':
                    # Activate user account
                    user.is_active = True
                    user.save()
                    
                    # Generate access token
                    refresh = RefreshToken.for_user(user)
                    return Response({
                        'message': 'Email verified successfully. Account activated.',
                        'access_token': str(refresh.access_token),
                        'refresh_token': str(refresh),
                        'user': {
                            'id': user.id,
                            'username': user.username,
                            'email': user.email,
                            'first_name': user.first_name,
                            'last_name': user.last_name
                        }
                    }, status=status.HTTP_200_OK)
                    
                elif otp_type == 'password_reset':
                    # Generate password reset token
                    reset_payload = {
                        'user_id': user.id,
                        'email': user.email,
                        'type': 'reset_password',
                        'exp': datetime.datetime.now() + datetime.timedelta(minutes=30)
                    }
                    reset_token = create_token(reset_payload)
                    
                    return Response({
                        'message': 'OTP verified. You can now reset your password.',
                        'reset_token': reset_token
                    }, status=status.HTTP_200_OK)
                    
            else:
                return Response({
                    'message': 'Invalid OTP. Please try again.'
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({
                'message': 'OTP expired or invalid. Please request a new one.'
            }, status=status.HTTP_400_BAD_REQUEST)


class ResetPasswordView(GenericAPIView):
    serializer_class = ResetPasswordSerializer
    
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        token = serializer.validated_data['token']
        new_password = serializer.validated_data['new_password']
        
        data = decrypt_token(token)
        if data['status']:
            payload = data['payload']
            if payload.get('type') == 'reset_password':
                user = User.objects.get(id=payload['user_id'])
                user.set_password(new_password)
                user.save()
                
                return Response({
                    'message': 'Password reset successfully.'
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'message': 'Invalid reset token.'
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({
                'message': 'Token expired or invalid.'
            }, status=status.HTTP_400_BAD_REQUEST)


class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            user = request.user
            profile, created = UserProfile.objects.get_or_create(user=user)
            
            return Response({
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'date_joined': user.date_joined.isoformat(),
                'last_login': user.last_login.isoformat() if user.last_login else None,
                'profile_picture': profile.get_profile_picture_url(),
                'bio': profile.bio,
                'phone_number': profile.phone_number
            })
        except Exception as e:
            logger.error(f"Profile retrieval error: {e}")
            return Response({'error': 'Failed to retrieve profile'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def put(self, request):
        try:
            user = request.user
            profile, created = UserProfile.objects.get_or_create(user=user)
            
            # Update user fields
            if 'first_name' in request.data:
                user.first_name = request.data['first_name']
            if 'last_name' in request.data:
                user.last_name = request.data['last_name']
            user.save()
            
            # Update profile fields
            if 'bio' in request.data:
                profile.bio = request.data['bio']
            if 'phone_number' in request.data:
                profile.phone_number = request.data['phone_number']
            profile.save()
            
            return Response({
                'message': 'Profile updated successfully',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'profile_picture': profile.get_profile_picture_url(),
                    'bio': profile.bio,
                    'phone_number': profile.phone_number
                }
            })
        except Exception as e:
            logger.error(f"Profile update error: {e}")
            return Response({'error': 'Failed to update profile'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            refresh_token = request.data["refresh_token"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({
                'message': 'Successfully logged out.'
            }, status=status.HTTP_200_OK)
        except Exception:
            return Response({
                'message': 'Logout successful.'
            }, status=status.HTTP_200_OK)


class ChangePasswordView(GenericAPIView):
    serializer_class = ChangePasswordSerializer
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        current_password = serializer.validated_data['current_password']
        new_password = serializer.validated_data['new_password']
        
        # Check current password
        if not user.check_password(current_password):
            return Response({
                'message': 'Current password is incorrect.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Set new password
        user.set_password(new_password)
        user.save()
        
        return Response({
            'message': 'Password changed successfully.'
        }, status=status.HTTP_200_OK)


class DeleteAccountView(APIView):
    permission_classes = [IsAuthenticated]
    
    def delete(self, request):
        user = request.user
        
        # Log the account deletion
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Account deleted for user: {user.username} ({user.email})")
        
        # Delete the user account
        user.delete()
        
        return Response({
            'message': 'Account deleted successfully.'
        }, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name='dispatch')
class UploadProfilePictureView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            user = request.user
            profile, created = UserProfile.objects.get_or_create(user=user)
            
            # Check if file was uploaded
            if 'profile_picture' not in request.FILES:
                return Response({'error': 'No profile picture file provided'}, status=status.HTTP_400_BAD_REQUEST)
            
            file = request.FILES['profile_picture']
            
            # Validate file type
            allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif']
            if file.content_type not in allowed_types:
                return Response({'error': 'Invalid file type. Only JPEG, PNG, and GIF are allowed'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate file size (max 5MB)
            if file.size > 5 * 1024 * 1024:
                return Response({'error': 'File size too large. Maximum size is 5MB'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Delete old profile picture if it exists
            if profile.profile_picture:
                try:
                    if os.path.exists(profile.profile_picture.path):
                        os.remove(profile.profile_picture.path)
                except Exception as e:
                    logger.warning(f"Failed to delete old profile picture: {e}")
            
            # Save new profile picture
            profile.profile_picture = file
            profile.save()
            
            return Response({
                'message': 'Profile picture uploaded successfully',
                'profile_picture_url': profile.get_profile_picture_url()
            })
            
        except Exception as e:
            logger.error(f"Profile picture upload error: {e}")
            return Response({'error': 'Failed to upload profile picture'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
