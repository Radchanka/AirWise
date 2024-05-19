import json
import time

from datetime import datetime
from functools import wraps

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.views import generic, View

from rest_framework.views import APIView
from rest_framework.response import Response
from .decorators import process_exception
from .forms import TicketForm, TicketSelectionForm, SearchFlightForm, CreateFlight, FlightFacilitiesFormSet, \
    SearchUserForm
from .models import Ticket, Order, Basket, TicketFacilities, FlightFacilities, Flight, FacilitiesOrder
from .tasks import send_tickets
from .utils.ticket_seats import free_seats
from .utils.wayforpay import create_request_params, send_request, handle_response, generate_response_signature, \
    SECRET_KEY, decode_order_reference, generate_hmac
from .validators import update_ticket_validator, create_ticket_validator


class IndexView(LoginRequiredMixin, generic.ListView):
    """
        View for displaying a list of available flights.
    """
    model = Flight
    template_name = "base_user_interface.html"
    login_url = reverse_lazy('users:login')

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data()
        user = self.request.user
        basket = Basket.objects.get(user=user)
        basket_items_count = basket.tickets.count()
        place_of_departure = self.request.GET.get("place_of_departure", "")
        place_of_arrival = self.request.GET.get("place_of_arrival", "")
        context["place_of_departure"] = place_of_departure
        context["place_of_arrival"] = place_of_arrival
        context['basket_items_count'] = basket_items_count
        context['search_form'] = SearchFlightForm(
            initial={
                "place_of_departure": place_of_departure,
                "place_of_arrival": place_of_arrival,
            }
        )

        flight_tickets = {}
        check_in_tickets = {}
        gate_tickets = {}
        for flight in context['object_list']:
            tickets_count = Ticket.objects.filter(flight=flight, status='checked_out').count()
            tickets_check_in = Ticket.objects.filter(flight=flight, status='checked_out',
                                                     check_in_manager__isnull=False).count()
            tickets_gate = Ticket.objects.filter(flight=flight, status='checked_out',
                                                 gate_manager__isnull=False).count()
            flight_tickets[flight.pk] = tickets_count
            check_in_tickets[flight.pk] = tickets_check_in
            gate_tickets[flight.pk] = tickets_gate
        context['flight_tickets'] = flight_tickets
        context['check_in_tickets'] = check_in_tickets
        context['gate_tickets'] = gate_tickets
        return context

    def get_queryset(self):
        place_of_departure = self.request.GET.get("place_of_departure")
        place_of_arrival = self.request.GET.get("place_of_arrival")

        queryset = super().get_queryset()

        if place_of_departure and place_of_arrival:
            queryset = queryset.filter(
                place_of_departure__icontains=place_of_departure,
                place_of_arrival__icontains=place_of_arrival,
            )
        if place_of_departure:
            queryset = queryset.filter(
                place_of_departure__icontains=place_of_departure,
            )
        if place_of_arrival:
            queryset = queryset.filter(
                place_of_arrival__icontains=place_of_arrival,
            )

        return queryset


