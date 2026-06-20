from django.contrib import admin
from .models import (ProductionJob, ProductionItem, ProductionCutItem,
                     HardwareRequirement, OptimizationRun, OptimizationSegment,
                     OptimizedCut, ReusableOffcut)

class ProductionItemInline(admin.TabularInline):
    model = ProductionItem
    extra = 0
    fields = ['line_no', 'reference', 'location', 'system', 'width', 'height', 'qty', 'is_complete']

@admin.register(ProductionJob)
class ProductionJobAdmin(admin.ModelAdmin):
    list_display = ['job_no', 'project', 'status', 'assigned_to', 'scheduled_date']
    list_filter = ['status']
    inlines = [ProductionItemInline]

@admin.register(OptimizationRun)
class OptimizationRunAdmin(admin.ModelAdmin):
    list_display = ['pk', 'production_job', 'total_bars_used', 'utilisation_pct', 'is_active', 'created_at']
    list_filter = ['is_active']

@admin.register(ReusableOffcut)
class ReusableOffcutAdmin(admin.ModelAdmin):
    list_display = ['profile', 'length_mm', 'source_job', 'is_available', 'created_at']
    list_filter = ['is_available', 'profile']
