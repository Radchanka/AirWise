from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect
from django.urls import reverse


def process_exception(request, exception):
    order_id = request.resolver_match.kwargs.get('order_id')
    if order_id and isinstance(exception, ValidationError):
        messages.error(request, str(exception))
        return HttpResponseRedirect(reverse('customer_interface:ticket_customization', kwargs={'order_id': order_id}))
