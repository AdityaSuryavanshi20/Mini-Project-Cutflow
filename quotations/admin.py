from django.contrib import admin
from .models import Quotation, QuotationItem

class QuotationItemInline(admin.TabularInline):
    model = QuotationItem
    extra = 0
    fields = ['line_no', 'reference', 'location', 'system', 'width', 'height', 'qty', 'unit_rate']

@admin.register(Quotation)
class QuotationAdmin(admin.ModelAdmin):
    list_display = ['quote_no', 'revision', 'project', 'status', 'quote_date', 'salesman']
    list_filter = ['status']
    inlines = [QuotationItemInline]