class FlightDetailView(generic.DetailView):
    """
       View for displaying detailed information about a specific flight.
    """
    model = Flight
    template_name = 'customer_interface/flight_detail.html'

    def post(self, request, *args, **kwargs):
        flight = self.get_object()
        user = request.user
        basket = Basket.objects.get(user=user)

        if request.method == "POST" and 'add_economy' in request.POST:
            seat_class = 'economy'
        else:
            seat_class = 'business'

        ticket = Ticket(flight=flight, seat_class=seat_class)
        try:
            create_ticket_validator(ticket.seat_class, ticket.seat_number, ticket.flight, Ticket)
            available_tickets = Ticket.objects.filter(
                flight=ticket.flight,
                status='available',
                seat_class=seat_class
            )

            if available_tickets.exists():
                available_ticket = available_tickets.first()
                basket_overdue = Basket.objects.filter(tickets=available_ticket).first()
                basket_overdue.messages += f'\nDue to the fact that you did not buy the ticket within 30 minutes and it was bought by another user we have removed Flight: {available_ticket.flight} Seat: {available_ticket.seat_class} from your cart.'
                basket_overdue.save()
                available_ticket.delete()

            ticket.save()
            basket.tickets.add(ticket)

        except ValidationError as e:
            error_message = str(e)
            available_economy_seats = flight.available_economy_seats
            available_business_seats = flight.available_business_seats
            total_economy_tickets = Ticket.objects.filter(flight=flight, seat_class='economy',
                                                          status__in=['booked', 'checked_out']).count()
            total_business_tickets = Ticket.objects.filter(flight=flight, seat_class='business',
                                                           status__in=['booked', 'checked_out']).count()
            available_economy_seats -= total_economy_tickets
            available_business_seats -= total_business_tickets

            free_economy_seats = free_seats(flight, seat_class='economy')
            free_business_seats = free_seats(flight,
                                             seat_class='business')  # This function returns the set of free spaces in the class

            return render(request, self.template_name, {
                'flight': flight,
                'error_message': error_message,
                'available_economy_seats': available_economy_seats,
                'available_business_seats': available_business_seats,
                'free_economy_seats': free_economy_seats,
                'free_business_seats': free_business_seats
            })

        return redirect('customer_interface:flight_detail', pk=flight.pk)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        flight = self.get_object()
        user = self.request.user
        basket = Basket.objects.get(user=user)
        basket_items_count = basket.tickets.count()
        available_economy_seats = flight.available_economy_seats
        available_business_seats = flight.available_business_seats
        total_economy_tickets = Ticket.objects.filter(flight=flight, seat_class='economy',
                                                      status__in=['booked', 'checked_out']).count()
        total_business_tickets = Ticket.objects.filter(flight=flight, seat_class='business',
                                                       status__in=['booked', 'checked_out']).count()
        available_economy_seats -= total_economy_tickets
        available_business_seats -= total_business_tickets

        free_economy_seats = free_seats(flight, seat_class='economy')
        free_business_seats = free_seats(flight,
                                         seat_class='business')  # This function returns the set of free spaces in the class

        context['free_economy_seats'] = free_economy_seats
        context['free_business_seats'] = free_business_seats
        context['available_economy_seats'] = available_economy_seats
        context['available_business_seats'] = available_business_seats
        context['basket_items_count'] = basket_items_count
        return context


def basket_view(request):
    """
        View for managing the user's shopping basket.
    """
    user = request.user
    basket = Basket.objects.get(user=user)
    tickets = basket.tickets.all()

    if request.method == 'POST':
        if 'add_ticket' in request.POST:
            ticket_form = TicketForm(request.POST)
            if ticket_form.is_valid():
                ticket = ticket_form.save(commit=False)
                create_ticket_validator(ticket.seat_class, ticket.seat_number, ticket.flight, Ticket)
                if ticket.seat_class == 'economy':
                    # Check if there are already available tickets for this flight
                    available_tickets = Ticket.objects.filter(
                        flight=ticket.flight,
                        status='available',
                        seat_class='economy'
                    )
                else:
                    available_tickets = Ticket.objects.filter(
                        flight=ticket.flight,
                        status='available',
                        seat_class='business')

                if available_tickets.exists():
                    # If there are available tickets, delete one of them
                    available_ticket = available_tickets.first()
                    basket_overdue = Basket.objects.filter(tickets=available_ticket).first()
                    basket_overdue.messages += f'\nDue to the fact that you did not buy the ticket within 30 minutes and it was bought by another user we have removed Flight: {available_ticket.flight} Seat: {available_ticket.seat_class} from your cart.'
                    basket_overdue.save()
                    available_ticket.delete()

                ticket.save()
                basket.tickets.add(ticket)
                return redirect('customer_interface:basket')
            else:
                return render(request, 'customer_interface/basket.html',
                              {'tickets': tickets, 'ticket_form': ticket_form})

        if 'delete_ticket' in request.POST:
            ticket_id = request.POST.get('ticket_id')
            ticket_to_delete = Ticket.objects.get(id=ticket_id)
            ticket_to_delete.delete()
            return redirect('customer_interface:basket')

        if 'next' in request.POST:
            return redirect('customer_interface:create_order')

    basket_messages = basket.messages.split("\n") if basket.messages else []
    basket.messages = ""
    basket.save()

    ticket_form = TicketForm()

    return render(request, 'customer_interface/basket.html',
                  {'tickets': tickets, 'ticket_form': ticket_form, 'basket_messages': basket_messages})


def delete_ticket(request, ticket_id):
    """
        View for deleting a ticket from the shopping basket.
    """
    ticket = get_object_or_404(Ticket, id=ticket_id)
    ticket.delete()
    return redirect('customer_interface:basket')


