from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import System, Profile, Glass, Hardware

@login_required
def system_list(request):
    return render(request, 'catalog/system_list.html', {
        'systems': System.objects.filter(is_active=True).select_related('brand')
    })

@login_required
def profile_list(request):
    return render(request, 'catalog/profile_list.html', {
        'profiles': Profile.objects.filter(is_active=True).select_related('brand')
    })

@login_required
def glass_list(request):
    return render(request, 'catalog/glass_list.html', {
        'glasses': Glass.objects.filter(is_active=True)
    })

@login_required
def hardware_list(request):
    return render(request, 'catalog/hardware_list.html', {
        'hardware': Hardware.objects.filter(is_active=True).select_related('brand')
    })
