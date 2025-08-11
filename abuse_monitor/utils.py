import re
import requests
from decouple import config
from .grok_api import GrokAPI
from .whatsapp_service import WhatsAppService

def parse_email(email_content):
    ticket_id = re.search(r'\[Ticket#(\d+)\]', email_content['subject'])
    deadline = re.search(r'(\d+-hour deadline)', email_content['body'])
    actions = re.search(r'(compliance actions required)', email_content['body'])
    
    return {
        'ticket_id': ticket_id.group(1) if ticket_id else None,
        'deadline': deadline.group(1) if deadline else None,
        'actions': actions.group(1) if actions else None,
    }

def send_whatsapp_notification(message):
    try:
        whatsapp_service = WhatsAppService()
        success = whatsapp_service.send_message_immediate(message)
        if not success:
            print("Failed to send WhatsApp notification")
    except Exception as e:
        print(f"Failed to send WhatsApp notification: {e}") 