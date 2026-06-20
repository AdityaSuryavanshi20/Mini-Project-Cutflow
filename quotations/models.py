from decimal import Decimal

from django.db import models
from django.contrib.auth.models import User
from projects.models import Project, MeasurementItem
from catalog.models import (
    System, Glass, Color, Hardware,
    ProfileFormula, SystemHardwareRule, CompanySettings,
)
from core.formula_engine import evaluate_formula, build_formula_context


class QuotationStatus(models.TextChoices):
    DRAFT = 'draft', 'Draft'
    SENT = 'sent', 'Sent to Customer'
    ACCEPTED = 'accepted', 'Accepted'
    REJECTED = 'rejected', 'Rejected'
    REVISED = 'revised', 'Revised'
    EXPIRED = 'expired', 'Expired'


class QuotationType(models.TextChoices):
    TENTATIVE = 'tentative', 'Tentative'
    PRODUCTION = 'production', 'Production'


class Quotation(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='quotations')
    quote_no = models.CharField(max_length=30, unique=True)
    revision = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(max_length=20, choices=QuotationStatus.choices,
                               default=QuotationStatus.DRAFT)
    quote_type = models.CharField(max_length=20, choices=QuotationType.choices,
                                  default=QuotationType.TENTATIVE,
                                  help_text='Quotation intent: tentative estimate or production-ready quote')
    pricing_variant = models.CharField(max_length=20, choices=[
        ('budget', 'Budget'), ('economy', 'Economy'), ('standard', 'Standard'), ('premium', 'Premium')],
        default='standard', help_text='Apply pricing variant to item markups')
    quote_date = models.DateField(auto_now_add=True)
    valid_until = models.DateField(null=True, blank=True)
    salesman = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                  related_name='quotations')

    # Pricing additions
    installation_type = models.CharField(max_length=10, default='percent',
                                          choices=[('percent', 'Percentage'), ('sqft', 'Per Sqft'), ('fixed', 'Fixed')])
    installation_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    freight = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    lifting_charges = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_type = models.CharField(max_length=10, default='percent',
                                      choices=[('percent', 'Percentage'), ('fixed', 'Fixed')])
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    apply_sgst = models.BooleanField(default=True)
    apply_cgst = models.BooleanField(default=True)
    apply_igst = models.BooleanField(default=False)
    sgst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=9)
    cgst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=9)
    igst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=18)

    payment_terms = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)

    sent_at = models.DateTimeField(null=True, blank=True)
    sent_to_email = models.EmailField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                    related_name='quotations_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.quote_no}/Rev{self.revision} – {self.project.reference}"

    @property
    def subtotal(self):
        return sum((item.total_amount for item in self.items.all()), Decimal('0.00'))

    @property
    def discount_amount(self):
        if self.discount_type == 'percent':
            return self.subtotal * self.discount_value / Decimal('100')
        return self.discount_value

    @property
    def after_discount(self):
        return self.subtotal - self.discount_amount

    @property
    def installation_amount(self):
        if self.installation_type == 'percent':
            return self.after_discount * self.installation_value / Decimal('100')
        elif self.installation_type == 'sqft':
            total_sqft = sum(
                float(item.measurement.area_sqft) for item in self.items.all()
                if item.measurement
            )
            return self.installation_value * Decimal(str(total_sqft))
        return self.installation_value

    @property
    def taxable_amount(self):
        return self.after_discount + self.installation_amount + self.transport_cost

    @property
    def transport_cost(self):
        return self.freight + self.lifting_charges

    @property
    def sgst_amount(self):
        return self.taxable_amount * self.sgst_rate / Decimal('100') if self.apply_sgst else Decimal('0.00')

    @property
    def cgst_amount(self):
        return self.taxable_amount * self.cgst_rate / Decimal('100') if self.apply_cgst else Decimal('0.00')

    @property
    def igst_amount(self):
        return self.taxable_amount * self.igst_rate / Decimal('100') if self.apply_igst else Decimal('0.00')

    @property
    def grand_total(self):
        return self.taxable_amount + self.sgst_amount + self.cgst_amount + self.igst_amount

    @property
    def total_area_sqft(self):
        return sum(float(item.measurement.area_sqft) for item in self.items.all() if item.measurement)

    @property
    def total_weight_kg(self):
        return sum(float(item.weight_kg) for item in self.items.all())

    @property
    def avg_rate_per_sqft(self):
        sqft = self.total_area_sqft
        return self.subtotal / Decimal(str(sqft)) if sqft else Decimal('0.00')

    @property
    def is_production_quote(self):
        return self.quote_type == QuotationType.PRODUCTION