@transaction.atomic
def create_order(request):
    """
        View for creating an order from the tickets in the shopping basket.
    """
    user = request.user
    basket = Basket.objects.get(user=user)
    tickets = basket.tickets.all()

    if request.method == "POST" and 'create_order' in request.POST:
        order_form = TicketSelectionForm(request.POST, tickets=tickets)
        if order_form.is_valid():
            if any(order_form.cleaned_data.get(f'ticket_{ticket.id}') for ticket in tickets):
                order = Order.objects.create(user=user)
                for ticket in tickets:
                    if order_form.cleaned_data.get(f'ticket_{ticket.id}'):
                        ticket.order = order
                        ticket.save()

                        basket.tickets.remove(ticket)
                return redirect('customer_interface:ticket_customization', order_id=order.id)
            else:
                messages.error(request, "You must select at least 1 ticket to place an order.")
                order_form = TicketSelectionForm(tickets=tickets)
    else:
        order_form = TicketSelectionForm(tickets=tickets)

    return render(request, 'customer_interface/create_order.html', {'order_form': order_form, 'tickets': tickets})


def handle_exception(view_func):
    """
        Decorator to handle exceptions raised by view functions.
    """

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        try:
            return view_func(request, *args, **kwargs)
        except Exception as e:
            response = process_exception(request, e)
            if response:
                return response
            else:
                raise

    return _wrapped_view


@handle_exception
def ticket_customization(request, order_id):
    """
        View for customizing tickets before finalizing the order.
    """
    order = Order.objects.get(id=order_id)  # Receiving the order
    order_tickets = order.tickets.all()  # Here I use related_name (tickets) to get all tickets associated with the order.

    if request.method == 'POST':
        with transaction.atomic():  # Creating a transaction
            for ticket in order_tickets:
                facilities_ids = request.POST.getlist(f'facilities_{ticket.id}')
                # Add new links for the selected amenities
                for facility_id in facilities_ids:
                    TicketFacilities.objects.create(
                        ticket=ticket,
                        flight_facilities=FlightFacilities.objects.get(id=facility_id),
                    )

                seat_number = request.POST.get(f'seat_number_{ticket.id}', None)
                if seat_number == '':
                    seat_number = None
                update_ticket_validator(ticket.seat_class, seat_number, ticket.flight, Ticket)
                ticket.seat_number = seat_number
                first_name = request.POST.get(f'first_name_{ticket.id}')
                last_name = request.POST.get(f'last_name_{ticket.id}')
                ticket.first_name = first_name
                ticket.last_name = last_name
                ticket.save()

                if ticket.seat_class == 'economy':
                    order.price += ticket.flight.price_economy_seats
                    if ticket.seat_number:
                        order.price += ticket.flight.price_number_economy_seats
                else:
                    order.price += ticket.flight.price_business_seats
                    if ticket.seat_number:
                        order.price += ticket.flight.price_number_business_seats

                if ticket.flight_facilities.exists():
                    for ticket_facility in ticket.ticketfacilities_set.all():
                        order.price += ticket_facility.flight_facilities.price

                order.save()

        return redirect('customer_interface:buy_order', order_id=order_id)

    # Extract unique flights from the ticket list
    unique_flights = set(ticket.flight for ticket in order_tickets)

    # We get the available seats for each flight
    free_economy_seats = {}
    free_business_seats = {}
    for flight in unique_flights:
        free_economy_seats = free_seats(flight, seat_class='economy')
        free_business_seats = free_seats(flight, seat_class='business')

    ticket_info = []
    for ticket in order_tickets:
        flight_facilities = FlightFacilities.objects.filter(flight=ticket.flight)
        ticket_info.append({'ticket': ticket, 'facilities': flight_facilities})

    return render(request, 'customer_interface/ticket_customization.html', {
        'order_id': order_id,
        'free_economy_seats': free_economy_seats,
        'free_business_seats': free_business_seats,
        'ticket_info': ticket_info,
    })


@transaction.atomic
def buy_order(request, order_id):
    """
        View for finalizing and purchasing an order.
    """
    order = Order.objects.get(id=order_id)
    order_tickets = order.tickets.all()

    if request.method == 'POST':
        request_params = create_request_params(order.price, order.user.email, order_tickets.count(), order_id)
        response = send_request(request_params)
        result = handle_response(response)
        print(result)

        return redirect('customer_interface:basket')

    return render(request, 'customer_interface/buy_order.html', {
        'order': order,
        'order_tickets': order_tickets,
    })


