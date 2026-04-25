from django.dispatch import receiver
from allauth.account.signals import user_signed_up
from song_gen.models import RegisteredUser, Library

@receiver(user_signed_up)
def user_signed_up_callback(request, user, **kwargs):
    # Automatically create the RegisteredUser extending model and the Library
    reg_user, _ = RegisteredUser.objects.get_or_create(email=user.email)
    Library.objects.get_or_create(owner=reg_user)
