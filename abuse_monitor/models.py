from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    profile_picture = models.ImageField(upload_to='profile_pictures/', null=True, blank=True)
    bio = models.TextField(max_length=500, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s profile"

    def get_profile_picture_url(self):
        if self.profile_picture:
            return self.profile_picture.url
        return None

class Ticket(models.Model):
    ticket_id = models.CharField(max_length=20, unique=True)
    subject = models.CharField(max_length=255)
    body = models.TextField()
    sender = models.CharField(max_length=255, default='abuse@contabo.com')
    recipient = models.CharField(max_length=255, default='tangentohost@gmail.com')
    received_at = models.DateTimeField(auto_now_add=True)
    priority = models.CharField(max_length=20, default='medium')
    status = models.CharField(max_length=20, default='open')
    ai_analysis = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.ticket_id} - {self.subject}"

class Notification(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE)
    sent_to = models.CharField(max_length=50)
    sent_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default='sent')
    message = models.TextField(blank=True)

    def __str__(self):
        return f"Notification for {self.ticket.ticket_id} to {self.sent_to}"

class ActivityLog(models.Model):
    ACTIVITY_TYPES = [
        # User Actions
        ('user_login', 'User Login'),
        ('user_logout', 'User Logout'),
        ('user_register', 'User Registration'),
        ('password_change', 'Password Change'),
        ('profile_update', 'Profile Update'),
        
        # Ticket Actions
        ('ticket_view', 'Ticket Viewed'),
        ('ticket_create', 'Ticket Created'),
        ('ticket_update', 'Ticket Updated'),
        ('ticket_status_change', 'Ticket Status Changed'),
        ('ticket_priority_change', 'Ticket Priority Changed'),
        ('ticket_delete', 'Ticket Deleted'),
        
        # System Events
        ('email_monitor_start', 'Email Monitoring Started'),
        ('email_monitor_stop', 'Email Monitoring Stopped'),
        ('email_received', 'Email Received'),
        ('ai_analysis', 'AI Analysis Performed'),
        ('notification_sent', 'Notification Sent'),
        ('notification_failed', 'Notification Failed'),
        
        # Chat Actions
        ('chat_message', 'Chat Message Sent'),
        ('chat_analysis', 'Chat Analysis Requested'),
        ('chat_reset', 'Chat Reset'),
        
        # Admin Actions
        ('user_created', 'User Created'),
        ('user_updated', 'User Updated'),
        ('user_deleted', 'User Deleted'),
        ('system_config', 'System Configuration Changed'),
        
        # Error Events
        ('error_occurred', 'Error Occurred'),
        ('api_failure', 'API Failure'),
        ('connection_failed', 'Connection Failed'),
    ]
    
    SEVERITY_LEVELS = [
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('critical', 'Critical'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    activity_type = models.CharField(max_length=50, choices=ACTIVITY_TYPES)
    severity = models.CharField(max_length=20, choices=SEVERITY_LEVELS, default='info')
    description = models.TextField()
    details = models.JSONField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    related_ticket = models.ForeignKey(Ticket, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'activity_type', 'created_at']),
            models.Index(fields=['activity_type', 'severity', 'created_at']),
            models.Index(fields=['related_ticket', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.get_activity_type_display()} - {self.user.username if self.user else 'System'} - {self.created_at}" 