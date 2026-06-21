from decimal import Decimal, InvalidOperation

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.utils import timezone
from django.db import transaction
import datetime

from .models import Quotation, QuotationItem, QuotationStatus, QuotationType
from projects.models import Project, MeasurementItem
from catalog.models import System, Glass, Color, CompanySettings
from .pdf_generator import generate_quotation_pdf


def _next_quote_no():
    last = Quotation.objects.order_by('-id').first()
    if not last:
        return 'Q00001'
    try:
        num = int(last.quote_no.replace('Q', '')) + 1
    except Exception:
        num = 1
    return f'Q{num:05d}'


def _parse_nonneg_decimal(raw, default, field_label, errors):
    """
    Parse a POSTed value into a non-negative Decimal, falling back to
    `default` and recording a message in `errors` if the value is missing,
    not a valid number, or negative. Never raises.
    """
    if raw is None or str(raw).strip() == '':
        return Decimal(str(default))
    try:
        value = Decimal(str(raw).strip())
    except (InvalidOperation, ValueError, TypeError):
        errors.append(f'{field_label} must be a number; kept previous value.')
        return Decimal(str(default))
    if value < 0:
        errors.append(f'{field_label} cannot be negative; kept previous value.')
        return Decimal(str(default))
    return value


@login_required
def quotation_list(request):
    qs = Quotation.objects.select_related('project__customer', 'salesman').all()
    return render(request, 'quotations/quotation_list.html', {'quotations': qs})


