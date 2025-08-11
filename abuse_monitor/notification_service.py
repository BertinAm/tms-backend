import json
import logging
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.utils import timezone
from .models import Ticket

logger = logging.getLogger(__name__)

class NotificationService:
    """
    Service for sending real-time notifications via WebSocket
    """
    
    @staticmethod
    def send_ticket_notification(ticket: Ticket):
        """
        Send a WebSocket notification when a new ticket is created
        """
        try:
            channel_layer = get_channel_layer()
            
            # Prepare notification data
            notification_data = {
                'type': 'notification_message',
                'ticket_id': ticket.ticket_id,
                'subject': ticket.subject,
                'priority': ticket.priority,
                'status': ticket.status,
                'timestamp': ticket.created_at.isoformat(),
                'message': f"New abuse complaint received: {ticket.subject}"
            }
            
            # Send to the notifications group
            async_to_sync(channel_layer.group_send)(
                "notifications",
                notification_data
            )
            
            logger.info(f"WebSocket notification sent for ticket {ticket.ticket_id}")
            
        except Exception as e:
            logger.error(f"Failed to send WebSocket notification: {e}")
    
    @staticmethod
    def send_browser_notification(ticket: Ticket):
        """
        Send a browser notification (if supported by the frontend)
        """
        try:
            channel_layer = get_channel_layer()
            
            notification_data = {
                'type': 'browser_notification',
                'title': 'New Abuse Complaint',
                'body': f"New ticket: {ticket.subject}",
                'ticket_id': ticket.ticket_id,
                'priority': ticket.priority,
                'timestamp': ticket.created_at.isoformat()
            }
            
            async_to_sync(channel_layer.group_send)(
                "notifications",
                notification_data
            )
            
            logger.info(f"Browser notification sent for ticket {ticket.ticket_id}")
            
        except Exception as e:
            logger.error(f"Failed to send browser notification: {e}") 