from customer_interface.models import Ticket


def free_seats(flight, seat_class):
    all_seat_numbers = set(range(1, flight.available_economy_seats + 1)) if seat_class == 'economy' \
        else set(range(1, flight.available_business_seats + 1))

    busy_tickets = Ticket.objects.filter(flight=flight, seat_class=seat_class)
    all_busy_seats = set(ticket.seat_number for ticket in busy_tickets)

    return all_seat_numbers - all_busy_seats