@login_required
def quotation_create(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    if not project.can_edit(request.user):
        messages.error(request, 'Project is locked.')
        return redirect('project_detail', pk=project_pk)

    settings = CompanySettings.get()
    valid_until = datetime.date.today() + datetime.timedelta(days=settings.quotation_validity_days)

    quote_type = request.GET.get('quote_type', QuotationType.TENTATIVE)
    if quote_type not in QuotationType.values:
        quote_type = QuotationType.TENTATIVE

    with transaction.atomic():
        quote = Quotation.objects.create(
            project=project,
            quote_no=_next_quote_no(),
            quote_type=quote_type,
            salesman=request.user,
            pricing_variant='standard',
            valid_until=valid_until,
            sgst_rate=settings.sgst_rate,
            cgst_rate=settings.cgst_rate,
            igst_rate=settings.igst_rate,
            payment_terms=settings.default_payment_terms,
            created_by=request.user,
        )
        # Auto-populate from measurements and compute rates
        for i, m in enumerate(project.measurements.all()):
            item = QuotationItem.objects.create(
                quotation=quote,
                measurement=m,
                line_no=m.line_no,
                reference=m.reference,
                location=m.location,
                system=m.system,
                glass=m.glass,
                color=m.color,
                description=m.description,
                width=m.effective_width,
                height=m.effective_height,
                qty=m.qty,
                n_panels=m.n_panels,
                sort_order=i,
            )
            item.refresh_pricing()
    messages.success(request, f'Quotation {quote.quote_no} created.')
    return redirect('quotation_detail', pk=quote.pk)


@login_required
def quotation_detail(request, pk):
    quote = get_object_or_404(Quotation, pk=pk)
    items = quote.items.select_related('system', 'glass', 'color').all()
    return render(request, 'quotations/quotation_detail.html', {
        'quote': quote,
        'items': items,
        'systems': System.objects.filter(is_active=True),
        'glasses': Glass.objects.filter(is_active=True),
        'colors': Color.objects.filter(is_active=True),
        'statuses': QuotationStatus.choices,
        'quote_types': QuotationType.choices,
    })


@login_required
def quotation_update_pricing(request, pk):
    quote = get_object_or_404(Quotation, pk=pk)
    if not quote.project.can_edit(request.user):
        messages.error(request, 'Project is locked.')
        return redirect('quotation_detail', pk=pk)

    if request.method == 'POST':
        errors = []

        quote.quote_type = request.POST.get('quote_type', quote.quote_type)
        if quote.quote_type not in QuotationType.values:
            quote.quote_type = QuotationType.TENTATIVE
            errors.append('Invalid quote type; defaulted to Tentative.')

        pricing_variant = request.POST.get('pricing_variant', quote.pricing_variant)
        valid_variants = {choice[0] for choice in Quotation._meta.get_field('pricing_variant').choices}
        quote.pricing_variant = pricing_variant if pricing_variant in valid_variants else quote.pricing_variant

        installation_type = request.POST.get('installation_type', quote.installation_type)
        valid_installation_types = {choice[0] for choice in Quotation._meta.get_field('installation_type').choices}
        quote.installation_type = (
            installation_type if installation_type in valid_installation_types else 'percent'
        )

        discount_type = request.POST.get('discount_type', quote.discount_type)
        valid_discount_types = {choice[0] for choice in Quotation._meta.get_field('discount_type').choices}
        quote.discount_type = discount_type if discount_type in valid_discount_types else 'percent'

        quote.installation_value = _parse_nonneg_decimal(
            request.POST.get('installation_value'), quote.installation_value, 'Installation value', errors)
        quote.freight = _parse_nonneg_decimal(
            request.POST.get('freight'), quote.freight, 'Freight', errors)
        quote.lifting_charges = _parse_nonneg_decimal(
            request.POST.get('lifting_charges'), quote.lifting_charges, 'Lifting charges', errors)
        quote.discount_value = _parse_nonneg_decimal(
            request.POST.get('discount_value'), quote.discount_value, 'Discount value', errors)
        if quote.discount_type == 'percent' and quote.discount_value > 100:
            errors.append('Discount percentage cannot exceed 100%; capped at 100%.')
            quote.discount_value = Decimal('100')

        quote.apply_sgst = bool(request.POST.get('apply_sgst'))
        quote.apply_cgst = bool(request.POST.get('apply_cgst'))
        quote.apply_igst = bool(request.POST.get('apply_igst'))
        quote.sgst_rate = _parse_nonneg_decimal(
            request.POST.get('sgst_rate'), quote.sgst_rate, 'SGST rate', errors)
        quote.cgst_rate = _parse_nonneg_decimal(
            request.POST.get('cgst_rate'), quote.cgst_rate, 'CGST rate', errors)
        quote.igst_rate = _parse_nonneg_decimal(
            request.POST.get('igst_rate'), quote.igst_rate, 'IGST rate', errors)

        quote.payment_terms = request.POST.get('payment_terms', '')
        quote.notes = request.POST.get('notes', '')
        quote.save()

        for item in quote.items.all():
            rate_key = f'rate_{item.pk}'
            manual_rate = request.POST.get(rate_key)
            if manual_rate:
                try:
                    rate = Decimal(str(manual_rate))
                    if rate < 0:
                        errors.append(f'Rate for item {item.reference or item.line_no} cannot be negative; ignored.')
                    else:
                        item.unit_rate = rate
                        item.save(update_fields=['unit_rate'])
                except (ValueError, TypeError, InvalidOperation):
                    errors.append(f'Rate for item {item.reference or item.line_no} was not a valid number; ignored.')
            else:
                item.refresh_pricing()

        if errors:
            for err in errors:
                messages.warning(request, err)
        messages.success(request, 'Quotation pricing updated.')
    return redirect('quotation_detail', pk=pk)


@login_required
def quotation_pdf(request, pk):
    quote = get_object_or_404(Quotation, pk=pk)
    pdf_bytes = generate_quotation_pdf(quote)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{quote.quote_no}.pdf"'
    return response


from django.core.mail import EmailMessage
from django.conf import settings

@login_required
def quotation_send(request, pk):
    quote = get_object_or_404(Quotation, pk=pk)
    if request.method == 'POST':
        email = request.POST.get('email', quote.project.customer.email)
        
        try:
            # Generate PDF
            pdf_bytes = generate_quotation_pdf(quote)
            
            company_settings = CompanySettings.get()
            company_name = company_settings.company_name
            
            # Create EmailMessage
            subject = f"Quotation {quote.quote_no} from {company_name}"
            body = f"Dear {quote.project.customer.name},\n\nPlease find attached the quotation {quote.quote_no} for project {quote.project.name}.\n\nThank you,\n{company_name}"
            
            email_msg = EmailMessage(
                subject,
                body,
                settings.DEFAULT_FROM_EMAIL,
                [email],
            )
            email_msg.attach(f'{quote.quote_no}.pdf', pdf_bytes, 'application/pdf')
            email_msg.send()
            
            quote.status = QuotationStatus.SENT
            quote.sent_at = timezone.now()
            quote.sent_to_email = email
            quote.save()
            messages.success(request, f'Quotation sent successfully to {email}.')
        except Exception as e:
            messages.error(request, f'Failed to send email: {str(e)}')
            
    return redirect('quotation_detail', pk=pk)
