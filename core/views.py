from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from projects.models import Project, ProjectStatus
from quotations.models import Quotation


@login_required
def dashboard(request):
    projects = Project.objects.select_related('customer', 'salesman').order_by('-updated_at')[:10]
    stats = {
        'total_projects': Project.objects.count(),
        'draft': Project.objects.filter(status=ProjectStatus.DRAFT).count(),
        'quoted': Project.objects.filter(status=ProjectStatus.QUOTED).count(),
        'production': Project.objects.filter(status=ProjectStatus.PRODUCTION).count(),
        'locked': Project.objects.filter(is_locked=True).count(),
    }
    return render(request, 'core/dashboard.html', {
        'recent_projects': projects,
        'stats': stats,
    })
