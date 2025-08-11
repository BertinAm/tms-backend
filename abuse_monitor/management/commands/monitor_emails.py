from django.core.management.base import BaseCommand
from django.utils import timezone
from abuse_monitor.email_monitor import EmailMonitor
import logging
import time
import schedule
from datetime import datetime

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Monitor Gmail for Contabo abuse emails and process them automatically'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--continuous',
            action='store_true',
            help='Run continuously with scheduled intervals',
        )
        parser.add_argument(
            '--interval',
            type=int,
            default=30,
            help='Interval in minutes for continuous monitoring (default: 30)',
        )
        parser.add_argument(
            '--test',
            action='store_true',
            help='Test the email monitoring system without processing',
        )
        parser.add_argument(
            '--days-back',
            type=int,
            default=1,
            help='Number of days back to check for emails (default: 1)',
        )
        parser.add_argument(
            '--uid-tracking',
            action='store_true',
            help='Use UID tracking for efficient continuous monitoring',
        )
        parser.add_argument(
            '--uid-interval',
            type=int,
            default=60,
            help='Interval in seconds for UID tracking monitoring (default: 60)',
        )
    
    def handle(self, *args, **options):
        monitor = EmailMonitor()
        
        if options['test']:
            self.test_monitoring_system(monitor)
        elif options['uid_tracking']:
            self.run_uid_tracking_monitoring(monitor, options['uid_interval'])
        elif options['continuous']:
            self.run_continuous_monitoring(monitor, options['interval'])
        else:
            self.run_single_cycle(monitor, options['days_back'])
    
    def test_monitoring_system(self, monitor: EmailMonitor):
        """
        Test the monitoring system without processing emails
        """
        self.stdout.write(
            self.style.SUCCESS('Testing email monitoring system...')
        )
        
        try:
            # Test Gmail connection
            imap = monitor.connect_to_gmail()
            if imap:
                self.stdout.write(
                    self.style.SUCCESS('✓ Gmail connection successful')
                )
                imap.close()
                imap.logout()
            else:
                self.stdout.write(
                    self.style.ERROR('✗ Gmail connection failed')
                )
                return
            
            # Test UID tracking initialization
            if monitor.initialize_uid_max():
                self.stdout.write(
                    self.style.SUCCESS('✓ UID tracking initialization successful')
                )
            else:
                self.stdout.write(
                    self.style.WARNING('⚠ UID tracking initialization failed')
                )
            
            # Test WhatsApp connection
            if monitor.whatsapp_service.test_connection():
                self.stdout.write(
                    self.style.SUCCESS('✓ WhatsApp connection successful')
                )
            else:
                self.stdout.write(
                    self.style.WARNING('⚠ WhatsApp connection failed - notifications may not work')
                )
            
            # Test Grok API
            test_analysis = monitor.grok_api.analyze_ticket({
                'ticket_id': 'TEST001',
                'subject': 'Test abuse complaint',
                'body': 'This is a test email for system validation.',
                'sender': 'abuse@contabo.com',
                'recipient': 'tangentohost@gmail.com',
                'priority': 'medium',
                'status': 'open'
            })
            
            if 'error' not in test_analysis:
                self.stdout.write(
                    self.style.SUCCESS('✓ Grok API connection successful')
                )
            else:
                self.stdout.write(
                    self.style.WARNING('⚠ Grok API connection failed')
                )
            
            self.stdout.write(
                self.style.SUCCESS('System test completed successfully!')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'System test failed: {e}')
            )
    
    def run_uid_tracking_monitoring(self, monitor: EmailMonitor, interval_seconds: int):
        """
        Run continuous monitoring with UID tracking
        """
        self.stdout.write(
            self.style.SUCCESS(f'Starting UID tracking monitoring (checking every {interval_seconds} seconds)...')
        )
        
        try:
            monitor.run_continuous_monitoring(interval_seconds)
        except KeyboardInterrupt:
            self.stdout.write(
                self.style.SUCCESS('\nUID tracking monitoring stopped by user')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'UID tracking monitoring failed: {e}')
            )
    
    def run_single_cycle(self, monitor: EmailMonitor, days_back: int):
        """
        Run a single monitoring cycle
        """
        self.stdout.write(
            self.style.SUCCESS(f'Starting email monitoring cycle (checking last {days_back} days)...')
        )
        
        start_time = timezone.now()
        
        try:
            results = monitor.process_new_emails(days_back=days_back)
            
            # Display results
            self.stdout.write(
                self.style.SUCCESS(f'Monitoring cycle completed in {timezone.now() - start_time}')
            )
            self.stdout.write(f'Emails found: {results["emails_found"]}')
            self.stdout.write(f'Tickets created: {results["tickets_created"]}')
            self.stdout.write(f'Notifications sent: {results["notifications_sent"]}')
            
            if results['errors']:
                self.stdout.write(
                    self.style.WARNING(f'Errors encountered: {len(results["errors"])}')
                )
                for error in results['errors']:
                    self.stdout.write(f'  - {error}')
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Monitoring cycle failed: {e}')
            )
    
    def run_continuous_monitoring(self, monitor: EmailMonitor, interval_minutes: int):
        """
        Run continuous monitoring with scheduled intervals
        """
        self.stdout.write(
            self.style.SUCCESS(f'Starting continuous email monitoring (checking every {interval_minutes} minutes)...')
        )
        
        def monitoring_job():
            """Job to run monitoring cycle"""
            try:
                self.stdout.write(
                    f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] Running monitoring cycle...'
                )
                
                results = monitor.run_monitoring_cycle()
                
                if results['emails_found'] > 0:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] '
                            f'Found {results["emails_found"]} emails, '
                            f'created {results["tickets_created"]} tickets, '
                            f'sent {results["notifications_sent"]} notifications'
                        )
                    )
                else:
                    self.stdout.write(
                        f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] No new emails found'
                    )
                
                if results['errors']:
                    self.stdout.write(
                        self.style.WARNING(f'Errors: {len(results["errors"])}')
                    )
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] Monitoring cycle failed: {e}')
                )
        
        # Schedule the job
        schedule.every(interval_minutes).minutes.do(monitoring_job)
        
        # Run initial cycle
        monitoring_job()
        
        # Keep running
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
                
        except KeyboardInterrupt:
            self.stdout.write(
                self.style.SUCCESS('\nContinuous monitoring stopped by user')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Continuous monitoring failed: {e}')
            ) 