class WayForPayCallback(APIView):
    """
        Callback API view for processing payment responses from WayForPay.
    """

    def post(self, request):
        print(request.data)
        data_string = list(request.data.keys())[0]
        data_dict = json.loads(data_string)

        # Доступ к параметру orderReference
        orderReference = data_dict.get("orderReference")
        code = data_dict.get("reasonCode")
        time_now = int(time.time())
        print(time_now)
        print(code)
        print(data_dict)
        print(orderReference)
        order_id = decode_order_reference(orderReference)
        print(order_id)

        if code == 1100:
            order = Order.objects.get(id=order_id)
            order_tickets = order.tickets.all()

            for ticket in order_tickets:
                ticket.status = 'checked_out'
                ticket.save()

                send_tickets.apply_async(args=[ticket.id, ticket.order.user.email])

        # Отправить ответ WayForPay о принятии заказа
        response_data = {
            "orderReference": orderReference,
            "status": "accept",
            "time": time_now,
        }

        data_to_sign = [
            response_data["orderReference"],
            response_data["status"],
            str(response_data["time"]),
        ]
        print(response_data)
        response_data["signature"] = generate_hmac(data_to_sign, SECRET_KEY)
        print(response_data)

        return Response(response_data)


@permission_required(perm='customer_interface.view_ticket', raise_exception=True)
def ticket_input(request):
    """
        View for inputting ticket information.
    """
    if request.method == 'POST':
        ticket_id = request.POST.get('ticket_id')
        return redirect('customer_interface:ticket_detail', ticket_id=ticket_id)
    return render(request, 'customer_interface/ticket_input.html')


@permission_required(perm='customer_interface.view_ticket', raise_exception=True)
def ticket_detail(request, ticket_id):
    """
        View for displaying detailed information about a ticket.
    """
    user = request.user
    ticket = Ticket.objects.get(id=ticket_id)
    flight = ticket.flight
    facilities_price = 0

    if request.method == 'POST':
        ticket.check_in_manager = user
        ticket.time_check = datetime.now()

        try:
            with transaction.atomic():
                facilities_ids = request.POST.getlist(f'facilities_{ticket.id}')
                # Добавляем новые связи только для выбранных удобств
                for facility_id in facilities_ids:
                    facilities = TicketFacilities.objects.create(
                        ticket=ticket,
                        flight_facilities=FlightFacilities.objects.get(id=facility_id),
                    )
                    facilities_price += facilities.flight_facilities.price

                seat_number = request.POST.get('seat_number')
                if seat_number:
                    update_ticket_validator(ticket.seat_class, seat_number, ticket.flight, Ticket)
                    ticket.seat_number = seat_number
                    if ticket.seat_class == 'economy':
                        facilities_price += ticket.flight.price_number_economy_seats
                    else:
                        facilities_price += ticket.flight.price_number_business_seats

                ticket.save()
        except ValidationError as e:
            error_message = str(e)

            flight_facilities = FlightFacilities.objects.filter(flight=ticket.flight)

            free_economy_seats = free_seats(flight, seat_class='economy')
            free_business_seats = free_seats(flight, seat_class='business')

            return render(request, 'customer_interface/ticket_detail.html', {
                'ticket': ticket,
                'flight_facilities': flight_facilities,
                'free_economy_seats': free_economy_seats,
                'free_business_seats': free_business_seats,
                'error_message': error_message,
            })

        if facilities_price:
            FacilitiesOrder.objects.create(
                ticket=ticket,
                price=facilities_price
            )

        send_tickets.apply_async(args=[ticket.id, user.email])

        return redirect('customer_interface:ticket_input')

    flight_facilities = FlightFacilities.objects.filter(flight=ticket.flight)
    ticket_facility_ids = ticket.flight_facilities.values_list('id', flat=True)

    free_economy_seats = free_seats(flight, seat_class='economy')
    free_business_seats = free_seats(flight, seat_class='business')

    return render(request, 'customer_interface/ticket_detail.html', {
        'ticket': ticket,
        'flight_facilities': flight_facilities,
        'ticket_facility_ids': ticket_facility_ids,
        'free_economy_seats': free_economy_seats,
        'free_business_seats': free_business_seats,
    })


@permission_required(perm='customer_interface.add_ticket', raise_exception=True)
def ticket_gate(request):
    """
    View for managing gate access for tickets.
    """

    user = request.user
    if request.method == 'POST':
        ticket_id = request.POST.get('ticket_id')
        ticket = Ticket.objects.get(id=ticket_id)
        ticket.gate_manager = user
        ticket.time_gate = datetime.now()
        ticket.save()
    return render(request, 'customer_interface/ticket_gate.html')


