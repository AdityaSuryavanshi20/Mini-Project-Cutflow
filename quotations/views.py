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
        quote.quote_type = request.POST.get('quote_type', quote.quote_type)
        quote.pricing_variant = request.POST.get('pricing_variant', quote.pricing_variant)
        quote.installation_type = request.POST.get('installation_type', 'percent')
        quote.installation_value = request.POST.get('installation_value', 0) or 0
        quote.freight = request.POST.get('freight', 0) or 0
        quote.lifting_charges = request.POST.get('lifting_charges', 0) or 0
        quote.discount_type = request.POST.get('discount_type', 'percent')
        quote.discount_value = request.POST.get('discount_value', 0) or 0
        quote.apply_sgst = bool(request.POST.get('apply_sgst'))
        quote.apply_cgst = bool(request.POST.get('apply_cgst'))
        quote.apply_igst = bool(request.POST.get('apply_igst'))
        quote.sgst_rate = request.POST.get('sgst_rate', 9) or 9
        quote.cgst_rate = request.POST.get('cgst_rate', 9) or 9
        quote.igst_rate = request.POST.get('igst_rate', 18) or 18
        quote.payment_terms = request.POST.get('payment_terms', '')
        quote.notes = request.POST.get('notes', '')
        quote.save()

        for item in quote.items.all():
            rate_key = f'rate_{item.pk}'
            manual_rate = request.POST.get(rate_key)
            if manual_rate:
                try:
                    item.unit_rate = Decimal(str(manual_rate))
                    item.save(update_fields=['unit_rate'])
                except (ValueError, TypeError, InvalidOperation):
                    pass
            else:
                item.refresh_pricing()

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
