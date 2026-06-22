"""
Tests for the projects app — customer/project creation validation,
measurement add/edit input handling, and the lock/unlock permission logic.

These pin down the fixes made after the original audit found that:
  - measurement_add crashed (500) on non-numeric width/height, and silently
    accepted negative dimensions that corrupted downstream pricing.
  - A freshly created Django superuser couldn't lock/unlock projects because
    permission checks only looked at profile.is_admin, not is_superuser.
  - Garbage (non-numeric) foreign key ids crashed views with a raw
    ValueError instead of a friendly validation message.
"""
from django.contrib.auth.models import User
from django.test import TestCase

from accounts.models import UserProfile, UserRole
from catalog.models import System, SystemCategory
from .models import Customer, MeasurementItem, Project


def make_system(code='SY-PROJTEST'):
    return System.objects.create(code=code, name='Test System', category=SystemCategory.CASEMENT)


def make_salesman(username, password='pw12345'):
    u = User.objects.create_user(username, password=password)
    u.profile.role = UserRole.SALESMAN
    u.profile.save()
    return u


class CustomerCreateViewTests(TestCase):
    def setUp(self):
        self.user = make_salesman('salesman_pc')
        self.client.login(username='salesman_pc', password='pw12345')

    def test_missing_name_does_not_crash_and_is_rejected(self):
        response = self.client.post('/projects/customers/new/', data={'phone': '123'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Customer.objects.filter(phone='123').exists())

    def test_blank_name_is_rejected(self):
        response = self.client.post(
            '/projects/customers/new/', data={'name': '   ', 'phone': '123'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Customer.objects.filter(phone='123').exists())

    def test_valid_name_creates_customer(self):
        response = self.client.post(
            '/projects/customers/new/', data={'name': 'Acme Fabrication', 'phone': '999'},
            follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Customer.objects.filter(name='Acme Fabrication').exists())


class ProjectCreateViewTests(TestCase):
    def setUp(self):
        self.user = make_salesman('salesman_pp')
        self.client.login(username='salesman_pp', password='pw12345')
        self.customer = Customer.objects.create(name='Project Test Customer')

    def test_missing_customer_does_not_crash(self):
        response = self.client.post(
            '/projects/new/', data={'reference': 'PCNOCUST', 'name': 'No customer'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Project.objects.filter(reference='PCNOCUST').exists())

    def test_non_numeric_customer_id_does_not_crash(self):
        response = self.client.post(
            '/projects/new/',
            data={'reference': 'PCBADCUST', 'name': 'Bad customer', 'customer': 'not-an-id'},
            follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Project.objects.filter(reference='PCBADCUST').exists())

    def test_nonexistent_customer_id_is_rejected(self):
        response = self.client.post(
            '/projects/new/',
            data={'reference': 'PCGHOST', 'name': 'Ghost customer', 'customer': '999999'},
            follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Project.objects.filter(reference='PCGHOST').exists())

    def test_duplicate_reference_is_rejected(self):
        Project.objects.create(reference='DUPREF', name='First', customer=self.customer)
        response = self.client.post(
            '/projects/new/',
            data={'reference': 'DUPREF', 'name': 'Second', 'customer': self.customer.pk},
            follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Project.objects.filter(reference='DUPREF').count(), 1)

    def test_valid_submission_creates_project(self):
        response = self.client.post(
            '/projects/new/',
            data={'reference': 'GOODPROJ', 'name': 'Good project', 'customer': self.customer.pk},
            follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Project.objects.filter(reference='GOODPROJ').exists())


class MeasurementAddViewTests(TestCase):
    def setUp(self):
        self.user = make_salesman('salesman_ma')
        self.client.login(username='salesman_ma', password='pw12345')
        self.customer = Customer.objects.create(name='Measurement Test Customer')
        self.project = Project.objects.create(
            reference='MEAS-001', name='Measurement Test', customer=self.customer)
        self.system = make_system()

    def _post(self, **overrides):
        data = {'reference': 'W1', 'location': 'Test', 'system': self.system.pk,
                'width': '1200', 'height': '1500', 'qty': '1'}
        data.update(overrides)
        return self.client.post(
            f'/projects/{self.project.pk}/measurements/add/', data=data, follow=True)

    def test_non_numeric_width_does_not_crash(self):
        response = self._post(width='abc', reference='BADWIDTH')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(MeasurementItem.objects.filter(reference='BADWIDTH').exists())

    def test_missing_width_does_not_crash(self):
        data = {'reference': 'NOWIDTH', 'location': 'Test', 'system': self.system.pk,
                'height': '1500', 'qty': '1'}
        response = self.client.post(
            f'/projects/{self.project.pk}/measurements/add/', data=data, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(MeasurementItem.objects.filter(reference='NOWIDTH').exists())

    def test_negative_width_is_rejected_not_saved(self):
        response = self._post(width='-500', reference='NEGWIDTH')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(MeasurementItem.objects.filter(reference='NEGWIDTH').exists())

    def test_zero_width_is_rejected(self):
        response = self._post(width='0', reference='ZEROWIDTH')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(MeasurementItem.objects.filter(reference='ZEROWIDTH').exists())

    def test_garbage_qty_falls_back_to_default_of_one(self):
        response = self._post(qty='abc', reference='BADQTY')
        self.assertEqual(response.status_code, 200)
        item = MeasurementItem.objects.get(reference='BADQTY')
        self.assertEqual(item.qty, 1)

    def test_invalid_system_id_is_rejected(self):
        response = self._post(system='not-a-real-id', reference='BADSYS')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(MeasurementItem.objects.filter(reference='BADSYS').exists())

    def test_nonexistent_system_id_is_rejected(self):
        response = self._post(system='999999', reference='GHOSTSYS')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(MeasurementItem.objects.filter(reference='GHOSTSYS').exists())

    def test_garbage_glass_id_does_not_crash(self):
        response = self._post(glass='abc', reference='BADGLASS')
        self.assertEqual(response.status_code, 200)
        item = MeasurementItem.objects.get(reference='BADGLASS')
        self.assertIsNone(item.glass_id)

    def test_valid_submission_creates_measurement(self):
        response = self._post(reference='GOODMEAS')
        self.assertEqual(response.status_code, 200)
        item = MeasurementItem.objects.get(reference='GOODMEAS')
        self.assertEqual(item.width, 1200)
        self.assertEqual(item.height, 1500)
        self.assertEqual(item.qty, 1)

    def test_locked_project_blocks_measurement_add(self):
        admin = User.objects.create_superuser('admin_ma', 'a@x.com', 'pw12345')
        self.project.lock(admin, 'testing')
        self.client.logout()
        self.client.login(username='salesman_ma', password='pw12345')
        response = self._post(reference='LOCKEDBLOCK')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(MeasurementItem.objects.filter(reference='LOCKEDBLOCK').exists())


class MeasurementEditViewTests(TestCase):
    def setUp(self):
        self.user = make_salesman('salesman_me')
        self.client.login(username='salesman_me', password='pw12345')
        self.customer = Customer.objects.create(name='Edit Test Customer')
        self.project = Project.objects.create(
            reference='EDIT-001', name='Edit Test', customer=self.customer)
        self.system = make_system(code='SY-EDITTEST')
        self.item = MeasurementItem.objects.create(
            project=self.project, line_no='0001', reference='E1', system=self.system,
            width=1000, height=1000, qty=1,
        )

    def _post(self, **overrides):
        data = {'reference': 'E1', 'location': 'Test', 'system': self.system.pk,
                'width': '1000', 'height': '1000', 'qty': '1'}
        data.update(overrides)
        return self.client.post(f'/projects/measurements/{self.item.pk}/edit/', data=data, follow=True)

    def test_non_numeric_width_keeps_previous_value(self):
        response = self._post(width='abc')
        self.assertEqual(response.status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(self.item.width, 1000)  # unchanged, not crashed

    def test_negative_height_keeps_previous_value(self):
        response = self._post(height='-200')
        self.assertEqual(response.status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(self.item.height, 1000)  # unchanged

    def test_valid_edit_updates_dimensions(self):
        response = self._post(width='1500', height='2000')
        self.assertEqual(response.status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(self.item.width, 1500)
        self.assertEqual(self.item.height, 2000)

    def test_final_width_can_be_cleared_to_none(self):
        self.item.final_width = 1490
        self.item.save()
        response = self._post(final_width='')
        self.assertEqual(response.status_code, 200)
        self.item.refresh_from_db()
        self.assertIsNone(self.item.final_width)


class ProjectLockUnlockViewTests(TestCase):
    """
    Regression tests for the headline bug: a freshly created superuser
    couldn't lock/unlock a project because the view only checked
    profile.is_admin, which defaults to a non-admin role for new users.
    """

    def setUp(self):
        self.customer = Customer.objects.create(name='Lock Test Customer')
        self.project = Project.objects.create(
            reference='LOCK-001', name='Lock Test', customer=self.customer)

    def test_superuser_can_lock_project(self):
        admin = User.objects.create_superuser('admin_lock', 'a@x.com', 'pw12345')
        self.client.login(username='admin_lock', password='pw12345')
        response = self.client.post(
            f'/projects/{self.project.pk}/lock/', data={'reason': 'test'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.project.refresh_from_db()
        self.assertTrue(self.project.is_locked)

    def test_superuser_can_unlock_project(self):
        admin = User.objects.create_superuser('admin_unlock', 'a@x.com', 'pw12345')
        self.project.lock(admin, 'setup')
        self.client.login(username='admin_unlock', password='pw12345')
        response = self.client.post(f'/projects/{self.project.pk}/unlock/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.project.refresh_from_db()
        self.assertFalse(self.project.is_locked)

    def test_newly_created_superuser_profile_defaults_to_admin_role(self):
        # Regression test for the accounts/signals.py fix: previously every
        # new user (including superusers) defaulted to the 'viewer' role.
        admin = User.objects.create_superuser('admin_role', 'a@x.com', 'pw12345')
        self.assertEqual(admin.profile.role, UserRole.ADMIN)
        self.assertTrue(admin.profile.is_admin)

    def test_regular_viewer_cannot_lock_project(self):
        viewer = User.objects.create_user('viewer_lock', password='pw12345')
        self.client.login(username='viewer_lock', password='pw12345')
        response = self.client.post(
            f'/projects/{self.project.pk}/lock/', data={'reason': 'test'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.project.refresh_from_db()
        self.assertFalse(self.project.is_locked)

    def test_profile_admin_role_can_also_lock_project(self):
        # Non-superuser admins (role='admin' on their profile) should also
        # be able to lock, since _is_admin() checks both paths.
        user = User.objects.create_user('roleadmin_lock', password='pw12345')
        user.profile.role = UserRole.ADMIN
        user.profile.save()
        self.client.login(username='roleadmin_lock', password='pw12345')
        response = self.client.post(
            f'/projects/{self.project.pk}/lock/', data={'reason': 'test'}, follow=True)
        self.project.refresh_from_db()
        self.assertTrue(self.project.is_locked)

    def test_superuser_can_edit_locked_project(self):
        # can_edit() must also recognize superusers, not just profile.is_admin.
        admin = User.objects.create_superuser('admin_edit_locked', 'a@x.com', 'pw12345')
        self.project.lock(admin, 'setup')
        self.assertTrue(self.project.can_edit(admin))

    def test_regular_user_cannot_edit_locked_project(self):
        admin = User.objects.create_superuser('admin_lockedcheck', 'a@x.com', 'pw12345')
        self.project.lock(admin, 'setup')
        viewer = User.objects.create_user('viewer_lockedcheck', password='pw12345')
        self.assertFalse(self.project.can_edit(viewer))


class UserWithoutProfileTests(TestCase):
    """
    Regression test: a user lacking a UserProfile (e.g. profile deleted, or
    a future creation path that bypasses the signal) must not crash views
    that check admin status -- it should be treated as non-admin, not 500.
    """

    def setUp(self):
        self.customer = Customer.objects.create(name='No Profile Customer')
        self.project = Project.objects.create(
            reference='NOPROFILE-001', name='No Profile Test', customer=self.customer)

    def test_user_without_profile_is_denied_not_crashed(self):
        user = User.objects.create_user('noprofile_test', password='pw12345')
        UserProfile.objects.filter(user=user).delete()
        user.refresh_from_db()
        self.assertFalse(hasattr(user, 'profile'))

        self.client.login(username='noprofile_test', password='pw12345')
        response = self.client.post(
            f'/projects/{self.project.pk}/lock/', data={'reason': 'test'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.project.refresh_from_db()
        self.assertFalse(self.project.is_locked)


class RoleEnforcementTests(TestCase):
    """
    Verify that the role_required decorator correctly prevents viewers from
    performing write operations that are restricted to salesman+ roles.
    These pin down the role enforcement added after the audit found that
    the role system existed (UserRole choices, is_admin checks) but was
    never actually wired up to the main write endpoints.
    """

    def setUp(self):
        self.customer = Customer.objects.create(name='Role Test Customer')
        self.project = Project.objects.create(
            reference='ROLE-001', name='Role Test', customer=self.customer)
        self.system = make_system(code='SY-ROLE')

    def test_viewer_cannot_create_customer(self):
        viewer = User.objects.create_user('viewer_cc', password='pw12345')
        self.assertEqual(viewer.profile.role, UserRole.VIEWER)
        self.client.login(username='viewer_cc', password='pw12345')
        response = self.client.post(
            '/projects/customers/new/', data={'name': 'New Co'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Customer.objects.filter(name='New Co').exists())

    def test_viewer_cannot_create_project(self):
        viewer = User.objects.create_user('viewer_cp', password='pw12345')
        self.client.login(username='viewer_cp', password='pw12345')
        response = self.client.post(
            '/projects/new/',
            data={'reference': 'VIEWER-PROJ', 'name': 'Viewer Project',
                  'customer': self.customer.pk},
            follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Project.objects.filter(reference='VIEWER-PROJ').exists())

    def test_viewer_cannot_add_measurement(self):
        viewer = User.objects.create_user('viewer_ma', password='pw12345')
        self.client.login(username='viewer_ma', password='pw12345')
        response = self.client.post(
            f'/projects/{self.project.pk}/measurements/add/',
            data={'reference': 'VIEWER-M', 'location': 'Test',
                  'system': self.system.pk, 'width': '1000', 'height': '1000', 'qty': '1'},
            follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(MeasurementItem.objects.filter(reference='VIEWER-M').exists())

    def test_salesman_can_create_customer(self):
        salesman = make_salesman('salesman_role_check')
        self.client.login(username='salesman_role_check', password='pw12345')
        response = self.client.post(
            '/projects/customers/new/', data={'name': 'Salesman New Co'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Customer.objects.filter(name='Salesman New Co').exists())

    def test_viewer_can_view_project_list(self):
        # Viewers should still be able to access read-only views.
        viewer = User.objects.create_user('viewer_read', password='pw12345')
        self.client.login(username='viewer_read', password='pw12345')
        response = self.client.get('/projects/')
        self.assertEqual(response.status_code, 200)

    def test_viewer_can_view_project_detail(self):
        viewer = User.objects.create_user('viewer_detail', password='pw12345')
        self.client.login(username='viewer_detail', password='pw12345')
        response = self.client.get(f'/projects/{self.project.pk}/')
        self.assertEqual(response.status_code, 200)


class ProjectDetailTemplateTests(TestCase):
    """
    Regression tests for a template bug found while writing this suite:
    project_detail.html crashed with an unhandled VariableDoesNotExist
    whenever project.salesman or project.locked_by was None, because
    `{{ x.get_full_name|default:x.username }}` evaluates x.username eagerly
    as the default filter's argument even when x itself is None. This isn't
    a hypothetical -- any project created without an explicit salesman
    (e.g. via Django admin, a data import, or any path other than the
    project_create view) hits this on page load, in any environment.
    """

    def setUp(self):
        self.user = User.objects.create_superuser('admin_tpl', 'a@x.com', 'pw12345')
        self.client.login(username='admin_tpl', password='pw12345')
        self.customer = Customer.objects.create(name='Template Test Customer')

    def test_project_detail_renders_without_a_salesman(self):
        project = Project.objects.create(
            reference='TPL-NOSALES', name='No Salesman', customer=self.customer, salesman=None)
        response = self.client.get(f'/projects/{project.pk}/')
        self.assertEqual(response.status_code, 200)

    def test_project_detail_renders_with_a_salesman(self):
        project = Project.objects.create(
            reference='TPL-SALES', name='Has Salesman', customer=self.customer, salesman=self.user)
        response = self.client.get(f'/projects/{project.pk}/')
        self.assertEqual(response.status_code, 200)

    def test_project_detail_renders_when_locked(self):
        project = Project.objects.create(
            reference='TPL-LOCKED', name='Locked', customer=self.customer, salesman=None)
        project.lock(self.user, 'testing')
        response = self.client.get(f'/projects/{project.pk}/')
        self.assertEqual(response.status_code, 200)

    def test_dashboard_renders_with_a_salesman_less_project(self):
        Project.objects.create(
            reference='TPL-DASH', name='Dashboard Test', customer=self.customer, salesman=None)
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
