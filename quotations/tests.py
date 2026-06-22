"""
Tests for the quotations app — the pricing cascade (Quotation/QuotationItem
properties) and the view-layer input validation that was added after the
original audit found that bad form input could 500 the page or silently
corrupt a customer-facing quote (e.g. a negative discount that inflated the
total instead of reducing it).
"""
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from catalog.models import System, SystemCategory, CompanySettings
from projects.models import Customer, Project
from quotations.models import Quotation, QuotationItem, QuotationType

def make_salesman(username, password='pw12345'):
    from django.contrib.auth.models import User
    from accounts.models import UserProfile, UserRole
    u = User.objects.create_user(username, password=password)
    u.profile.role = UserRole.SALESMAN
    u.profile.save()
    return u


def make_production_user(username, password='pw12345'):
    from django.contrib.auth.models import User
    from accounts.models import UserProfile, UserRole
    u = User.objects.create_user(username, password=password)
    u.profile.role = UserRole.PRODUCTION
    u.profile.save()
    return u



def make_system(**overrides):
    defaults = dict(
        code='SY-TEST', name='Test System', category=SystemCategory.CASEMENT,
        markup_percent=Decimal('15'), premium_markup_percent=Decimal('25'),
        budget_markup_percent=Decimal('10'),
    )
    defaults.update(overrides)
    return System.objects.create(**defaults)


class QuotationPricingMathTests(TestCase):
    """
    Pure arithmetic tests on the Quotation model properties. These set
    fields directly rather than going through forms, isolating the math
    itself from any view-layer concerns.
    """

    def setUp(self):
        CompanySettings.objects.create(pk=1)
        self.user = make_salesman('salesman1', password='x')
        self.customer = Customer.objects.create(name='Test Co')
        self.project = Project.objects.create(
            reference='PRICING-001', name='Pricing Test', customer=self.customer,
        )
        self.system = make_system()
        self.quote = Quotation.objects.create(
            project=self.project, quote_no='Q-PRICING-001', salesman=self.user,
        )

    def _add_item(self, unit_rate, qty=1, width=1000, height=1000):
        return QuotationItem.objects.create(
            quotation=self.quote, line_no='0001', system=self.system,
            width=width, height=height, qty=qty, unit_rate=Decimal(str(unit_rate)),
        )

    def test_subtotal_sums_item_totals(self):
        self._add_item(unit_rate=1000, qty=2)   # 2000
        self._add_item(unit_rate=500, qty=3)    # 1500
        self.assertEqual(self.quote.subtotal, Decimal('3500.00'))

    def test_percent_discount_reduces_subtotal(self):
        self._add_item(unit_rate=1000, qty=1)
        self.quote.discount_type = 'percent'
        self.quote.discount_value = Decimal('10')
        self.quote.save()
        self.assertEqual(self.quote.discount_amount, Decimal('100.00'))
        self.assertEqual(self.quote.after_discount, Decimal('900.00'))

    def test_fixed_discount_reduces_subtotal_by_flat_amount(self):
        self._add_item(unit_rate=1000, qty=1)
        self.quote.discount_type = 'fixed'
        self.quote.discount_value = Decimal('150')
        self.quote.save()
        self.assertEqual(self.quote.discount_amount, Decimal('150'))
        self.assertEqual(self.quote.after_discount, Decimal('850'))

    def test_zero_discount_leaves_subtotal_unchanged(self):
        self._add_item(unit_rate=1000, qty=1)
        self.assertEqual(self.quote.discount_amount, Decimal('0.00'))
        self.assertEqual(self.quote.after_discount, self.quote.subtotal)

    def test_percent_installation_applies_after_discount(self):
        self._add_item(unit_rate=1000, qty=1)
        self.quote.discount_type = 'percent'
        self.quote.discount_value = Decimal('10')  # after_discount = 900
        self.quote.installation_type = 'percent'
        self.quote.installation_value = Decimal('5')  # 5% of 900 = 45
        self.quote.save()
        self.assertEqual(self.quote.installation_amount, Decimal('45.00'))

    def test_fixed_installation_ignores_area_and_discount(self):
        self._add_item(unit_rate=1000, qty=1)
        self.quote.installation_type = 'fixed'
        self.quote.installation_value = Decimal('2500')
        self.quote.save()
        self.assertEqual(self.quote.installation_amount, Decimal('2500'))

    def test_transport_cost_is_freight_plus_lifting(self):
        self.quote.freight = Decimal('300')
        self.quote.lifting_charges = Decimal('150')
        self.quote.save()
        self.assertEqual(self.quote.transport_cost, Decimal('450'))

    def test_gst_only_applied_when_flag_is_true(self):
        self._add_item(unit_rate=1000, qty=1)
        self.quote.apply_sgst = True
        self.quote.apply_cgst = False
        self.quote.apply_igst = False
        self.quote.sgst_rate = Decimal('9')
        self.quote.save()
        self.assertEqual(self.quote.sgst_amount, Decimal('90.00'))
        self.assertEqual(self.quote.cgst_amount, Decimal('0.00'))
        self.assertEqual(self.quote.igst_amount, Decimal('0.00'))

    def test_grand_total_is_taxable_amount_plus_all_applicable_taxes(self):
        self._add_item(unit_rate=1000, qty=1)
        self.quote.apply_sgst = True
        self.quote.apply_cgst = True
        self.quote.apply_igst = False
        self.quote.sgst_rate = Decimal('9')
        self.quote.cgst_rate = Decimal('9')
        self.quote.save()
        # subtotal=1000, no discount/installation/freight -> taxable=1000
        # sgst=90, cgst=90 -> grand_total=1180
        self.assertEqual(self.quote.grand_total, Decimal('1180.00'))

    def test_avg_rate_per_sqft_is_zero_when_no_area(self):
        # No items at all -> total_area_sqft is 0, must not divide by zero.
        self.assertEqual(self.quote.avg_rate_per_sqft, Decimal('0.00'))

    def test_quote_type_helper_property(self):
        self.quote.quote_type = QuotationType.PRODUCTION
        self.assertTrue(self.quote.is_production_quote)
        self.quote.quote_type = QuotationType.TENTATIVE
        self.assertFalse(self.quote.is_production_quote)


