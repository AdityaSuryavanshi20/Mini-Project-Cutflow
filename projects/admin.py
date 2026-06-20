from django.contrib import admin
from .models import Customer, Project, MeasurementItem, ProjectStatusHistory

class MeasurementInline(admin.TabularInline):
    model = MeasurementItem
    extra = 0
    fields = ['line_no', 'reference', 'location', 'system', 'width', 'height', 'qty']

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['name', 'company', 'phone', 'email', 'city']
    search_fields = ['name', 'phone', 'email']

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['reference', 'name', 'customer', 'status', 'salesman', 'is_locked']
    list_filter = ['status', 'is_locked']
    inlines = [MeasurementInline]

@admin.register(MeasurementItem)
class MeasurementItemAdmin(admin.ModelAdmin):
    list_display = ['project', 'line_no', 'reference', 'location', 'system', 'width', 'height', 'qty']
