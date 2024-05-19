from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver
from customer_interface.models import Basket


@receiver(post_save, sender=get_user_model())
def create_basket(sender, instance, created, **kwargs):
    if created:
        Basket.objects.create(user=instance)
