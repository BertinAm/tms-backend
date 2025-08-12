import re
import requests
import logging
from decouple import config
from .grok_api import GrokAPI
# from .whatsapp_service import WhatsAppService  # Disabled WhatsApp service
from .models import ActivityLog, Ticket
from django.contrib.auth.models import User
from django.utils import timezone
import json

logger = logging.getLogger(__name__)

def parse_email(email_content: str) -> dict:
    """
    Parse email content and extract relevant information
    """
    # Basic email parsing logic
    lines = email_content.split('\n')
    parsed_data = {
        'subject': '',
        'body': '',
        'sender': '',
        'date': ''
    }
    
    for line in lines:
        if line.startswith('Subject:'):
            parsed_data['subject'] = line.replace('Subject:', '').strip()
        elif line.startswith('From:'):
            parsed_data['sender'] = line.replace('From:', '').strip()
        elif line.startswith('Date:'):
            parsed_data['date'] = line.replace('Date:', '').strip()
    
    # Join remaining lines as body
    body_lines = [line for line in lines if not line.startswith(('Subject:', 'From:', 'Date:'))]
    parsed_data['body'] = '\n'.join(body_lines).strip()
    
    return parsed_data

def log_activity(
    activity_type: str,
    description: str,
    user=None,
    severity='info',
    details=None,
    related_ticket=None,
    request=None
):
    """
    Log an activity to the ActivityLog model
    """
    try:
        # Get IP address and user agent from request if available
        ip_address = None
        user_agent = None
        
        if request:
            ip_address = request.META.get('REMOTE_ADDR') or request.META.get('HTTP_X_FORWARDED_FOR')
            user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Create the activity log entry
        ActivityLog.objects.create(
            user=user,
            activity_type=activity_type,
            severity=severity,
            description=description,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            related_ticket=related_ticket
        )
        
        logger.info(f"Activity logged: {activity_type} - {description}")
        
    except Exception as e:
        logger.error(f"Failed to log activity: {e}")

def send_whatsapp_notification(message):
    """
    Send WhatsApp notification
    DISABLED: WhatsApp service temporarily disabled due to pywhatkit issues on Render
    """
    try:
        # whatsapp_service = WhatsAppService()  # Disabled WhatsApp service
        # success = whatsapp_service.send_message_immediate(message)  # Disabled WhatsApp service

        # Log the message instead of sending
        logger.info(f"WhatsApp notification would be sent: {message[:100]}...")
        print("WhatsApp notification disabled - message logged instead")
        
        # Log this activity
        log_activity(
            activity_type='notification_sent',
            description='WhatsApp notification logged (service disabled)',
            severity='info',
            details={'message_preview': message[:100]}
        )
        
        return True

    except Exception as e:
        logger.error(f"Error in WhatsApp notification (disabled): {e}")
        
        # Log the error
        log_activity(
            activity_type='notification_failed',
            description='WhatsApp notification failed',
            severity='error',
            details={'error': str(e)}
        )
        
        print(f"Failed to process WhatsApp notification: {e}")
        return False 