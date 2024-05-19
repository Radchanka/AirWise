from django import forms
from django.forms import inlineformset_factory

from .models import Ticket, Flight, FlightFacilities


class TicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ['flight', 'seat_class']


class TicketSelectionForm(forms.Form):
    def __init__(self, *args, **kwargs):
        tickets = kwargs.pop('tickets')
        super().__init__(*args, **kwargs)
        for ticket in tickets:
            self.fields[f'ticket_{ticket.id}'] = forms.BooleanField(label=f'Ticket {ticket.id}', initial=True,
                                                                    required=False)


class SearchFlightForm(forms.Form):
    place_of_departure = forms.CharField(
        max_length=255,
        required=False,
        label="",
        widget=forms.TextInput(
            attrs={"placeholder": "Search by place of departure"}
        )
    )
    place_of_arrival = forms.CharField(
        max_length=255,
        required=False,
        label="",
        widget=forms.TextInput(
            attrs={"placeholder": "Search by place of arrival"}
        )
    )


class CreateFlight(forms.ModelForm):
    date_time_of_departure = forms.DateTimeField(
        widget=forms.DateInput(
            attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }
        )
    )

    date_time_of_arrival = forms.DateTimeField(
        widget=forms.DateInput(
            attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }
        )
    )

    class Meta:
        model = Flight
        exclude = ['available_economy_seats', 'available_business_seats', 'facilities']


class FlightFacilitiesForm(forms.ModelForm):
    class Meta:
        model = FlightFacilities
        fields = ['facilities', 'price']
        widgets = {
            'facilities': forms.Select(attrs={'class': 'form-control'}),
            'price': forms.NumberInput(attrs={'class': 'form-control'}),
        }


FlightFacilitiesFormSet = inlineformset_factory(
    Flight,
    FlightFacilities,
    form=FlightFacilitiesForm,
    extra=1,
    can_delete=False,
)


class SearchUserForm(forms.Form):
    email = forms.CharField(
        max_length=255,
        required=False,
        label="",
        widget=forms.TextInput(
            attrs={"placeholder": "Search by user email"}
        )
    )
