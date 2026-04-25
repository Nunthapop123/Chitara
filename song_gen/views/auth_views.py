from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.models import User
from django.shortcuts import redirect, render

from song_gen.models import Library, RegisteredUser


def landing_view(request):
    return render(request, 'song_gen/landing.html')


def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        user_obj = User.objects.filter(email=email).first()
        if user_obj:
            user = authenticate(request, username=user_obj.username, password=password)
        else:
            user = None

        if user is not None:
            auth_login(request, user)
            return redirect('library')

        messages.error(request, 'Invalid email or password.')

    return render(request, 'song_gen/login.html')


def register_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')

        if not email or not password or not username:
            messages.error(request, 'All fields are required.')
        elif User.objects.filter(username=username).exists() or User.objects.filter(email=email).exists():
            messages.error(request, 'Username or Email already registered.')
        else:
            user = User.objects.create_user(username=username, email=email, password=password)
            auth_login(request, user)

            reg_user, _ = RegisteredUser.objects.get_or_create(email=email)
            Library.objects.get_or_create(owner=reg_user)

            return redirect('library')

    return render(request, 'song_gen/register.html')


def logout_view(request):
    auth_logout(request)
    return redirect('landing')


def get_or_create_user(request):
    if request.user.is_authenticated:
        user, _ = RegisteredUser.objects.get_or_create(email=request.user.email)
        Library.objects.get_or_create(owner=user)
        return user
    return None
