import threading
import time
import logging
from django.apps import AppConfig
from django.conf import settings
from .email_monitor import EmailMonitor

logger = logging.getLogger(__name__)

class EmailMonitoringService:
    """
    Background service for continuous email monitoring
    """
    
    def __init__(self):
        self.monitor = EmailMonitor()
        self.is_running = False
        self.monitoring_thread = None
        self.check_interval = 60  # seconds
        
    def start_monitoring(self):
        """
        Start the continuous email monitoring in a background thread
        """
        if self.is_running:
            logger.info("Email monitoring is already running")
            return
        
        self.is_running = True
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitoring_thread.start()
        logger.info("Email monitoring service started")
    
    def stop_monitoring(self):
        """
        Stop the continuous email monitoring
        """
        self.is_running = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        logger.info("Email monitoring service stopped")
    
    def _monitoring_loop(self):
        """
        Main monitoring loop
        """
        logger.info("Starting continuous email monitoring loop")
        
        # Initialize UID tracking with retries
        retry_count = 0
        max_retries = 3
        while retry_count < max_retries:
            if self.monitor.initialize_uid_max():
                break
            retry_count += 1
            logger.warning(f"UID tracking initialization failed, retry {retry_count}/{max_retries}")
            time.sleep(30)  # Wait 30 seconds before retry
        
        if retry_count >= max_retries:
            logger.error("Failed to initialize UID tracking after multiple retries")
            return
        
        while self.is_running:
            try:
                # Run one monitoring cycle
                self._run_monitoring_cycle()
                
                # Wait before next check
                time.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                # Wait a bit longer on error
                time.sleep(self.check_interval * 2)
    
    def _run_monitoring_cycle(self):
        """
        Run a single monitoring cycle
        """
        mail = None
        try:
            # Connect to Gmail
            mail = self.monitor.connect_to_gmail()
            if not mail:
                logger.error("Failed to connect to Gmail")
                return
            
            # Select the INBOX before searching
            mail.select('INBOX')
            
            # Search for new emails
            result, data = mail.uid('search', None, self.monitor.search_string(self.monitor.uid_max, self.monitor.criteria))
            uids = [int(s) for s in data[0].split()]
            
            new_emails_found = 0
            for uid in uids:
                # Check if this is a new email
                if uid > self.monitor.uid_max:
                    try:
                        # Fetch email data
                        result, data = mail.uid('fetch', str(uid), '(RFC822)')
                        
                        for response_part in data:
                            if isinstance(response_part, tuple):
                                # Parse email
                                import email
                                email_message = email.message_from_bytes(response_part[1])
                                
                                # Extract email details
                                email_data = self.monitor.extract_email_details_from_message(email_message, uid)
                                if email_data:
                                    # Process the email
                                    self.monitor.process_single_email(email_data)
                                    new_emails_found += 1
                                    logger.info(f"Processed new email: {email_data['ticket_id']}")
                        
                        # Update uid_max
                        self.monitor.uid_max = uid
                        
                    except Exception as e:
                        logger.error(f"Error processing email {uid}: {e}")
            
            if new_emails_found > 0:
                logger.info(f"Found and processed {new_emails_found} new emails")
            
        except Exception as e:
            logger.error(f"Error in monitoring cycle: {e}")
        finally:
            # Always close connection properly
            if mail:
                try:
                    mail.close()
                    mail.logout()
                except Exception as e:
                    logger.error(f"Error closing mail connection: {e}")

# Global service instance
email_monitoring_service = EmailMonitoringService()

def start_email_monitoring():
    """
    Start the email monitoring service
    """
    email_monitoring_service.start_monitoring()

def stop_email_monitoring():
    """
    Stop the email monitoring service
    """
    email_monitoring_service.stop_monitoring() 