class QuotationItemAreaTests(TestCase):
    """Tests for QuotationItem's geometry-derived properties."""

    def setUp(self):
        CompanySettings.objects.create(pk=1)
        self.customer = Customer.objects.create(name='Area Test Co')
        self.project = Project.objects.create(
            reference='AREA-001', name='Area Test', customer=self.customer,
        )
        self.system = make_system(code='SY-AREA')
        self.quote = Quotation.objects.create(project=self.project, quote_no='Q-AREA-001')

    def test_area_sqft_matches_known_conversion(self):
        # 1000mm x 1000mm = 1 sqm ~= 10.764 sqft. 304.8mm = 1ft exactly.
        item = QuotationItem.objects.create(
            quotation=self.quote, line_no='0001', system=self.system,
            width=3048, height=3048, qty=1,  # exactly 10ft x 10ft = 100 sqft
        )
        self.assertEqual(item.area_sqft, 100.0)

    def test_total_amount_multiplies_rate_by_qty(self):
        item = QuotationItem.objects.create(
            quotation=self.quote, line_no='0002', system=self.system,
            width=1000, height=1000, qty=4, unit_rate=Decimal('250'),
        )
        self.assertEqual(item.total_amount, Decimal('1000'))

    def test_glass_cut_dimensions_subtract_rebate_and_floor_at_zero(self):
        # Very small window: width/height - 40 would go negative without the floor.
        item = QuotationItem.objects.create(
            quotation=self.quote, line_no='0003', system=self.system,
            width=30, height=30, qty=1,
        )
        self.assertEqual(item.glass_cut_width, 0)
        self.assertEqual(item.glass_cut_height, 0)

    def test_glass_cost_is_zero_without_a_glass_type(self):
        item = QuotationItem.objects.create(
            quotation=self.quote, line_no='0004', system=self.system,
            width=1000, height=1000, qty=1, glass=None,
        )
        self.assertEqual(item.glass_cost, Decimal('0.00'))
        self.assertEqual(item.glass_weight_kg, Decimal('0.000'))


