from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from customer_interface.validators import create_ticket_validator, update_ticket_validator


class Airplane(models.Model):
    economy_seats = models.IntegerField(validators=[MinValueValidator(20), MaxValueValidator(60)])
    business_seats = models.IntegerField(validators=[MinValueValidator(6), MaxValueValidator(25)])

    def __str__(self):
        return f"Airplane with {self.economy_seats} economy seats and {self.business_seats} business seats"


class Facilities(models.Model):
    TYPE_CHOICES = (
        ('lunch', 'Lunch'),
        ('luggage', 'Luggage'),
    )
    facilities_name = models.CharField(max_length=20, choices=TYPE_CHOICES)

    objects = models.Manager()

    def __str__(self):
        return f"{self.facilities_name}"

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['facilities_name'], name='unique_facilities_name')
        ]


class Flight(models.Model):
    date_time_of_departure = models.DateTimeField()
    date_time_of_arrival = models.DateTimeField()
    place_of_departure = models.CharField(max_length=100)
    place_of_arrival = models.CharField(max_length=100)
    airplane = models.ForeignKey(Airplane, on_delete=models.CASCADE, related_name='flights')
    facilities = models.ManyToManyField(Facilities, through="FlightFacilities")
    available_economy_seats = models.IntegerField(editable=False, default=0)
    available_business_seats = models.IntegerField(editable=False, default=0)
    price_economy_seats = models.IntegerField(default=0)
    price_business_seats = models.IntegerField(default=0)
    price_number_economy_seats = models.IntegerField(default=0)
    price_number_business_seats = models.IntegerField(default=0)

    objects = models.Manager()

    def __str__(self):
        return f"Flight from {self.place_of_departure} to {self.place_of_arrival} at {self.date_time_of_departure}"

    def clean(self):
        if not self.pk:  # check if object is being created
            self.available_economy_seats = self.airplane.economy_seats
            self.available_business_seats = self.airplane.business_seats
        super().clean()


class FlightFacilities(models.Model):
    facilities = models.ForeignKey(Facilities, on_delete=models.CASCADE)
    flight = models.ForeignKey(Flight, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    objects = models.Manager()

    def __str__(self):
        return f"Flight {self.flight} Facilities: {self.facilities.facilities_name}"

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['facilities', 'flight'], name='unique_facilities_flight')
        ]


class Basket(models.Model):
    user = models.OneToOneField(get_user_model(), on_delete=models.CASCADE)
    tickets = models.ManyToManyField('Ticket', null=True)
    messages = models.TextField(blank=True)

    objects = models.Manager()


class Order(models.Model):
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    created_order = models.DateTimeField(auto_now_add=True)
    price = models.IntegerField(blank=True, default=0)

    objects = models.Manager()


class FacilitiesOrder(models.Model):
    ticket = models.ForeignKey('Ticket', on_delete=models.CASCADE)
    created_order = models.DateTimeField(auto_now_add=True)
    price = models.IntegerField(blank=True, default=0)

    objects = models.Manager()


class Ticket(models.Model):
    TYPE_CHOICES = (
        ('booked', 'Booked'),
        ('available', 'Available'),
        ('checked_out', 'Checked out')
    )

    flight = models.ForeignKey(Flight, on_delete=models.CASCADE)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, null=True, default=None, related_name='tickets')
    flight_facilities = models.ManyToManyField(FlightFacilities, through="TicketFacilities")
    seat_class = models.CharField(max_length=10, choices=[('economy', _('Economy')), ('business', _('Business'))])
    seat_number = models.PositiveIntegerField(blank=True, null=True, default=None)
    status = models.CharField(max_length=20, choices=TYPE_CHOICES, default='booked')
    first_name = models.CharField(max_length=100, null=True, default=None)
    last_name = models.CharField(max_length=100, null=True, default=None)
    created_at = models.DateTimeField(auto_now_add=True)
    check_in_manager = models.ForeignKey(get_user_model(), on_delete=models.CASCADE,
                                         null=True, default=None, related_name='check_tickets')
    time_check = models.DateTimeField(null=True, default=None)
    gate_manager = models.ForeignKey(get_user_model(), on_delete=models.CASCADE,
                                     null=True, default=None, related_name='check_gate_tickets')
    time_gate = models.DateTimeField(null=True, default=None)

    objects = models.Manager()

    def clean(self):
        if self._state.adding:
            create_ticket_validator(self.seat_class, self.seat_number, self.flight, Ticket)
        else:
            update_ticket_validator(self.seat_class, self.seat_number, self.flight, Ticket)


@receiver(post_save, sender=Ticket)
def schedule_deletion(sender, instance, created, **kwargs):
    from .tasks import available_ticket
    if instance.status == 'booked':
        # If the object is created for the first time and the created flag is True, schedule a deletion task.
        if created:
            available_ticket.apply_async(args=[instance.id], countdown=60)  # Schedule a task 60 seconds after saving.
        else:
            # If the object has been modified, check if more than 1 minute has passed since it was created.
            if timezone.now() - instance.created_at > timedelta(minutes=1):
                available_ticket.apply_async(args=[instance.id])


class TicketFacilities(models.Model):
    flight_facilities = models.ForeignKey(FlightFacilities, on_delete=models.CASCADE)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE)

    objects = models.Manager()

    def __str__(self):
        return f"{self.flight_facilities}"
