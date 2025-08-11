from django.db import models
from django.contrib.auth.models import User

class Ticket(models.Model):
    ticket_id = models.CharField(max_length=20, unique=True)
    subject = models.CharField(max_length=255)
    body = models.TextField()
    sender = models.CharField(max_length=255, default='abuse@contabo.com')
    recipient = models.CharField(max_length=255, default='tangentohost@gmail.com')
    received_at = models.DateTimeField(auto_now_add=True)
    priority = models.CharField(max_length=20, default='medium')
    status = models.CharField(max_length=20, default='open')
    ai_analysis = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.ticket_id} - {self.subject}"

class Notification(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE)
    sent_to = models.CharField(max_length=50)
    sent_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default='sent')

    def __str__(self):
        return f"Notification for {self.ticket.ticket_id}" 