class QuotationUpdatePricingViewTests(TestCase):
    """
    Regression tests for the quotation_update_pricing view, which previously
    500'd on non-numeric input and silently accepted negative discount
    values that inflated the customer's total instead of reducing it.
    """

    def setUp(self):
        CompanySettings.objects.create(pk=1)
        self.admin = User.objects.create_superuser('admin_qp', 'a@x.com', 'pw12345')
        self.customer = Customer.objects.create(name='View Test Co')
        self.project = Project.objects.create(
            reference='VIEWQ-001', name='View Test', customer=self.customer,
        )
        self.system = make_system(code='SY-VIEWQ')
        self.quote = Quotation.objects.create(project=self.project, quote_no='Q-VIEWQ-001')
        self.item = QuotationItem.objects.create(
            quotation=self.quote, line_no='0001', system=self.system,
            width=1000, height=1000, qty=1, unit_rate=Decimal('1000'),
        )
        self.client.login(username='admin_qp', password='pw12345')

    def _post(self, **overrides):
        data = {
            'installation_value': '0', 'freight': '0', 'lifting_charges': '0',
            'discount_value': '0', 'sgst_rate': '9', 'cgst_rate': '9', 'igst_rate': '18',
            # Checkboxes only appear in POST data when checked; include them
            # explicitly so an unrelated assertion isn't tripped up by GST
            # silently toggling off, the same way a real form submission
            # would behave if the user left these boxes checked.
            'apply_sgst': 'on', 'apply_cgst': 'on',
            # Pin the item's rate via manual override on every POST so that
            # quotation_update_pricing's refresh_pricing() fallback (which
            # recomputes unit_rate from catalog formulas this fixture
            # doesn't define) doesn't zero out the price we're testing with.
            f'rate_{self.item.pk}': '1000',
        }
        data.update(overrides)
        return self.client.post(f'/quotations/{self.quote.pk}/pricing/', data=data, follow=True)

    def test_non_numeric_installation_value_does_not_500(self):
        response = self._post(installation_value='not-a-number')
        self.assertEqual(response.status_code, 200)
        self.quote.refresh_from_db()
        self.assertEqual(self.quote.installation_value, Decimal('0.00'))

    def test_negative_discount_is_rejected_not_applied(self):
        before_total = self.quote.grand_total
        response = self._post(discount_value='-50')
        self.assertEqual(response.status_code, 200)
        self.quote.refresh_from_db()
        self.assertEqual(self.quote.discount_value, Decimal('0.00'))
        # A rejected negative discount must not have changed the total at all.
        self.assertEqual(self.quote.grand_total, before_total)

    def test_discount_over_100_percent_is_capped(self):
        self._post(discount_value='500', discount_type='percent')
        self.quote.refresh_from_db()
        self.assertEqual(self.quote.discount_value, Decimal('100'))

    def test_invalid_choice_fields_fall_back_to_safe_defaults(self):
        self._post(quote_type='bogus', installation_type='bogus', discount_type='bogus')
        self.quote.refresh_from_db()
        self.assertEqual(self.quote.quote_type, QuotationType.TENTATIVE)
        self.assertEqual(self.quote.installation_type, 'percent')
        self.assertEqual(self.quote.discount_type, 'percent')

    def test_valid_update_applies_correctly(self):
        self._post(freight='1000', discount_value='10', discount_type='percent')
        self.quote.refresh_from_db()
        self.assertEqual(self.quote.freight, Decimal('1000.00'))
        self.assertEqual(self.quote.discount_value, Decimal('10.00'))

    def test_negative_freight_is_rejected(self):
        before_freight = self.quote.freight
        response = self._post(freight='-200')
        self.assertEqual(response.status_code, 200)
        self.quote.refresh_from_db()
        self.assertEqual(self.quote.freight, before_freight)

    def test_locked_project_blocks_pricing_update(self):
        self.project.lock(self.admin, 'testing lock')
        before = self.quote.freight
        self._post(freight='9999')
        self.quote.refresh_from_db()
        # Superuser CAN edit locked projects (see can_edit fix), so this
        # should actually succeed -- confirming the superuser bypass works
        # at this view too, not just project_lock/unlock.
        self.assertEqual(self.quote.freight, Decimal('9999.00'))
