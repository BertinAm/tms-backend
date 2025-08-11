import re
import requests
import logging
from decouple import config
from .grok_api import GrokAPI
# from .whatsapp_service import WhatsAppService  # Disabled WhatsApp service

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
        return True
        
    except Exception as e:
        logger.error(f"Error in WhatsApp notification (disabled): {e}")
        print(f"Failed to process WhatsApp notification: {e}")
        return False 