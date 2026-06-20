from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.db import transaction

from .models import ProductionJob, ProductionItem, ProductionCutItem, OptimizationRun, ReusableOffcut
from .models import ProductionJobStatus
from projects.models import Project
from .services import generate_production_items, run_optimization
from quotations.pdf_generator import generate_cutting_list_pdf


def _next_job_no():
    last = ProductionJob.objects.order_by('-id').first()
    if not last:
        return 'J00001'
    try:
        num = int(last.job_no.replace('J', '')) + 1
    except Exception:
        num = 1
    return f'J{num:05d}'


@login_required
def job_list(request):
    jobs = ProductionJob.objects.select_related('project__customer', 'assigned_to').all()
    return render(request, 'production/job_list.html', {'jobs': jobs})


@login_required
def job_create(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    if request.method == 'POST':
        with transaction.atomic():
            job = ProductionJob.objects.create(
                project=project,
                job_no=_next_job_no(),
                notes=request.POST.get('notes', ''),
                created_by=request.user,
            )
        messages.success(request, f'Production job {job.job_no} created.')
        return redirect('job_detail', pk=job.pk)
    return render(request, 'production/job_create.html', {'project': project})


@login_required
def job_detail(request, pk):
    job = get_object_or_404(ProductionJob, pk=pk)
    items = job.items.select_related('system', 'glass', 'color').prefetch_related(
        'cut_items__profile', 'hardware_items__hardware')
    active_run = job.optimization_runs.filter(is_active=True).first()
    job_profile_ids = ProductionCutItem.objects.filter(
        production_item__job=job
    ).values_list('profile_id', flat=True).distinct()
    offcuts = ReusableOffcut.objects.filter(
        is_available=True, profile_id__in=job_profile_ids
    ).select_related('profile')
    return render(request, 'production/job_detail.html', {
        'job': job,
        'items': items,
        'active_run': active_run,
        'offcuts': offcuts,
        'statuses': ProductionJobStatus.choices,
    })


@login_required
def generate_items(request, pk):
    job = get_object_or_404(ProductionJob, pk=pk)
    if not job.project.can_edit(request.user) and not request.user.profile.is_admin:
        messages.error(request, 'Access denied.')
        return redirect('job_detail', pk=pk)
    try:
        generate_production_items(job)
        messages.success(request, 'Production items generated from measurements.')
    except Exception as e:
        messages.error(request, f'Error: {e}')
    return redirect('job_detail', pk=pk)


@login_required
def run_optimization_view(request, pk):
    job = get_object_or_404(ProductionJob, pk=pk)
    try:
        opt_run = run_optimization(job)
        messages.success(
            request,
            f'Optimization complete: {opt_run.total_bars_used} bars, '
            f'{opt_run.utilisation_pct}% utilisation, '
            f'{opt_run.total_waste_mm}mm waste.'
        )
    except ValueError as e:
        messages.error(request, str(e))
    except Exception as e:
        messages.error(request, f'Optimization error: {e}')
    return redirect('job_detail', pk=pk)


@login_required
def cutting_list_pdf(request, pk):
    job = get_object_or_404(ProductionJob, pk=pk)
    active_run = job.optimization_runs.filter(is_active=True).first()
    if not active_run:
        messages.error(request, 'No active optimization run. Run optimization first.')
        return redirect('job_detail', pk=pk)
    pdf_bytes = generate_cutting_list_pdf(active_run)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{job.job_no}_cutting_list.pdf"'
    return response


@login_required
def optimization_summary(request, pk):
    job = get_object_or_404(ProductionJob, pk=pk)
    active_run = job.optimization_runs.filter(is_active=True).first()
    if not active_run:
        messages.error(request, 'Run optimization first.')
        return redirect('job_detail', pk=pk)
    segments = active_run.segments.select_related('profile').prefetch_related(
        'cuts__production_item')
    return render(request, 'production/optimization_summary.html', {
        'job': job,
        'run': active_run,
        'segments': segments,
    })


@login_required
def hardware_summary(request, pk):
    job = get_object_or_404(ProductionJob, pk=pk)
    # Aggregate hardware across all items
    from django.db.models import Sum
    from .models import HardwareRequirement
    hw_totals = (
        HardwareRequirement.objects
        .filter(production_item__job=job)
        .values('hardware__stock_no', 'hardware__name', 'hardware__category',
                'hardware__unit_cost', 'unit')
        .annotate(total_qty=Sum('quantity'))
        .order_by('hardware__category', 'hardware__stock_no')
    )
    return render(request, 'production/hardware_summary.html', {
        'job': job,
        'hw_totals': hw_totals,
    })


@login_required
def glass_schedule(request, pk):
    job = get_object_or_404(ProductionJob, pk=pk)
    items = job.items.select_related('glass', 'measurement').filter(glass__isnull=False)
    return render(request, 'production/glass_schedule.html', {
        'job': job,
        'items': items,
    })


@login_required
def update_job_status(request, pk):
    job = get_object_or_404(ProductionJob, pk=pk)
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in dict(ProductionJobStatus.choices):
            job.status = new_status
            job.save()
            messages.success(request, f'Job status updated to {new_status}.')
    return redirect('job_detail', pk=pk)


@login_required
def offcut_inventory(request):
    from catalog.models import Profile

    offcuts = ReusableOffcut.objects.select_related('profile', 'source_job', 'used_in_job')
    profile_id = request.GET.get('profile')
    status = request.GET.get('status', 'available')

    if profile_id:
        offcuts = offcuts.filter(profile_id=profile_id)
    if status == 'available':
        offcuts = offcuts.filter(is_available=True)
    elif status == 'used':
        offcuts = offcuts.filter(is_available=False)
    # status == 'all' leaves the queryset unfiltered by availability

    profiles = Profile.objects.filter(is_active=True).order_by('category', 'stock_no')
    return render(request, 'production/offcut_inventory.html', {
        'offcuts': offcuts,
        'profiles': profiles,
        'selected_profile': int(profile_id) if profile_id else None,
        'selected_status': status,
    })


@login_required
def offcut_add(request):
    from catalog.models import Profile

    if request.method == 'POST':
        profile_id = request.POST.get('profile')
        length_mm = request.POST.get('length_mm')
        location_notes = request.POST.get('location_notes', '')
        try:
            profile = Profile.objects.get(pk=profile_id)
            length_mm = int(length_mm)
            if length_mm <= 0:
                raise ValueError('Length must be positive.')
        except (Profile.DoesNotExist, TypeError, ValueError) as e:
            messages.error(request, f'Could not add offcut: {e}')
            return redirect('offcut_inventory')

        ReusableOffcut.objects.create(
            profile=profile,
            length_mm=length_mm,
            location_notes=location_notes,
            is_available=True,
        )
        messages.success(request, f'Offcut added: {profile.stock_no} @ {length_mm}mm.')
        return redirect('offcut_inventory')

    profiles = Profile.objects.filter(is_active=True).order_by('category', 'stock_no')
    return render(request, 'production/offcut_add.html', {'profiles': profiles})


@login_required
def offcut_edit(request, pk):
    offcut = get_object_or_404(ReusableOffcut, pk=pk)
    if request.method == 'POST':
        length_mm = request.POST.get('length_mm')
        try:
            length_mm = int(length_mm)
            if length_mm <= 0:
                raise ValueError('Length must be positive.')
        except (TypeError, ValueError) as e:
            messages.error(request, f'Could not update offcut: {e}')
            return redirect('offcut_inventory')

        offcut.length_mm = length_mm
        offcut.location_notes = request.POST.get('location_notes', '')
        offcut.is_available = request.POST.get('is_available') == 'on'
        offcut.save()
        messages.success(request, 'Offcut updated.')
        return redirect('offcut_inventory')
    return render(request, 'production/offcut_edit.html', {'offcut': offcut})


@login_required
def offcut_delete(request, pk):
    offcut = get_object_or_404(ReusableOffcut, pk=pk)
    if request.method == 'POST':
        offcut.delete()
        messages.success(request, 'Offcut removed from inventory.')
    return redirect('offcut_inventory')


@login_required
def offcut_scrap(request, pk):
    """Mark an offcut as scrapped/unavailable without deleting its history."""
    offcut = get_object_or_404(ReusableOffcut, pk=pk)
    if request.method == 'POST':
        offcut.is_available = False
        offcut.save()
        messages.success(request, f'Offcut {offcut.profile.stock_no} @ {offcut.length_mm}mm marked as scrapped.')
    return redirect('offcut_inventory')
