from django.apps import AppConfig


class AbuseMonitorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'abuse_monitor'
    
    def ready(self):
        """
        Start email monitoring service when Django is ready
        """
        import os
        # Only start monitoring if we're running the server (not during migrations, etc.)
        if os.environ.get('RUN_MAIN') == 'true':
            try:
                from .services import start_email_monitoring
                start_email_monitoring()
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to start email monitoring service: {e}") 