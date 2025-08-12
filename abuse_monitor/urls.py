from django.urls import path
from . import views, auth_views

urlpatterns = [
    # Authentication endpoints
    path('auth/register', auth_views.UserRegistrationView.as_view(), name='user-register'),
    path('auth/login', auth_views.UserLoginView.as_view(), name='user-login'),
    path('auth/logout', auth_views.LogoutView.as_view(), name='user-logout'),
    path('auth/forgot-password', auth_views.ForgotPasswordView.as_view(), name='forgot-password'),
    path('auth/check-otp', auth_views.CheckOTPView.as_view(), name='check-otp'),
    path('auth/reset-password', auth_views.ResetPasswordView.as_view(), name='reset-password'),
    path('auth/profile', auth_views.UserProfileView.as_view(), name='user-profile'),
    path('auth/change-password', auth_views.ChangePasswordView.as_view(), name='change-password'),
    path('auth/delete-account', auth_views.DeleteAccountView.as_view(), name='delete-account'),
    
    # Health check endpoint
    path('health', views.HealthCheckView.as_view(), name='health-check'),
    
    # Ticket endpoints
    path('tickets', views.TicketListView.as_view(), name='ticket-list'),
    path('tickets/search', views.TicketSearchView.as_view(), name='ticket-search'),
    path('tickets/intelligent-search', views.TicketIntelligentSearchView.as_view(), name='ticket-intelligent-search'),
    path('tickets/analytics', views.TicketAnalyticsView.as_view(), name='ticket-analytics'),
    path('tickets/<str:ticket_id>', views.TicketDetailView.as_view(), name='ticket-detail'),
    
    # Chat endpoints
    path('chat', views.ChatView.as_view(), name='chat'),
    path('chat/stream', views.ChatStreamView.as_view(), name='chat-stream'),
    path('chat/history', views.ConversationHistoryView.as_view(), name='conversation-history'),
    
    # Analysis endpoints
    path('tickets/analyze', views.TicketAnalysisView.as_view(), name='ticket-analysis'),
    
    # Webhook endpoints
    path('webhook/email', views.EmailWebhookView.as_view(), name='email-webhook'),
    
    # Email monitoring endpoints
    path('monitor/email', views.EmailMonitorView.as_view(), name='email-monitor'),
    path('monitor/service', views.EmailMonitoringServiceView.as_view(), name='email-monitor-service'),
    
    # Notification endpoints
    path('notifications', views.NotificationListView.as_view(), name='notification-list'),

    # Activity log endpoints
    path('activity-logs', views.ActivityLogView.as_view(), name='activity_logs'),
    path('activity-logs/stats', views.ActivityLogStatsView.as_view(), name='activity_log_stats'),
] 