class CreateFlightView(PermissionRequiredMixin, LoginRequiredMixin, View):
    """
        View for creating a new flight.
    """
    login_url = reverse_lazy('users:login')
    permission_required = 'customer_interface.add_flight'

    def get(self, request):
        flight_form = CreateFlight()
        flight_facilities_formset = FlightFacilitiesFormSet(instance=Flight())
        context = {
            'flight_form': flight_form,
            'flight_facilities_formset': flight_facilities_formset,
        }
        return render(request, 'customer_interface/create_flight.html', context)

    def post(self, request):
        flight_form = CreateFlight(request.POST)
        flight_facilities_formset = FlightFacilitiesFormSet(request.POST, instance=Flight())

        if 'add_facility' in request.POST:
            if flight_facilities_formset.is_valid():
                flight_facilities_formset = FlightFacilitiesFormSet(instance=Flight(), queryset=Flight.objects.none())
                flight_facilities_formset.extra += 1
                context = {
                    'flight_form': flight_form,
                    'flight_facilities_formset': flight_facilities_formset,
                }
                return render(request, 'customer_interface/create_flight.html', context)
        elif flight_form.is_valid() and flight_facilities_formset.is_valid():
            flight = flight_form.save()
            flight_facilities_formset.instance = flight
            flight_facilities_formset.save()
            return redirect('customer_interface:basket')
        else:
            context = {
                'flight_form': flight_form,
                'flight_facilities_formset': flight_facilities_formset,
            }
            return render(request, 'customer_interface/create_flight.html', context)


class UsersList(PermissionRequiredMixin, LoginRequiredMixin, generic.ListView):
    """
        View for displaying a list of users.
    """
    model = get_user_model()
    template_name = "customer_interface/users_list.html"
    login_url = reverse_lazy('users:login')
    permission_required = 'customer_interface.add_flight'

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data()
        email = self.request.GET.get("email", "")
        context["email"] = email
        context['search_form'] = SearchUserForm(
            initial={"email": email}
        )
        gate_manager_group = Group.objects.get(name="gate_manager")
        check_in_manager_group = Group.objects.get(name="check_in_manager")
        context['check_in_manager_group'] = check_in_manager_group
        context['gate_manager_group'] = gate_manager_group
        return context

    def get_queryset(self):
        email = self.request.GET.get("email")
        queryset = super().get_queryset()

        queryset = queryset.filter(is_superuser=False)

        if email:
            queryset = queryset.filter(email__icontains=email)

        return queryset


class SaveUserGroupsView(View):
    """
        View for saving user group assignments.
    """

    def post(self, request, *args, **kwargs):
        email = request.POST.get("email")
        check_in_manager_group = Group.objects.get(name='check_in_manager')
        gate_manager_group = Group.objects.get(name='gate_manager')

        check_in_manager_users = request.POST.getlist('check_in_manager_users[]')
        gate_manager_users = request.POST.getlist('gate_manager_users[]')

        users_to_update = get_user_model().objects.filter(is_superuser=False)

        for user in users_to_update:
            if str(user.id) in check_in_manager_users:

                if check_in_manager_group not in user.groups.all():
                    user.groups.add(check_in_manager_group)
            else:

                if check_in_manager_group in user.groups.all():
                    user.groups.remove(check_in_manager_group)

            if str(user.id) in gate_manager_users:

                if gate_manager_group not in user.groups.all():
                    user.groups.add(gate_manager_group)
            else:

                if gate_manager_group in user.groups.all():
                    user.groups.remove(gate_manager_group)

        return HttpResponseRedirect(reverse('customer_interface:users_list') + "?email=" + email)


@permission_required(perm='customer_interface.view_flight', raise_exception=True)
def flight_stats(request, pk):
    """
        View for displaying statistics about a specific flight.
    """
    flight = get_object_or_404(Flight, pk=pk)
    tickets = Ticket.objects.filter(flight=flight)
    total_economy_tickets = Ticket.objects.filter(flight=flight, seat_class='economy', status='checked_out').count()
    total_business_tickets = Ticket.objects.filter(flight=flight, seat_class='business', status='checked_out').count()
    return render(request, 'customer_interface/flight_stats.html', {
        'flight': flight,
        'tickets': tickets,
        'total_economy_tickets': total_economy_tickets,
        'total_business_tickets': total_business_tickets,
    })
