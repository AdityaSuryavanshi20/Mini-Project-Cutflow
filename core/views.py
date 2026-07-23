from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from projects.models import Project, ProjectStatus
from quotations.models import Quotation
from core.scoping import scoped_projects


@login_required
def dashboard(request):
    base = scoped_projects(request.user)
    projects = base.select_related('customer', 'salesman').order_by('-updated_at')[:10]
    stats = {
        'total_projects': base.count(),
        'draft': base.filter(status=ProjectStatus.DRAFT).count(),
        'quoted': base.filter(status=ProjectStatus.QUOTED).count(),
        'production': base.filter(status=ProjectStatus.PRODUCTION).count(),
        'locked': base.filter(is_locked=True).count(),
    }
    return render(request, 'core/dashboard.html', {
        'recent_projects': projects,
        'stats': stats,
    })
