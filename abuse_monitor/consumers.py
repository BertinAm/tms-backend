import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Ticket, Notification
from django.utils import timezone
from datetime import timedelta

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        """
        Called when the websocket is handshaking as part of initial connection.
        """
        await self.accept()
        await self.channel_layer.group_add("notifications", self.channel_name)
        print(f"WebSocket connected: {self.channel_name}")

    async def disconnect(self, close_code):
        """
        Called when the WebSocket closes for any reason.
        """
        await self.channel_layer.group_discard("notifications", self.channel_name)
        print(f"WebSocket disconnected: {self.channel_name}")

    async def receive(self, text_data):
        """
        Called when we receive a message from the WebSocket.
        """
        text_data_json = json.loads(text_data)
        message_type = text_data_json.get('type', 'message')
        
        if message_type == 'ping':
            await self.send(text_data=json.dumps({
                'type': 'pong',
                'timestamp': timezone.now().isoformat()
            }))

    async def notification_message(self, event):
        """
        Called when we want to send a notification to the WebSocket.
        """
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'ticket_id': event['ticket_id'],
            'subject': event['subject'],
            'priority': event['priority'],
            'status': event['status'],
            'timestamp': event['timestamp'],
            'message': event['message']
        }))

    @database_sync_to_async
    def get_recent_notifications(self):
        """
        Get recent notifications for the user.
        """
        recent_tickets = Ticket.objects.filter(
            created_at__gte=timezone.now() - timedelta(hours=24)
        ).order_by('-created_at')[:10]
        
        notifications = []
        for ticket in recent_tickets:
            notifications.append({
                'ticket_id': ticket.ticket_id,
                'subject': ticket.subject,
                'priority': ticket.priority,
                'status': ticket.status,
                'timestamp': ticket.created_at.isoformat(),
                'message': f"New ticket received: {ticket.subject}"
            })
        
        return notifications 