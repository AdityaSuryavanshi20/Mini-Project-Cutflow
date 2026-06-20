from django.contrib import admin
from .models import (Brand, Color, System, SystemProfile, Profile, ProfileFormula,
                     ProfileStockLength, Glass, Hardware, SystemHardwareRule, CompanySettings)


class SystemProfileInline(admin.TabularInline):
    model = SystemProfile
    extra = 1
    fields = ['profile', 'role', 'formula_group', 'sort_order', 'is_required', 'is_active']

@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active']
    search_fields = ['name']

@admin.register(Color)
class ColorAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'is_active']

@admin.register(System)
class SystemAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'category', 'brand', 'is_active']
    list_filter = ['category', 'is_active', 'brand']
    search_fields = ['code', 'name']
    inlines = [SystemProfileInline]

class ProfileFormulaInline(admin.TabularInline):
    model = ProfileFormula
    extra = 1

class ProfileStockLengthInline(admin.TabularInline):
    model = ProfileStockLength
    extra = 1
    fields = ['length_mm', 'cost_per_meter_override', 'is_active']

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['stock_no', 'name', 'category', 'weight_per_meter', 'cost_per_meter',
                    'standard_bar_length', 'is_active']
    list_filter = ['category', 'is_active']
    search_fields = ['stock_no', 'name']
    inlines = [ProfileFormulaInline, ProfileStockLengthInline]

@admin.register(ProfileFormula)
class ProfileFormulaAdmin(admin.ModelAdmin):
    list_display = ['system', 'profile', 'position', 'formula', 'quantity_formula', 'is_active']
    list_filter = ['system', 'is_active']

@admin.register(Glass)
class GlassAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'specification', 'thickness', 'cost_per_sqft', 'is_active']
    list_filter = ['specification', 'is_active']
    search_fields = ['code', 'name']

class SystemHardwareRuleInline(admin.TabularInline):
    model = SystemHardwareRule
    extra = 1

@admin.register(Hardware)
class HardwareAdmin(admin.ModelAdmin):
    list_display = ['stock_no', 'name', 'category', 'unit', 'unit_cost', 'is_active']
    list_filter = ['category', 'is_active']
    search_fields = ['stock_no', 'name']

@admin.register(SystemHardwareRule)
class SystemHardwareRuleAdmin(admin.ModelAdmin):
    list_display = ['system', 'hardware', 'quantity_formula', 'is_active']

@admin.register(CompanySettings)
class CompanySettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not CompanySettings.objects.exists()
    def has_delete_permission(self, request, obj=None):
        return False
