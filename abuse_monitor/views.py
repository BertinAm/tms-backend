from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from decouple import config
from .models import Ticket, Notification
# from .utils import parse_email, send_whatsapp_notification  # Disabled WhatsApp service
from .grok_api import GrokAPI
from .chat_manager import TMSChatManager
from .email_monitor import EmailMonitor
from .services import email_monitoring_service, start_email_monitoring, stop_email_monitoring
import json
import logging
from django.db import models
from datetime import datetime
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)

@method_decorator(csrf_exempt, name='dispatch')
class HealthCheckView(APIView):
    """
    Health check endpoint for Docker
    """
    def get(self, request):
        try:
            # Check database connection
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            
            # Check Redis connection (if available)
            try:
                from channels.layers import get_channel_layer
                channel_layer = get_channel_layer()
                # Try to send a test message
                from asgiref.sync import async_to_sync
                async_to_sync(channel_layer.group_send)("health_check", {"type": "health_check"})
            except Exception as e:
                logger.warning(f"Redis connection check failed: {e}")
            
            return Response({
                'status': 'healthy',
                'timestamp': timezone.now().isoformat(),
                'database': 'connected',
                'redis': 'connected' if 'channel_layer' in locals() else 'disconnected'
            })
        except Exception as e:
            return Response({
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@method_decorator(csrf_exempt, name='dispatch')
class TicketListView(APIView):
    # permission_classes = [IsAuthenticated] # Temporarily removed for testing
    def get(self, request):
        tickets = Ticket.objects.all()
        response_data = [{
            'ticket_id': t.ticket_id,
            'subject': t.subject,
            'status': t.status,
            'priority': t.priority,
            'received_at': t.received_at.isoformat() if t.received_at else None
        } for t in tickets]
        print(f"Returning {len(response_data)} tickets")
        return Response(response_data)

@method_decorator(csrf_exempt, name='dispatch')
class ChatView(APIView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Initialize chat manager with API key
        api_key = config('GROK_API_KEY')
        self.chat_manager = TMSChatManager(api_key)
    
    def post(self, request):
        """
        Enhanced chat endpoint with unified chat manager
        """
        try:
            message = request.data.get('message', '')
            session_id = request.data.get('session_id', 'default')
            reset_conversation = request.data.get('reset', False)
            
            if not message:
                return Response({'error': 'Message is required'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Reset conversation if requested
            if reset_conversation:
                self.chat_manager.reset_conversation()
            
            # Get response from unified chat manager
            response = self.chat_manager.chat(message, stream=False)
            
            # Get conversation history for context
            conversation_history = self.chat_manager.get_conversation_history()
            
            return Response({
                'response': response,
                'timestamp': datetime.now().isoformat(),
                'session_id': session_id,
                'conversation_length': len(conversation_history),
                'message_count': len([m for m in conversation_history if m['role'] == 'user'])
            })
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@method_decorator(csrf_exempt, name='dispatch')
class ChatStreamView(APIView):
    """
    Streaming chat endpoint for real-time responses
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Initialize chat manager with API key
        api_key = config('GROK_API_KEY')
        self.chat_manager = TMSChatManager(api_key)
    
    def post(self, request):
        """
        Streaming chat endpoint
        """
        try:
            message = request.data.get('message', '')
            session_id = request.data.get('session_id', 'default')
            reset_conversation = request.data.get('reset', False)
            
            if not message:
                return Response({'error': 'Message is required'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Reset conversation if requested
            if reset_conversation:
                self.chat_manager.reset_conversation()
            
            # Get streaming response
            response = self.chat_manager.chat(message, stream=True)
            
            return Response({
                'response': response,
                'timestamp': datetime.now().isoformat(),
                'session_id': session_id,
                'streaming': True
            })
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@method_decorator(csrf_exempt, name='dispatch')
class ConversationHistoryView(APIView):
    """
    Get conversation history for a session
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Initialize chat manager with API key
        api_key = config('GROK_API_KEY')
        self.chat_manager = TMSChatManager(api_key)
    
    def get(self, request):
        """
        Get conversation history
        """
        try:
            history = self.chat_manager.get_conversation_history()
            return Response({
                'history': history,
                'message_count': len([m for m in history if m['role'] == 'user']),
                'total_messages': len(history)
            })
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def delete(self, request):
        """
        Reset conversation history
        """
        try:
            self.chat_manager.reset_conversation()
            return Response({'message': 'Conversation reset successfully'})
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@method_decorator(csrf_exempt, name='dispatch')
class TicketAnalysisView(APIView):
    def post(self, request):
        """
        Analyze a specific ticket using Grok AI
        """
        try:
            ticket_id = request.data.get('ticket_id')
            
            if not ticket_id:
                return Response({'error': 'Ticket ID is required'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Get ticket from database
            try:
                ticket = Ticket.objects.get(ticket_id=ticket_id)
            except Ticket.DoesNotExist:
                return Response({'error': 'Ticket not found'}, status=status.HTTP_404_NOT_FOUND)
            
            # Prepare ticket data for analysis
            ticket_data = {
                'ticket_id': ticket.ticket_id,
                'subject': ticket.subject,
                'body': ticket.body,
                'priority': ticket.priority,
                'status': ticket.status,
                'received_at': ticket.received_at.isoformat()
            }
            
            # Initialize Grok API for analysis
            grok_api = GrokAPI()
            analysis = grok_api.analyze_ticket(ticket_data)
            
            return Response({
                'ticket_id': ticket_id,
                'analysis': analysis,
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@method_decorator(csrf_exempt, name='dispatch')
class TicketDetailView(APIView):
    def get(self, request, ticket_id):
        """
        Get detailed information about a specific ticket
        """
        try:
            ticket = Ticket.objects.get(ticket_id=ticket_id)
            
            ticket_data = {
                'ticket_id': ticket.ticket_id,
                'subject': ticket.subject,
                'body': ticket.body,
                'priority': ticket.priority,
                'status': ticket.status,
                'received_at': ticket.received_at.isoformat() if ticket.received_at else None,
                'sender': ticket.sender,
                'recipient': ticket.recipient
            }
            
            return Response(ticket_data)
            
        except Ticket.DoesNotExist:
            return Response({'error': 'Ticket not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@method_decorator(csrf_exempt, name='dispatch')
class TicketSearchView(APIView):
    def get(self, request):
        """
        Search tickets with various filters
        """
        try:
            query = request.GET.get('q', '').strip()
            priority = request.GET.get('priority', '').strip()
            status = request.GET.get('status', '').strip()
            limit = int(request.GET.get('limit', 20))
            
            tickets = Ticket.objects.all()
            
            # Apply filters
            if query:
                tickets = tickets.filter(
                    models.Q(ticket_id__icontains=query) |
                    models.Q(subject__icontains=query) |
                    models.Q(body__icontains=query)
                )
            
            if priority:
                tickets = tickets.filter(priority__iexact=priority)
            
            if status:
                tickets = tickets.filter(status__iexact=status)
            
            # Order by most recent first
            tickets = tickets.order_by('-received_at')[:limit]
            
            results = [{
                'ticket_id': t.ticket_id,
                'subject': t.subject,
                'body': t.body[:200] + '...' if len(t.body) > 200 else t.body,
                'priority': t.priority,
                'status': t.status,
                'received_at': t.received_at.isoformat() if t.received_at else None
            } for t in tickets]
            
            return Response({
                'query': query,
                'filters': {'priority': priority, 'status': status},
                'results': results,
                'count': len(results)
            })
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@method_decorator(csrf_exempt, name='dispatch')
class TicketIntelligentSearchView(APIView):
    def get(self, request):
        """
        Intelligent ticket search for Grok - search by ID, subject, date, priority, status
        """
        try:
            query = request.GET.get('q', '').strip()
            date_filter = request.GET.get('date', '').strip()
            priority_filter = request.GET.get('priority', '').strip()
            status_filter = request.GET.get('status', '').strip()
            
            tickets = Ticket.objects.all()
            
            # Apply filters
            if query:
                tickets = tickets.filter(
                    models.Q(ticket_id__icontains=query) |
                    models.Q(subject__icontains=query) |
                    models.Q(body__icontains=query)
                )
            
            if date_filter:
                try:
                    # Try to parse date in various formats
                    from datetime import datetime
                    date_obj = datetime.strptime(date_filter, '%Y-%m-%d').date()
                    tickets = tickets.filter(received_at__date=date_obj)
                except ValueError:
                    # If date parsing fails, try to find date in query
                    pass
            
            if priority_filter:
                tickets = tickets.filter(priority__iexact=priority_filter)
            
            if status_filter:
                tickets = tickets.filter(status__iexact=status_filter)
            
            # Order by most recent first
            tickets = tickets.order_by('-received_at')
            
            results = [{
                'ticket_id': t.ticket_id,
                'subject': t.subject,
                'body': t.body[:200] + '...' if len(t.body) > 200 else t.body,
                'status': t.status,
                'priority': t.priority,
                'received_at': t.received_at.isoformat() if t.received_at else None,
                'sender': t.sender,
                'recipient': t.recipient
            } for t in tickets[:20]]  # Limit to 20 results
            
            return Response({
                'query': query,
                'filters': {
                    'date': date_filter,
                    'priority': priority_filter,
                    'status': status_filter
                },
                'results': results,
                'count': len(results),
                'total_found': tickets.count()
            })
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@method_decorator(csrf_exempt, name='dispatch')
class TicketAnalyticsView(APIView):
    def get(self, request):
        """
        Get analytics data for tickets
        """
        try:
            from django.db.models import Count, Q
            from datetime import datetime, timedelta
            
            # Get date range
            days = int(request.GET.get('days', 30))
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # Filter tickets by date range
            tickets = Ticket.objects.filter(received_at__range=[start_date, end_date])
            
            # Calculate analytics
            total_tickets = tickets.count()
            open_tickets = tickets.filter(status='open').count()
            closed_tickets = tickets.filter(status='closed').count()
            high_priority = tickets.filter(priority='high').count()
            medium_priority = tickets.filter(priority='medium').count()
            low_priority = tickets.filter(priority='low').count()
            
            # Daily ticket counts for the last 30 days
            daily_counts = []
            for i in range(days):
                date = end_date - timedelta(days=i)
                count = tickets.filter(received_at__date=date.date()).count()
                daily_counts.append({
                    'date': date.strftime('%Y-%m-%d'),
                    'count': count
                })
            
            # Priority distribution
            priority_distribution = tickets.values('priority').annotate(count=Count('priority'))
            
            # Status distribution
            status_distribution = tickets.values('status').annotate(count=Count('status'))
            
            # Recent tickets
            recent_tickets = tickets.order_by('-received_at')[:5]
            recent_tickets_data = [{
                'ticket_id': t.ticket_id,
                'subject': t.subject,
                'priority': t.priority,
                'status': t.status,
                'received_at': t.received_at.isoformat() if t.received_at else None
            } for t in recent_tickets]
            
            return Response({
                'summary': {
                    'total_tickets': total_tickets,
                    'open_tickets': open_tickets,
                    'closed_tickets': closed_tickets,
                    'high_priority': high_priority,
                    'medium_priority': medium_priority,
                    'low_priority': low_priority
                },
                'daily_counts': daily_counts,
                'priority_distribution': list(priority_distribution),
                'status_distribution': list(status_distribution),
                'recent_tickets': recent_tickets_data,
                'period_days': days
            })
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@method_decorator(csrf_exempt, name='dispatch')
class EmailWebhookView(APIView):
    def post(self, request):
        """
        Handle incoming email webhooks
        """
        try:
            # Parse email data
            email_data = request.data
            
            # Extract relevant information
            subject = email_data.get('subject', '')
            body = email_data.get('body', '')
            sender = email_data.get('from', '')
            recipient = email_data.get('to', '')
            
            # Create ticket from email
            ticket = Ticket.objects.create(
                ticket_id=f"EMAIL{datetime.now().strftime('%Y%m%d%H%M%S')}",
                subject=subject,
                body=body,
                priority='medium',
                status='open',
                sender=sender,
                recipient=recipient,
                received_at=datetime.now()
            )
            
            # Send WhatsApp notification
            # notification_message = f"New abuse complaint received: {subject}"
            # send_whatsapp_notification(notification_message) # Disabled WhatsApp service
            
            return Response({
                'success': True,
                'ticket_id': ticket.ticket_id,
                'message': 'Email processed and ticket created'
            })
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@method_decorator(csrf_exempt, name='dispatch')
class EmailMonitorView(APIView):
    """
    API endpoint to manually trigger email monitoring
    """
    def post(self, request):
        """
        Manually trigger email monitoring
        """
        try:
            days_back = request.data.get('days_back', 1)
            test_mode = request.data.get('test', False)
            uid_tracking = request.data.get('uid_tracking', False)
            uid_interval = request.data.get('uid_interval', 60)
            
            monitor = EmailMonitor()
            
            if test_mode:
                # Test mode - just check connection
                imap = monitor.connect_to_gmail()
                if imap:
                    imap.close()
                    imap.logout()
                    
                    # Test UID tracking
                    uid_success = monitor.initialize_uid_max()
                    
                    return Response({
                        'success': True,
                        'message': 'Gmail connection test successful',
                        'uid_tracking': uid_success,
                        'test_mode': True
                    })
                else:
                    return Response({
                        'success': False,
                        'message': 'Gmail connection test failed',
                        'test_mode': True
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            elif uid_tracking:
                # Start UID tracking monitoring in background
                import threading
                
                def run_uid_monitoring():
                    try:
                        monitor.run_continuous_monitoring(uid_interval)
                    except Exception as e:
                        logger.error(f"UID tracking monitoring failed: {e}")
                
                # Start monitoring in background thread
                monitor_thread = threading.Thread(target=run_uid_monitoring, daemon=True)
                monitor_thread.start()
                
                return Response({
                    'success': True,
                    'message': f'UID tracking monitoring started (checking every {uid_interval} seconds)',
                    'uid_tracking': True
                })
            else:
                # Run actual monitoring
                results = monitor.process_new_emails(days_back=days_back)
                
                return Response({
                    'success': True,
                    'message': 'Email monitoring completed',
                    'results': results,
                    'emails_found': results['emails_found'],
                    'tickets_created': results['tickets_created'],
                    'notifications_sent': results['notifications_sent'],
                    'errors': results['errors']
                })
                
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Email monitoring failed: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def get(self, request):
        """
        Get monitoring status and statistics
        """
        try:
            # Get recent tickets
            recent_tickets = Ticket.objects.order_by('-received_at')[:5]
            tickets_data = [{
                'ticket_id': t.ticket_id,
                'subject': t.subject,
                'priority': t.priority,
                'status': t.status,
                'received_at': t.received_at.isoformat() if t.received_at else None
            } for t in recent_tickets]
            
            # Get notification statistics
            recent_notifications = Notification.objects.order_by('-sent_at')[:5]
            notifications_data = [{
                'ticket_id': n.ticket.ticket_id,
                'sent_to': n.sent_to,
                'status': n.status,
                'sent_at': n.sent_at.isoformat() if n.sent_at else None
            } for n in recent_notifications]
            
            return Response({
                'monitoring_status': 'active',
                'recent_tickets': tickets_data,
                'recent_notifications': notifications_data,
                'total_tickets': Ticket.objects.count(),
                'total_notifications': Notification.objects.count()
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Failed to get monitoring status: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@method_decorator(csrf_exempt, name='dispatch')
class EmailMonitoringServiceView(APIView):
    """
    API endpoint to control the email monitoring service
    """
    def post(self, request):
        """
        Control the email monitoring service
        """
        try:
            action = request.data.get('action', 'status')
            
            if action == 'start':
                start_email_monitoring()
                return Response({
                    'success': True,
                    'message': 'Email monitoring service started',
                    'status': 'running'
                })
            elif action == 'stop':
                stop_email_monitoring()
                return Response({
                    'success': True,
                    'message': 'Email monitoring service stopped',
                    'status': 'stopped'
                })
            elif action == 'status':
                return Response({
                    'success': True,
                    'status': 'running' if email_monitoring_service.is_running else 'stopped',
                    'is_running': email_monitoring_service.is_running
                })
            else:
                return Response({
                    'success': False,
                    'message': 'Invalid action. Use: start, stop, or status'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Service control failed: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@method_decorator(csrf_exempt, name='dispatch')
class NotificationListView(APIView):
    """
    API endpoint to get notifications
    """
    def get(self, request):
        """
        Get recent notifications
        """
        try:
            # Get query parameters
            hours = int(request.GET.get('hours', 24))
            limit = int(request.GET.get('limit', 10))
            
            # Calculate time range
            since = timezone.now() - timedelta(hours=hours)
            
            # Get recent tickets
            recent_tickets = Ticket.objects.filter(
                created_at__gte=since
            ).order_by('-created_at')[:limit]
            
            notifications = []
            for ticket in recent_tickets:
                notifications.append({
                    'id': ticket.id,
                    'ticket_id': ticket.ticket_id,
                    'subject': ticket.subject,
                    'priority': ticket.priority,
                    'status': ticket.status,
                    'timestamp': ticket.created_at.isoformat(),
                    'message': f"New abuse complaint: {ticket.subject}",
                    'type': 'ticket_created'
                })
            
            return Response({
                'success': True,
                'notifications': notifications,
                'count': len(notifications),
                'hours_back': hours
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Failed to get notifications: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR) 