from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from django.conf import settings
from django.core.mail import EmailMessage
import segno


def create_ticket_pdf(ticket):
    pdf_path = f'ticket_{ticket.id}.pdf'
    c = canvas.Canvas(pdf_path, pagesize=letter)

    qr_code = segno.make(f'Ticket ID: {ticket.id}')
    qr_code_path = 'qr_code.png'  # Path to save the QR code image
    qr_code.save(qr_code_path)

    c.drawInlineImage(qr_code_path, x=400, y=675, width=100, height=100)

    flight_info = f'Flight: {ticket.flight.place_of_departure} - {ticket.flight.place_of_arrival}'
    c.drawString(45, 750, flight_info)

    flight_info_d = f'Date and Time of Departure: {ticket.flight.date_time_of_departure}'
    c.drawString(45, 720, flight_info_d)

    flight_info_a = f'Date and Time of Arrival: {ticket.flight.date_time_of_arrival}'
    c.drawString(45, 690, flight_info_a)

    passenger_info = f'Passenger: {ticket.first_name} {ticket.last_name}'
    c.drawString(45, 660, passenger_info)

    seat_info = f'Seat class: {ticket.seat_class}'
    c.drawString(45, 630, seat_info)

    y_offset = 600

    if ticket.seat_number:
        c.drawString(45, y_offset, f'Seat number: {ticket.seat_number}')
        y_offset -= 30

    facilities_list = ticket.flight_facilities.all()
    if facilities_list:
        for facility in facilities_list:
            facilities_info = f'Facilities: {facility.facilities.facilities_name}'
            c.drawString(45, y_offset, facilities_info)
            y_offset -= 30

    c.save()
    return pdf_path


def send_ticket_email(ticket, email):
    pdf_path = create_ticket_pdf(ticket)
    subject = 'Your flight ticket'
    message = 'Thank you for using our airline company.'
    email_from = settings.EMAIL_HOST_USER
    recipient_list = [email]

    email = EmailMessage(subject, message, email_from, recipient_list)
    email.attach_file(pdf_path)
    email.send()
