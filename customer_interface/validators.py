from django.core.exceptions import ValidationError


def create_ticket_validator(seat_class, seat_number, flight, Ticket):
    if seat_class == 'economy':
        total_tickets = Ticket.objects.filter(flight=flight, seat_class=seat_class,
                                              status__in=['booked', 'checked_out']).count()
        all_economy_seat = set(range(1, flight.available_economy_seats + 1))
        if total_tickets >= flight.available_economy_seats:
            raise ValidationError('This flight full')
        if seat_number is not None:
            try:
                seat_number = int(seat_number)
            except ValueError:
                raise ValidationError('Not a valid seat number')

            if seat_number not in all_economy_seat:
                raise ValidationError('Not a valid seat number')
        busy_tickets = Ticket.objects.filter(flight=flight, seat_class=seat_class)
        all_busy_seats = set(ticket.seat_number for ticket in busy_tickets)
        if seat_number is not None:
            if seat_number in all_busy_seats:
                raise ValidationError('this seat is busy')

    if seat_class == 'business':
        total_tickets = Ticket.objects.filter(flight=flight, seat_class=seat_class,
                                              status__in=['booked', 'checked_out']).count()
        all_business_seat = set(range(1, flight.available_business_seats + 1))
        if total_tickets >= flight.available_business_seats:
            raise ValidationError('This flight full')
        if seat_number is not None:
            try:
                seat_number = int(seat_number)
            except ValueError:
                raise ValidationError('Not a valid seat number')

            if seat_number not in all_business_seat:
                raise ValidationError('Not a valid seat number')
        busy_tickets = Ticket.objects.filter(flight=flight, seat_class=seat_class)
        all_busy_seats = set(ticket.seat_number for ticket in busy_tickets)
        if seat_number is not None:
            if seat_number in all_busy_seats:
                raise ValidationError('this seat is busy')


def update_ticket_validator(seat_class, seat_number, flight, Ticket):
    if seat_class == 'economy':
        all_economy_seat = set(range(1, flight.available_economy_seats + 1))
        if seat_number is not None:
            try:
                seat_number = int(seat_number)
            except ValueError:
                raise ValidationError('Not a valid seat number')

            if seat_number not in all_economy_seat:
                raise ValidationError('Not a valid seat number')
        busy_tickets = Ticket.objects.filter(flight=flight, seat_class=seat_class)
        all_busy_seats = set(ticket.seat_number for ticket in busy_tickets)
        if seat_number is not None:
            if seat_number in all_busy_seats:
                raise ValidationError('this seat is busy')

    if seat_class == 'business':
        all_business_seat = set(range(1, flight.available_business_seats + 1))
        if seat_number is not None:
            try:
                seat_number = int(seat_number)
            except ValueError:
                raise ValidationError('Not a valid seat number')

            if seat_number not in all_business_seat:
                raise ValidationError('Not a valid seat number')
        busy_tickets = Ticket.objects.filter(flight=flight, seat_class=seat_class)
        all_busy_seats = set(ticket.seat_number for ticket in busy_tickets)
        if seat_number is not None:
            if seat_number in all_busy_seats:
                raise ValidationError('this seat is busy')
