from django.core.management.base import BaseCommand
from abuse_monitor.email_monitor import EmailMonitor
import os
from datetime import datetime

class Command(BaseCommand):
    help = 'Export all existing emails from abuse@contabo.com to a text file'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            default='contabo_emails.txt',
            help='Output file name (default: contabo_emails.txt)',
        )
        parser.add_argument(
            '--days-back',
            type=int,
            default=365,
            help='Number of days back to search (default: 365)',
        )
    
    def handle(self, *args, **options):
        output_file = options['output']
        days_back = options['days_back']
        
        self.stdout.write(
            self.style.SUCCESS(f'Starting email export from abuse@contabo.com (last {days_back} days)...')
        )
        
        try:
            monitor = EmailMonitor()
            
            # Connect to Gmail
            imap = monitor.connect_to_gmail()
            if not imap:
                self.stdout.write(
                    self.style.ERROR('Failed to connect to Gmail')
                )
                return
            
            # Search for Contabo emails
            email_ids = monitor.search_contabo_emails(imap, days_back)
            
            if not email_ids:
                self.stdout.write(
                    self.style.WARNING('No emails found from abuse@contabo.com')
                )
                imap.close()
                imap.logout()
                return
            
            self.stdout.write(f'Found {len(email_ids)} emails from abuse@contabo.com')
            
            # Export emails to file
            exported_count = 0
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"Contabo Abuse Emails Export\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Total emails found: {len(email_ids)}\n")
                f.write("=" * 80 + "\n\n")
                
                for i, email_id in enumerate(email_ids, 1):
                    try:
                        # Extract email details
                        email_data = monitor.extract_email_details(imap, email_id)
                        if email_data:
                            f.write(f"Email #{i}\n")
                            f.write(f"Ticket ID: {email_data['ticket_id']}\n")
                            f.write(f"Subject: {email_data['subject']}\n")
                            f.write(f"From: {email_data['sender']}\n")
                            f.write(f"To: {email_data['recipient']}\n")
                            f.write(f"Date: {email_data['received_at']}\n")
                            f.write(f"Priority: {email_data['priority']}\n")
                            f.write("-" * 40 + "\n")
                            f.write(f"Body:\n{email_data['body']}\n")
                            f.write("=" * 80 + "\n\n")
                            exported_count += 1
                            
                            # Progress update
                            if i % 10 == 0:
                                self.stdout.write(f'Processed {i}/{len(email_ids)} emails...')
                    
                    except Exception as e:
                        self.stdout.write(
                            self.style.WARNING(f'Error processing email {email_id}: {e}')
                        )
            
            # Close connection
            imap.close()
            imap.logout()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Export completed! {exported_count} emails exported to {output_file}'
                )
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Export failed: {e}')
            ) 