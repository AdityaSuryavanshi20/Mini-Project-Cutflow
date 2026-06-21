from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db import transaction
from .models import Customer, Project, MeasurementItem, ProjectStatus, ProjectStatusHistory
from catalog.models import System, Color, Glass
import json


def _is_admin(user):
    """True for Django superusers or users whose profile role is admin."""
    if user.is_superuser:
        return True
    return hasattr(user, 'profile') and user.profile.is_admin


def _parse_fk_id(raw):
    """
    Return raw as a clean digit-string PK, or None if it's missing/blank/
    non-numeric. Use before any `<field>_id=` assignment or `pk=` lookup
    on a foreign key, since Django only validates FK values at save/query
    time and raises a raw ValueError on garbage input.
    """
    if raw is None or str(raw).strip() == '':
        return None
    raw = str(raw).strip()
    return raw if raw.isdigit() else None


def _parse_positive_int(raw, default, field_label, errors, allow_none=False):
    """
    Parse a POSTed value into a positive int, falling back to `default`
    (which may be None when allow_none=True) and recording a message in
    `errors` on missing/invalid/non-positive input. Never raises.
    """
    if raw is None or str(raw).strip() == '':
        if allow_none:
            return None
        errors.append(f'{field_label} is required; kept previous value.')
        return default
    try:
        value = int(str(raw).strip())
    except (ValueError, TypeError):
        errors.append(f'{field_label} must be a whole number; kept previous value.')
        return default
    if value <= 0:
        errors.append(f'{field_label} must be greater than zero; kept previous value.')
        return default
    return value


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
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, 'Customer name is required.')
            return render(request, 'projects/customer_form.html', {'action': 'Create', 'post': request.POST})
        c = Customer.objects.create(
            name=name,
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
        name = request.POST.get('name', '').strip()
        customer_id = _parse_fk_id(request.POST.get('customer'))

        if not ref:
            messages.error(request, 'Project reference is required.')
            return render(request, 'projects/project_form.html', {
                'action': 'Create', 'customers': Customer.objects.all(), 'post': request.POST})
        if Project.objects.filter(reference=ref).exists():
            messages.error(request, 'Reference already exists.')
            return render(request, 'projects/project_form.html', {
                'action': 'Create', 'customers': Customer.objects.all(), 'post': request.POST})
        if not name:
            messages.error(request, 'Project name is required.')
            return render(request, 'projects/project_form.html', {
                'action': 'Create', 'customers': Customer.objects.all(), 'post': request.POST})
        if not customer_id or not Customer.objects.filter(pk=customer_id).exists():
            messages.error(request, 'Please select a valid customer.')
            return render(request, 'projects/project_form.html', {
                'action': 'Create', 'customers': Customer.objects.all(), 'post': request.POST})

        with transaction.atomic():
            p = Project.objects.create(
                reference=ref,
                name=name,
                customer_id=customer_id,
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
        system_id = request.POST.get('system')
        if not system_id or not str(system_id).isdigit() or not System.objects.filter(pk=system_id, is_active=True).exists():
            messages.error(request, 'Please select a valid system.')
            return redirect('project_detail', pk=project_pk)

        errors = []
        width = _parse_positive_int(request.POST.get('width'), None, 'Width', errors)
        height = _parse_positive_int(request.POST.get('height'), None, 'Height', errors)
        qty = _parse_positive_int(request.POST.get('qty', 1), 1, 'Quantity', errors)
        n_panels = _parse_positive_int(request.POST.get('n_panels', 1), 1, 'Number of panels', errors)

        if width is None or height is None:
            for err in errors:
                messages.error(request, err)
            return redirect('project_detail', pk=project_pk)

        # Auto line_no
        existing = project.measurements.count()
        line_no = f"{existing + 1:04d}"
        MeasurementItem.objects.create(
            project=project,
            line_no=line_no,
            reference=request.POST.get('reference', f'W{existing+1}'),
            location=request.POST.get('location', ''),
            system_id=system_id,
            glass_id=_parse_fk_id(request.POST.get('glass')),
            color_id=_parse_fk_id(request.POST.get('color')),
            width=width,
            height=height,
            qty=qty,
            description=request.POST.get('description', ''),
            n_panels=n_panels,
            hinge_side=request.POST.get('hinge_side', ''),
            notes=request.POST.get('notes', ''),
            sort_order=existing,
        )
        for err in errors:
            messages.warning(request, err)
        messages.success(request, 'Measurement added.')
    return redirect('project_detail', pk=project_pk)


@login_required
def measurement_edit(request, pk):
    item = get_object_or_404(MeasurementItem, pk=pk)
    if not item.project.can_edit(request.user):
        messages.error(request, 'Project is locked.')
        return redirect('project_detail', pk=item.project.pk)
    if request.method == 'POST':
        system_id = request.POST.get('system')
        if not system_id or not str(system_id).isdigit() or not System.objects.filter(pk=system_id, is_active=True).exists():
            messages.error(request, 'Please select a valid system.')
            return redirect('project_detail', pk=item.project.pk)

        errors = []
        width = _parse_positive_int(request.POST.get('width'), item.width, 'Width', errors)
        height = _parse_positive_int(request.POST.get('height'), item.height, 'Height', errors)
        qty = _parse_positive_int(request.POST.get('qty', 1), item.qty, 'Quantity', errors)
        n_panels = _parse_positive_int(request.POST.get('n_panels', 1), item.n_panels, 'Number of panels', errors)
        final_width = _parse_positive_int(
            request.POST.get('final_width'), item.final_width, 'Final width', errors, allow_none=True)
        final_height = _parse_positive_int(
            request.POST.get('final_height'), item.final_height, 'Final height', errors, allow_none=True)

        item.reference = request.POST.get('reference', item.reference)
        item.location = request.POST.get('location', item.location)
        item.system_id = system_id
        item.glass_id = _parse_fk_id(request.POST.get('glass'))
        item.color_id = _parse_fk_id(request.POST.get('color'))
        item.width = width
        item.height = height
        item.qty = qty
        item.description = request.POST.get('description', '')
        item.n_panels = n_panels
        item.hinge_side = request.POST.get('hinge_side', '')
        item.notes = request.POST.get('notes', '')
        item.final_width = final_width
        item.final_height = final_height
        item.dimensions_confirmed = bool(request.POST.get('dimensions_confirmed'))
        item.save()
        for err in errors:
            messages.warning(request, err)
        messages.success(request, 'Measurement updated.')
    return redirect('project_detail', pk=item.project.pk)


@login_required
def project_lock(request, pk):
    if not _is_admin(request.user):
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
    if not _is_admin(request.user):
        messages.error(request, 'Only admin can unlock projects.')
        return redirect('project_detail', pk=pk)
    project = get_object_or_404(Project, pk=pk)
    if request.method == 'POST':
        project.unlock(request.user)
        messages.success(request, 'Project unlocked.')
    return redirect('project_detail', pk=pk)
