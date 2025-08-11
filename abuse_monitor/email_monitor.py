import imaplib
import email
import os
import logging
from email.header import decode_header
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from decouple import config
from dotenv import load_dotenv
import re
import json
import time
from itertools import chain
from django.utils import timezone
from .models import Ticket, Notification
from .grok_api import GrokAPI
# from .whatsapp_service import WhatsAppService
from .notification_service import NotificationService

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class EmailMonitor:
    """
    Automated email monitoring system for Contabo abuse complaints
    Uses improved IMAP approach with UID tracking
    """
    
    def __init__(self):
        self.gmail_user = config('GMAIL_USER', default="tangentohost@gmail.com")
        self.gmail_password = config('GMAIL_PASSWORD', default="dueaazzgfeigarug")
        self.target_sender = "abuse@contabo.com"
        self.imap_server = "imap.gmail.com"
        self.imap_port = 993
        self.grok_api = GrokAPI()
        # self.whatsapp_service = WhatsAppService()  # Disabled WhatsApp service
        
        # UID tracking for efficient email processing
        self.uid_max = 0
        self.criteria = {'FROM': self.target_sender}
        
    def search_string(self, uid_max: int, criteria: Dict[str, str]) -> str:
        """
        Produce search string in IMAP format
        """
        c = list(map(lambda t: (t[0], '"'+str(t[1])+'"'), criteria.items())) + [('UID', '%d:*' % (uid_max+1))]
        return '(%s)' % ' '.join(chain(*c))
    
    def initialize_uid_max(self) -> bool:
        """
        Initialize uid_max to track only new emails
        """
        mail = None
        try:
            mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            mail.login(self.gmail_user, self.gmail_password)
            mail.select('INBOX')
            
            result, data = mail.uid('SEARCH', None, self.search_string(self.uid_max, self.criteria))
            uids = [int(s) for s in data[0].split()]
            
            if uids:
                self.uid_max = max(uids)
                logger.info(f"Initialized uid_max to {self.uid_max}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize uid_max: {e}")
            return False
        finally:
            if mail:
                try:
                    mail.close()
                    mail.logout()
                except Exception as e:
                    logger.error(f"Error closing mail connection: {e}")
    
    def connect_to_gmail(self) -> Optional[imaplib.IMAP4_SSL]:
        """
        Establish secure connection to Gmail IMAP server
        """
        try:
            # Connect to Gmail IMAP server
            imap = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            
            # Login with credentials
            imap.login(self.gmail_user, self.gmail_password)
            
            logger.info("Successfully connected to Gmail IMAP")
            return imap
            
        except Exception as e:
            logger.error(f"Failed to connect to Gmail: {e}")
            return None
    
    def search_contabo_emails(self, imap: imaplib.IMAP4_SSL, days_back: int = 1) -> List[str]:
        """
        Search for emails from Contabo within specified time range
        """
        try:
            # Select the inbox
            imap.select('INBOX')
            
            # Calculate date range
            date_since = (datetime.now() - timedelta(days=days_back)).strftime("%d-%b-%Y")
            
            # Search for emails from Contabo
            search_criteria = f'(FROM "{self.target_sender}" SINCE {date_since})'
            status, message_numbers = imap.search(None, search_criteria)
            
            if status == 'OK':
                email_ids = message_numbers[0].split()
                logger.info(f"Found {len(email_ids)} emails from Contabo")
                return email_ids
            else:
                logger.error("Failed to search emails")
                return []
                
        except Exception as e:
            logger.error(f"Error searching emails: {e}")
            return []
    
    def search_new_emails(self, imap: imaplib.IMAP4_SSL) -> List[int]:
        """
        Search for new emails using UID tracking
        """
        try:
            imap.select('INBOX')
            result, data = imap.uid('search', None, self.search_string(self.uid_max, self.criteria))
            uids = [int(s) for s in data[0].split()]
            return uids
        except Exception as e:
            logger.error(f"Error searching new emails: {e}")
            return []
    
    def extract_email_details(self, imap: imaplib.IMAP4_SSL, email_id: bytes) -> Optional[Dict[str, Any]]:
        """
        Extract detailed information from an email
        """
        try:
            # Fetch the email
            status, msg_data = imap.fetch(email_id, '(RFC822)')
            
            if status != 'OK':
                logger.error(f"Failed to fetch email {email_id}")
                return None
            
            # Parse the email
            raw_email = msg_data[0][1]
            email_message = email.message_from_bytes(raw_email)
            
            # Extract headers
            subject = self._decode_header(email_message.get('Subject', ''))
            sender = self._decode_header(email_message.get('From', ''))
            recipient = self._decode_header(email_message.get('To', ''))
            date = email_message.get('Date', '')
            
            # Extract body content
            body = self._extract_email_body(email_message)
            
            # Generate ticket ID
            ticket_id = self._generate_ticket_id(subject, date)
            
            # Determine priority based on subject and content
            priority = self._determine_priority(subject, body)
            
            return {
                'ticket_id': ticket_id,
                'subject': subject,
                'body': body,
                'sender': sender,
                'recipient': recipient,
                'received_at': date,
                'priority': priority,
                'status': 'open',
                'email_id': email_id.decode()
            }
            
        except Exception as e:
            logger.error(f"Error extracting email details: {e}")
            return None
    
    def _decode_header(self, header: str) -> str:
        """
        Decode email header properly
        """
        try:
            decoded_parts = decode_header(header)
            decoded_string = ""
            for part, encoding in decoded_parts:
                if isinstance(part, bytes):
                    if encoding:
                        decoded_string += part.decode(encoding)
                    else:
                        decoded_string += part.decode('utf-8', errors='ignore')
                else:
                    decoded_string += str(part)
            return decoded_string
        except Exception as e:
            logger.error(f"Error decoding header: {e}")
            return str(header)
    
    def _extract_email_body(self, email_message: email.message.Message) -> str:
        """
        Extract the body content from email message
        """
        body = ""
        
        if email_message.is_multipart():
            for part in email_message.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                
                # Skip attachments
                if "attachment" in content_disposition:
                    continue
                
                # Get text content
                if content_type == "text/plain":
                    try:
                        body += part.get_payload(decode=True).decode()
                    except:
                        body += str(part.get_payload())
                elif content_type == "text/html":
                    try:
                        # Extract text from HTML
                        html_content = part.get_payload(decode=True).decode()
                        # Simple HTML to text conversion
                        html_content = re.sub(r'<[^>]+>', '', html_content)
                        html_content = re.sub(r'\s+', ' ', html_content)
                        body += html_content
                    except:
                        body += str(part.get_payload())
        else:
            # Not multipart
            content_type = email_message.get_content_type()
            if content_type == "text/plain":
                try:
                    body = email_message.get_payload(decode=True).decode()
                except:
                    body = str(email_message.get_payload())
            elif content_type == "text/html":
                try:
                    html_content = email_message.get_payload(decode=True).decode()
                    html_content = re.sub(r'<[^>]+>', '', html_content)
                    html_content = re.sub(r'\s+', ' ', html_content)
                    body = html_content
                except:
                    body = str(email_message.get_payload())
        
        return body.strip()
    
    def _generate_ticket_id(self, subject: str, date: str) -> str:
        """
        Generate a unique ticket ID based on subject and date
        """
        try:
            # Extract date components
            date_obj = email.utils.parsedate_to_datetime(date)
            date_str = date_obj.strftime("%Y%m%d")
            
            # Create hash from subject
            subject_hash = str(hash(subject))[-6:]
            
            return f"TMS{date_str}{subject_hash}"
        except:
            # Fallback to timestamp-based ID
            return f"TMS{int(timezone.now().timestamp())}"
    
    def _determine_priority(self, subject: str, body: str) -> str:
        """
        Determine priority based on subject and content keywords
        """
        content = (subject + " " + body).lower()
        
        # High priority keywords
        high_priority_keywords = [
            'urgent', 'critical', 'emergency', 'immediate', 'suspension',
            'termination', 'legal', 'dmca', 'copyright', 'law enforcement',
            'police', 'court', 'lawsuit', 'violation', 'breach'
        ]
        
        # Medium priority keywords
        medium_priority_keywords = [
            'warning', 'notice', 'complaint', 'abuse', 'spam', 'malware',
            'virus', 'attack', 'ddos', 'resource abuse', 'bandwidth'
        ]
        
        # Check for high priority
        for keyword in high_priority_keywords:
            if keyword in content:
                return 'high'
        
        # Check for medium priority
        for keyword in medium_priority_keywords:
            if keyword in content:
                return 'medium'
        
        return 'low'
    
    def save_ticket_to_database(self, email_data: Dict[str, Any]) -> Optional[Ticket]:
        """
        Save email data as a ticket in the database
        """
        try:
            # Check if ticket already exists
            existing_ticket = Ticket.objects.filter(ticket_id=email_data['ticket_id']).first()
            if existing_ticket:
                logger.info(f"Ticket {email_data['ticket_id']} already exists")
                return existing_ticket
            
            # Create new ticket
            ticket = Ticket.objects.create(
                ticket_id=email_data['ticket_id'],
                subject=email_data['subject'],
                body=email_data['body'],
                sender=email_data['sender'],
                recipient=email_data['recipient'],
                priority=email_data['priority'],
                status=email_data['status']
            )
            
            logger.info(f"Created new ticket: {ticket.ticket_id}")
            
            # Send real-time notification
            try:
                NotificationService.send_ticket_notification(ticket)
                NotificationService.send_browser_notification(ticket)
            except Exception as e:
                logger.error(f"Failed to send real-time notification: {e}")
            
            return ticket
            
        except Exception as e:
            logger.error(f"Error saving ticket to database: {e}")
            return None
    
    def analyze_ticket_with_grok(self, ticket: Ticket) -> Dict[str, Any]:
        """
        Analyze ticket using Grok AI
        """
        try:
            ticket_data = {
                'ticket_id': ticket.ticket_id,
                'subject': ticket.subject,
                'body': ticket.body,
                'sender': ticket.sender,
                'recipient': ticket.recipient,
                'priority': ticket.priority,
                'status': ticket.status,
                'received_at': ticket.received_at.isoformat() if ticket.received_at else None
            }
            
            analysis = self.grok_api.analyze_ticket(ticket_data)
            
            # Update ticket with analysis
            ticket.ai_analysis = analysis
            ticket.save()
            
            logger.info(f"Analysis completed for ticket {ticket.ticket_id}")
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing ticket with Grok: {e}")
            return {'error': str(e)}
    
    def send_whatsapp_notification(self, ticket: Ticket, analysis: Dict[str, Any]) -> bool:
        """
        Send WhatsApp notification to CEO about the new ticket
        DISABLED: WhatsApp service temporarily disabled due to pywhatkit issues on Render
        """
        try:
            # Create notification message
            message = self._create_notification_message(ticket, analysis)
        
            # WhatsApp service disabled - logging only
            logger.info(f"WhatsApp notification would be sent for ticket {ticket.ticket_id}")
            logger.info(f"Message content: {message[:100]}...")
            
            # Save notification record (for tracking purposes)
            Notification.objects.create(
                ticket=ticket,
                sent_to=config('CEO_PHONE_NUMBER', default=''),
                status='disabled'
            )
            
            return True
                
        except Exception as e:
            logger.error(f"Error in WhatsApp notification (disabled): {e}")
            return False
    
    def _create_notification_message(self, ticket: Ticket, analysis: Dict[str, Any]) -> str:
        """
        Create formatted WhatsApp notification message
        """
        urgency_emoji = {
            'high': '🔴',
            'medium': '🟡', 
            'low': '🟢'
        }
        
        urgency = urgency_emoji.get(ticket.priority, '⚪')
        
        message = f"""
🚨 NEW CONTABO ABUSE TICKET {urgency}

Ticket ID: {ticket.ticket_id}
Subject: {ticket.subject}
Priority: {ticket.priority.upper()}
Received: {ticket.received_at.strftime('%Y-%m-%d %H:%M')}

📋 ANALYSIS:
"""
        
        if 'error' not in analysis:
            if analysis.get('key_issues'):
                message += f"Key Issues: {', '.join(analysis['key_issues'][:3])}\n"
            
            if analysis.get('urgency_level'):
                message += f"Urgency: {analysis['urgency_level'].upper()}\n"
            
            if analysis.get('recommended_actions'):
                message += f"Actions: {', '.join(analysis['recommended_actions'][:2])}\n"
            
            if analysis.get('threat_assessment'):
                threat = analysis['threat_assessment'][:100] + "..." if len(analysis['threat_assessment']) > 100 else analysis['threat_assessment']
                message += f"Assessment: {threat}\n"
        else:
            message += "Analysis: Unable to analyze ticket\n"
        
        message += f"\n🔗 View in TMS: http://localhost:8000/admin/abuse_monitor/ticket/{ticket.id}/"
        
        return message
    
    def process_new_emails(self, days_back: int = 1) -> Dict[str, Any]:
        """
        Main method to process new emails from Contabo
        """
        results = {
            'emails_found': 0,
            'tickets_created': 0,
            'notifications_sent': 0,
            'errors': []
        }
        
        try:
            # Connect to Gmail
            imap = self.connect_to_gmail()
            if not imap:
                results['errors'].append("Failed to connect to Gmail")
                return results
            
            # Search for Contabo emails
            email_ids = self.search_contabo_emails(imap, days_back)
            results['emails_found'] = len(email_ids)
            
            for email_id in email_ids:
                try:
                    # Extract email details
                    email_data = self.extract_email_details(imap, email_id)
                    if not email_data:
                        continue
                    
                    # Save to database
                    ticket = self.save_ticket_to_database(email_data)
                    if not ticket:
                        continue
                    
                    results['tickets_created'] += 1
                    
                    # Analyze with Grok
                    analysis = self.analyze_ticket_with_grok(ticket)
                    
                    # Send WhatsApp notification
                    if self.send_whatsapp_notification(ticket, analysis):
                        results['notifications_sent'] += 1
                    
                except Exception as e:
                    logger.error(f"Error processing email {email_id}: {e}")
                    results['errors'].append(f"Email {email_id}: {str(e)}")
            
            # Close connection
            imap.close()
            imap.logout()
            
        except Exception as e:
            logger.error(f"Error in process_new_emails: {e}")
            results['errors'].append(str(e))
        
        logger.info(f"Email processing completed: {results}")
        return results
    
    def run_continuous_monitoring(self, interval_seconds: int = 60) -> None:
        """
        Run continuous monitoring with UID tracking
        """
        logger.info("Starting continuous email monitoring...")
        
        # Initialize uid_max
        if not self.initialize_uid_max():
            logger.error("Failed to initialize UID tracking")
            return
        
        while True:
            try:
                # Connect to Gmail
                mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
                mail.login(self.gmail_user, self.gmail_password)
                mail.select('INBOX')
                
                # Search for new emails
                result, data = mail.uid('search', None, self.search_string(self.uid_max, self.criteria))
                uids = [int(s) for s in data[0].split()]
                
                for uid in uids:
                    # Check if this is a new email
                    if uid > self.uid_max:
                        try:
                            # Fetch email data
                            result, data = mail.uid('fetch', str(uid), '(RFC822)')
                            
                            for response_part in data:
                                if isinstance(response_part, tuple):
                                    # Parse email
                                    email_message = email.message_from_bytes(response_part[1])
                                    
                                    # Extract email details
                                    email_data = self.extract_email_details_from_message(email_message, uid)
                                    if email_data:
                                        # Process the email
                                        self.process_single_email(email_data)
                            
                            # Update uid_max
                            self.uid_max = uid
                            
                        except Exception as e:
                            logger.error(f"Error processing email {uid}: {e}")
                
                # Close connection
                mail.logout()
                
                # Wait before next check
                time.sleep(interval_seconds)
                
            except Exception as e:
                logger.error(f"Error in continuous monitoring: {e}")
                time.sleep(interval_seconds)
    
    def extract_email_details_from_message(self, email_message: email.message.Message, uid: int) -> Optional[Dict[str, Any]]:
        """
        Extract email details from parsed email message
        """
        try:
            # Extract headers
            subject = self._decode_header(email_message.get('Subject', ''))
            sender = self._decode_header(email_message.get('From', ''))
            recipient = self._decode_header(email_message.get('To', ''))
            date = email_message.get('Date', '')
            
            # Extract body content
            body = self._extract_email_body(email_message)
            
            # Generate ticket ID
            ticket_id = self._generate_ticket_id(subject, date)
            
            # Determine priority
            priority = self._determine_priority(subject, body)
            
            return {
                'ticket_id': ticket_id,
                'subject': subject,
                'body': body,
                'sender': sender,
                'recipient': recipient,
                'received_at': date,
                'priority': priority,
                'status': 'open',
                'email_id': str(uid)
            }
            
        except Exception as e:
            logger.error(f"Error extracting email details from message: {e}")
            return None
    
    def process_single_email(self, email_data: Dict[str, Any]) -> None:
        """
        Process a single email
        """
        try:
            # Save to database
            ticket = self.save_ticket_to_database(email_data)
            if not ticket:
                return
            
            # Analyze with Grok
            analysis = self.analyze_ticket_with_grok(ticket)
            
            # Send WhatsApp notification
            self.send_whatsapp_notification(ticket, analysis)
            
            logger.info(f"Processed new email: {ticket.ticket_id}")
            
        except Exception as e:
            logger.error(f"Error processing single email: {e}")
    
    def run_monitoring_cycle(self) -> Dict[str, Any]:
        """
        Run a complete monitoring cycle (check last 24 hours)
        """
        logger.info("Starting email monitoring cycle")
        return self.process_new_emails(days_back=1) 