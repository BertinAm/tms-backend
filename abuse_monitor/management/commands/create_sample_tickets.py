from django.core.management.base import BaseCommand
from abuse_monitor.models import Ticket
from datetime import datetime, timedelta

class Command(BaseCommand):
    help = 'Create sample tickets for testing the TMS system'

    def handle(self, *args, **options):
        # Clear existing sample tickets
        Ticket.objects.filter(ticket_id__startswith='SAMPLE').delete()
        
        # Sample ticket 1 - Abuse complaint
        Ticket.objects.create(
            ticket_id='SAMPLE001',
            subject='[Ticket#2025071610014137] [Action required] Your VPS 4 NVMe (213.199.52.155 - server.tangentohost.com): Unsuspension to resolve abuse complaint',
            body='''Dear Nkwenti,

Thank you for your reply.

We have unsuspended your VPS 4 NVMe (213.199.52.155 - server.tangentohost.com). Please immediately start the investigation and take adequate action to stop the server misuse. It is required that you solve the problem within the next 12 hours, and that we receive your reply within this period, too. Your reply must contain all information which enable us to understand exactly which measures you took to stop the abuse and prevent such or similar incidents in the future.

We will suspend VPS 4 NVMe (213.199.52.155 - server.tangentohost.com) access once again if there is no solution and response from you within the given time frame. If so, we will have to charge another reactivation fee.

--
Best regards,

Contabo Trust and Compliance Team

Contabo GmbH
Aschauer Straße 32a
81549 München

Web: https://contabo.com?utm_source=support&utm_medium=email

Visit us on Facebook: http://www.facebook.com/contaboCom

Amtsgericht München
HRB 180722
Authorized executives:
Dr. Christian Böing & Mario Wilhelm''',
            sender='abuse@contabo.com',
            recipient='tangentohost@gmail.com',
            priority='high',
            status='open',
            received_at=datetime.now() - timedelta(hours=2)
        )

        # Sample ticket 2 - Payment required
        Ticket.objects.create(
            ticket_id='SAMPLE002',
            subject='[Ticket#2025071610014137] [Action required] Your VPS 4 NVMe (213.199.52.155 - server.tangentohost.com): Payment needed',
            body='''Dear Nkwenti,

Thank you for your reply.

We need to charge a fee of $46.00 for the reactivation of your VPS 4 NVMe (213.199.52.155 - server.tangentohost.com) to compensate at least partially for our efforts involved in handling this case. Our efforts so far comprise reviewing the case with the complainer, communicating the issue with you, suspending server access, and now unsuspending your server. The communicative, administrative, and technical process already took a lot of time. The fee is necessary since you missed to respond in due time, which is why our efforts considerably exceeded an acceptable level. We already advised you of the reactivation fee in our first e-mail.

Please reply to this e-mail once you have sent the payment so that we can reactivate your VPS 4 NVMe (213.199.52.155 - server.tangentohost.com) and finally solve this case. If we do not receive your reply, we cannot reactivate your VPS 4 NVMe (213.199.52.155 - server.tangentohost.com), even if you have paid for the fee. Once again please be advised that the temporary suspension does not have an effect on the contract. Without your adequate reaction, the contract will keep on renewing.

Please find all information regarding the payment options in our previous e-mail.

We are looking forward to hearing from you soon.''',
            sender='abuse@contabo.com',
            recipient='tangentohost@gmail.com',
            priority='medium',
            status='open',
            received_at=datetime.now() - timedelta(hours=4)
        )

        # Sample ticket 3 - DMCA violation
        Ticket.objects.create(
            ticket_id='SAMPLE003',
            subject='[Ticket#2025071610014138] [Action required] DMCA Copyright Violation - VPS 4 NVMe (213.199.52.155)',
            body='''Dear Nkwenti,

We have received a DMCA copyright violation complaint regarding content hosted on your VPS 4 NVMe (213.199.52.155 - server.tangentohost.com). The complaint alleges that copyrighted material is being distributed without authorization.

Please immediately:
1. Remove the infringing content
2. Investigate the source of the violation
3. Implement measures to prevent future violations
4. Provide a detailed response within 12 hours

Failure to respond within the specified timeframe may result in server suspension and additional fees.

--
Best regards,

Contabo Trust and Compliance Team

Contabo GmbH
Aschauer Straße 32a
81549 München''',
            sender='abuse@contabo.com',
            recipient='tangentohost@gmail.com',
            priority='high',
            status='open',
            received_at=datetime.now() - timedelta(hours=6)
        )

        # Sample ticket 4 - Spam complaint
        Ticket.objects.create(
            ticket_id='SAMPLE004',
            subject='[Ticket#2025071610014139] [Action required] Spam Activity Detected - VPS 4 NVMe (213.199.52.155)',
            body='''Dear Nkwenti,

We have detected spam activity originating from your VPS 4 NVMe (213.199.52.155 - server.tangentohost.com). Our monitoring systems have identified multiple spam emails being sent from this server.

Please immediately:
1. Scan the server for malware
2. Review email configurations
3. Implement spam filters
4. Investigate user accounts for compromise

This is a serious violation that requires immediate attention. Please respond within 12 hours with your findings and actions taken.

--
Best regards,

Contabo Trust and Compliance Team

Contabo GmbH
Aschauer Straße 32a
81549 München''',
            sender='abuse@contabo.com',
            recipient='tangentohost@gmail.com',
            priority='high',
            status='closed',
            received_at=datetime.now() - timedelta(days=1)
        )

        # Sample ticket 5 - Resource abuse
        Ticket.objects.create(
            ticket_id='SAMPLE005',
            subject='[Ticket#2025071610014140] [Action required] Resource Abuse - VPS 4 NVMe (213.199.52.155)',
            body='''Dear Nkwenti,

We have detected excessive resource usage on your VPS 4 NVMe (213.199.52.155 - server.tangentohost.com). The server is consuming resources beyond the allocated limits, which may affect other customers.

Please:
1. Review running processes
2. Optimize resource usage
3. Implement monitoring
4. Provide usage analysis

Please respond within 24 hours with your plan to resolve this issue.

--
Best regards,

Contabo Trust and Compliance Team

Contabo GmbH
Aschauer Straße 32a
81549 München''',
            sender='abuse@contabo.com',
            recipient='tangentohost@gmail.com',
            priority='medium',
            status='open',
            received_at=datetime.now() - timedelta(hours=12)
        )

        self.stdout.write(
            self.style.SUCCESS('Successfully created 5 sample tickets for testing')
        ) 