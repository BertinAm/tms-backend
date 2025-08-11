from django.contrib import admin
from .models import Ticket, Notification

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('ticket_id', 'subject', 'priority', 'status', 'received_at')
    list_filter = ('priority', 'status', 'received_at')
    search_fields = ('ticket_id', 'subject', 'body')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('ticket', 'sent_to', 'sent_at', 'status')
    list_filter = ('status', 'sent_at')
    search_fields = ('ticket__ticket_id', 'sent_to') 