from celery import shared_task
from django.core.exceptions import ObjectDoesNotExist
from django.utils.timezone import timedelta
from django.utils import timezone
from customer_interface.models import Ticket
from customer_interface.utils.send_tickets import send_ticket_email


@shared_task
def available_ticket(instance_id):
    """Deleting a ticket if the time limit has expired."""
    try:
        obj = Ticket.objects.get(id=instance_id)
        if obj.status == 'booked' and timezone.now() - obj.created_at > timedelta(minutes=1):
            obj.status = 'available'
            obj.save()
    except ObjectDoesNotExist:
        pass


@shared_task
def send_tickets(ticket_id, email):
    ticket = Ticket.objects.get(pk=ticket_id)
    send_ticket_email(ticket, email)
