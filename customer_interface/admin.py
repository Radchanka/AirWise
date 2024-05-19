from django.contrib import admin

from .models import Airplane, Flight, Ticket, Order, Facilities, FlightFacilities, TicketFacilities

admin.site.register(Airplane)
admin.site.register(Order)
admin.site.register(Facilities)
admin.site.register(FlightFacilities)
admin.site.register(TicketFacilities)


class FlightFacilitiesInline(admin.TabularInline):
    model = FlightFacilities
    extra = 2


class FlightAdmin(admin.ModelAdmin):
    inlines = [FlightFacilitiesInline]


admin.site.register(Flight, FlightAdmin)


class TicketFacilitiesInline(admin.TabularInline):
    model = TicketFacilities
    extra = 1


class TicketAdmin(admin.ModelAdmin):
    inlines = [TicketFacilitiesInline]


admin.site.register(Ticket, TicketAdmin)