class QuotationItem(models.Model):
    quotation = models.ForeignKey(Quotation, on_delete=models.CASCADE, related_name='items')
    measurement = models.ForeignKey(MeasurementItem, on_delete=models.SET_NULL,
                                     null=True, blank=True)
    line_no = models.CharField(max_length=10)
    reference = models.CharField(max_length=20, blank=True)
    location = models.CharField(max_length=100, blank=True)
    system = models.ForeignKey(System, on_delete=models.PROTECT)
    glass = models.ForeignKey(Glass, on_delete=models.SET_NULL, null=True, blank=True)
    color = models.ForeignKey(Color, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.CharField(max_length=255, blank=True)
    width = models.IntegerField()
    height = models.IntegerField()
    qty = models.PositiveIntegerField(default=1)
    n_panels = models.PositiveSmallIntegerField(default=1)
    unit_rate = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                     help_text='Price per unit (manually set or computed)')
    weight_kg = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    notes = models.TextField(blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'line_no']

    def __str__(self):
        return f"{self.quotation.quote_no}/{self.line_no} {self.reference}"

    @property
    def total_amount(self):
        return self.unit_rate * self.qty

    @property
    def area_sqft(self):
        return round((self.width * self.height) / (304.8 ** 2), 3)

    @property
    def area_sqm(self):
        return round((self.width * self.height) / 1_000_000, 4)

    def _pricing_context(self):
        return build_formula_context(
            width=self.width,
            height=self.height,
            n_panels=self.n_panels,
            qty=1,
            offset_l=0,
            offset_r=0,
            offset_t=0,
            offset_b=0,
        )

    @property
    def variant_markup_percent(self):
        variant = getattr(self.quotation, 'pricing_variant', 'standard')
        if variant == 'premium':
            return self.system.premium_markup_percent
        if variant in ['budget', 'economy']:
            return self.system.budget_markup_percent
        return self.system.markup_percent

    @property
    def glass_cut_width(self):
        return max(0, self.width - 40)

    @property
    def glass_cut_height(self):
        return max(0, self.height - 40)

    @property
    def glass_area_sqm(self):
        return round((self.glass_cut_width * self.glass_cut_height) / 1_000_000, 4)

    @property
    def glass_weight_kg(self):
        if not self.glass:
            return Decimal('0.000')
        return (Decimal(str(self.glass_area_sqm)) * self.glass.weight_per_sqm).quantize(Decimal('0.001'))

    @property
    def glass_cost(self):
        if not self.glass:
            return Decimal('0.00')
        return (Decimal(str(self.glass_area_sqm)) * self.glass.cost_per_sqm).quantize(Decimal('0.01'))

    def _profile_cut_costs(self):
        formulas = ProfileFormula.objects.filter(
            system=self.system,
            is_active=True,
            formula_type=ProfileFormula.FormulaType.CUT,
        ).select_related('profile')
        total_cost = Decimal('0.00')
        total_length_m = Decimal('0.00')
        total_weight_kg = Decimal('0.000')
        ctx = self._pricing_context()

        for formula in formulas:
            profile = formula.profile
            ctx['offset_l'] = profile.offset_left
            ctx['offset_r'] = profile.offset_right
            ctx['offset_t'] = profile.offset_top
            ctx['offset_b'] = profile.offset_bottom
            try:
                length_mm = float(evaluate_formula(formula.formula, ctx))
                quantity = float(evaluate_formula(formula.quantity_formula, ctx))
            except (ValueError, TypeError):
                continue
            if length_mm <= 0 or quantity <= 0:
                continue
            length_m = Decimal(str(length_mm / 1000.0)) * Decimal(str(quantity))
            total_length_m += length_m
            total_cost += length_m * profile.cost_per_meter
            total_weight_kg += length_m * profile.weight_per_meter

        return (
            total_cost.quantize(Decimal('0.01')),
            total_length_m.quantize(Decimal('0.001')),
            total_weight_kg.quantize(Decimal('0.001')),
        )

    @property
    def profile_material_cost(self):
        cost, _, _ = self._profile_cut_costs()
        return cost

    @property
    def profile_length_m(self):
        _, length_m, _ = self._profile_cut_costs()
        return length_m

    @property
    def profile_weight_kg(self):
        _, _, weight_kg = self._profile_cut_costs()
        return weight_kg

    @property
    def hardware_cost(self):
        rules = SystemHardwareRule.objects.filter(
            system=self.system,
            is_active=True,
        ).select_related('hardware')
        total = Decimal('0.00')
        ctx = self._pricing_context()
        for rule in rules:
            try:
                qty = evaluate_formula(rule.quantity_formula, ctx)
            except ValueError:
                qty = 0
            if qty <= 0:
                continue
            total += Decimal(str(round(qty, 2))) * rule.hardware.unit_cost
        return total.quantize(Decimal('0.01'))

    @property
    def fabrication_cost(self):
        settings = CompanySettings.get()
        return (self.profile_length_m * settings.fabrication_rate_per_meter).quantize(Decimal('0.01'))

    @property
    def material_cost(self):
        return (self.profile_material_cost + self.glass_cost + self.hardware_cost).quantize(Decimal('0.01'))

    @property
    def factory_cost(self):
        return (self.material_cost + self.fabrication_cost).quantize(Decimal('0.01'))

    @property
    def wastage_cost(self):
        settings = CompanySettings.get()
        return (self.factory_cost * settings.material_wastage_percent / Decimal('100')).quantize(Decimal('0.01'))

    @property
    def profit_amount(self):
        settings = CompanySettings.get()
        base = self.factory_cost + self.wastage_cost
        return (base * settings.profit_margin_percent / Decimal('100')).quantize(Decimal('0.01'))

    @property
    def total_cost_before_markup(self):
        return (self.factory_cost + self.wastage_cost + self.profit_amount).quantize(Decimal('0.01'))

    @property
    def variant_markup_amount(self):
        markup_pct = Decimal(str(self.variant_markup_percent)) / Decimal('100')
        return (self.total_cost_before_markup * markup_pct).quantize(Decimal('0.01'))

    @property
    def recommended_unit_rate(self):
        return (self.total_cost_before_markup + self.variant_markup_amount).quantize(Decimal('0.01'))

    def refresh_pricing(self):
        self.unit_rate = self.recommended_unit_rate
        self.weight_kg = (self.profile_weight_kg + self.glass_weight_kg).quantize(Decimal('0.001'))
        self.save(update_fields=['unit_rate', 'weight_kg'])
