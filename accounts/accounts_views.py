from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import UserProfile, UserRole


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user and hasattr(user, 'profile') and user.profile.is_active:
            login(request, user)
            next_url = request.GET.get('next', 'dashboard')
            return redirect(next_url)
        messages.error(request, 'Invalid credentials or account inactive.')
    return render(request, 'accounts/login.html')


def logout_view(request):
    # Only log out on POST to prevent logout CSRF: a crafted GET request
    # to /accounts/logout/ from any page (e.g. an <img> tag) would otherwise
    # silently kill the user's session. Django 5's built-in LogoutView also
    # enforces POST-only for this reason.
    if request.method == 'POST':
        logout(request)
    return redirect('login')


@login_required
def profile_view(request):
    profile = request.user.profile
    if request.method == 'POST':
        user = request.user
        user.first_name = request.POST.get('first_name', '')
        user.last_name = request.POST.get('last_name', '')
        user.email = request.POST.get('email', '')
        user.save()
        profile.phone = request.POST.get('phone', '')
        if 'avatar' in request.FILES:
            profile.avatar = request.FILES['avatar']
        profile.save()
        messages.success(request, 'Profile updated.')
        return redirect('profile')
    return render(request, 'accounts/profile.html', {'profile': profile})


@login_required
def change_password(request):
    if request.method == 'POST':
        old_pw = request.POST.get('old_password')
        new_pw = request.POST.get('new_password')
        confirm = request.POST.get('confirm_password')
        if new_pw != confirm:
            messages.error(request, 'Passwords do not match.')
        elif not request.user.check_password(old_pw):
            messages.error(request, 'Current password is incorrect.')
        else:
            request.user.set_password(new_pw)
            request.user.save()
            messages.success(request, 'Password changed. Please log in again.')
            return redirect('login')
    return render(request, 'accounts/change_password.html')
