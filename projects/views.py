from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db import transaction
from .models import Customer, Project, MeasurementItem, ProjectStatus, ProjectStatusHistory
from catalog.models import System, Color, Glass
import json


@login_required
def customer_list(request):
    qs = Customer.objects.all()
    q = request.GET.get('q', '')
    if q:
        qs = qs.filter(name__icontains=q) | qs.filter(phone__icontains=q)
    return render(request, 'projects/customer_list.html', {'customers': qs, 'q': q})


@login_required
def customer_create(request):
    if request.method == 'POST':
        c = Customer.objects.create(
            name=request.POST['name'],
            company=request.POST.get('company', ''),
            phone=request.POST.get('phone', ''),
            email=request.POST.get('email', ''),
            address_line1=request.POST.get('address_line1', ''),
            address_line2=request.POST.get('address_line2', ''),
            city=request.POST.get('city', ''),
            state=request.POST.get('state', ''),
            pincode=request.POST.get('pincode', ''),
            notes=request.POST.get('notes', ''),
            created_by=request.user,
        )
        messages.success(request, f'Customer "{c.name}" created.')
        return redirect('customer_detail', pk=c.pk)
    return render(request, 'projects/customer_form.html', {'action': 'Create'})


@login_required
def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    projects = customer.projects.all()
    return render(request, 'projects/customer_detail.html',
                  {'customer': customer, 'projects': projects})


@login_required
def project_list(request):
    qs = Project.objects.select_related('customer', 'salesman').all()
    status_filter = request.GET.get('status', '')
    if status_filter:
        qs = qs.filter(status=status_filter)
    return render(request, 'projects/project_list.html', {
        'projects': qs,
        'statuses': ProjectStatus.choices,
        'status_filter': status_filter,
    })


@login_required
def project_create(request):
    if request.method == 'POST':
        ref = request.POST.get('reference', '').strip()
        if Project.objects.filter(reference=ref).exists():
            messages.error(request, 'Reference already exists.')
            return render(request, 'projects/project_form.html', {
                'action': 'Create', 'customers': Customer.objects.all(), 'post': request.POST})
        with transaction.atomic():
            p = Project.objects.create(
                reference=ref,
                name=request.POST['name'],
                customer_id=request.POST['customer'],
                salesman=request.user,
                site_address=request.POST.get('site_address', ''),
                notes=request.POST.get('notes', ''),
                created_by=request.user,
            )
            ProjectStatusHistory.objects.create(
                project=p, from_status='', to_status=p.status, changed_by=request.user)
        messages.success(request, f'Project {p.reference} created.')
        return redirect('project_detail', pk=p.pk)
    return render(request, 'projects/project_form.html', {
        'action': 'Create', 'customers': Customer.objects.all()})


@login_required
def project_detail(request, pk):
    project = get_object_or_404(Project, pk=pk)
    measurements = project.measurements.select_related('system', 'glass', 'color').all()
    return render(request, 'projects/project_detail.html', {
        'project': project,
        'measurements': measurements,
        'systems': System.objects.filter(is_active=True),
        'glasses': Glass.objects.filter(is_active=True),
        'colors': Color.objects.filter(is_active=True),
    })


@login_required
def measurement_add(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    if not project.can_edit(request.user):
        messages.error(request, 'Project is locked.')
        return redirect('project_detail', pk=project_pk)
    if request.method == 'POST':
        # Auto line_no
        existing = project.measurements.count()
        line_no = f"{existing + 1:04d}"
        MeasurementItem.objects.create(
            project=project,
            line_no=line_no,
            reference=request.POST.get('reference', f'W{existing+1}'),
            location=request.POST.get('location', ''),
            system_id=request.POST['system'],
            glass_id=request.POST.get('glass') or None,
            color_id=request.POST.get('color') or None,
            width=int(request.POST['width']),
            height=int(request.POST['height']),
            qty=int(request.POST.get('qty', 1)),
            description=request.POST.get('description', ''),
            n_panels=int(request.POST.get('n_panels', 1)),
            hinge_side=request.POST.get('hinge_side', ''),
            notes=request.POST.get('notes', ''),
            sort_order=existing,
        )
        messages.success(request, 'Measurement added.')
    return redirect('project_detail', pk=project_pk)


@login_required
def measurement_edit(request, pk):
    item = get_object_or_404(MeasurementItem, pk=pk)
    if not item.project.can_edit(request.user):
        messages.error(request, 'Project is locked.')
        return redirect('project_detail', pk=item.project.pk)
    if request.method == 'POST':
        item.reference = request.POST.get('reference', item.reference)
        item.location = request.POST.get('location', item.location)
        item.system_id = request.POST['system']
        item.glass_id = request.POST.get('glass') or None
        item.color_id = request.POST.get('color') or None
        item.width = int(request.POST['width'])
        item.height = int(request.POST['height'])
        item.qty = int(request.POST.get('qty', 1))
        item.description = request.POST.get('description', '')
        item.n_panels = int(request.POST.get('n_panels', 1))
        item.hinge_side = request.POST.get('hinge_side', '')
        item.notes = request.POST.get('notes', '')
        item.final_width = int(request.POST['final_width']) if request.POST.get('final_width') else None
        item.final_height = int(request.POST['final_height']) if request.POST.get('final_height') else None
        item.dimensions_confirmed = bool(request.POST.get('dimensions_confirmed'))
        item.save()
        messages.success(request, 'Measurement updated.')
    return redirect('project_detail', pk=item.project.pk)


@login_required
def project_lock(request, pk):
    if not request.user.profile.is_admin:
        messages.error(request, 'Only admin can lock projects.')
        return redirect('project_detail', pk=pk)
    project = get_object_or_404(Project, pk=pk)
    if request.method == 'POST':
        reason = request.POST.get('reason', 'Production approved')
        project.lock(request.user, reason)
        ProjectStatusHistory.objects.create(
            project=project, from_status=project.status,
            to_status=ProjectStatus.LOCKED, changed_by=request.user, notes=reason)
        messages.success(request, 'Project locked.')
    return redirect('project_detail', pk=pk)


@login_required
def project_unlock(request, pk):
    if not request.user.profile.is_admin:
        messages.error(request, 'Only admin can unlock projects.')
        return redirect('project_detail', pk=pk)
    project = get_object_or_404(Project, pk=pk)
    if request.method == 'POST':
        project.unlock(request.user)
        messages.success(request, 'Project unlocked.')
    return redirect('project_detail', pk=pk)
