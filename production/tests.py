"""
Tests for the production app — offcut inventory CRUD validation, and the
generate_items permission check that previously risked an AttributeError
for a user without a profile.
"""
from django.contrib.auth.models import User
from django.test import TestCase

from accounts.models import UserProfile
from catalog.models import Profile, ProfileCategory
from projects.models import Customer, Project
from .models import ProductionJob, ReusableOffcut

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



def make_profile(stock_no='PR-TEST'):
    return Profile.objects.create(stock_no=stock_no, name='Test Profile', category=ProfileCategory.OUTER_FRAME)


class OffcutInventoryViewTests(TestCase):
    """
    Regression tests for offcut_inventory, which previously 500'd on a
    non-numeric `?profile=` query parameter.
    """

    def setUp(self):
        self.user = User.objects.create_user('offcut_viewer', password='pw12345')
        self.client.login(username='offcut_viewer', password='pw12345')
        self.profile = make_profile()
        ReusableOffcut.objects.create(profile=self.profile, length_mm=1500, is_available=True)
        ReusableOffcut.objects.create(profile=self.profile, length_mm=800, is_available=False)

    def test_non_numeric_profile_param_does_not_crash(self):
        response = self.client.get('/production/offcuts/?profile=abc')
        self.assertEqual(response.status_code, 200)

    def test_negative_profile_param_does_not_crash(self):
        response = self.client.get('/production/offcuts/?profile=-5')
        self.assertEqual(response.status_code, 200)

    def test_zero_profile_param_does_not_crash(self):
        response = self.client.get('/production/offcuts/?profile=0')
        self.assertEqual(response.status_code, 200)

    def test_garbage_status_param_falls_back_to_available(self):
        response = self.client.get('/production/offcuts/?status=bogus')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['selected_status'], 'available')

    def test_valid_profile_filter_returns_only_that_profiles_offcuts(self):
        other_profile = make_profile(stock_no='PR-OTHER')
        ReusableOffcut.objects.create(profile=other_profile, length_mm=2000, is_available=True)

        response = self.client.get(f'/production/offcuts/?profile={self.profile.pk}&status=all')
        self.assertEqual(response.status_code, 200)
        returned_ids = {o.profile_id for o in response.context['offcuts']}
        self.assertEqual(returned_ids, {self.profile.pk})

    def test_status_available_filters_correctly(self):
        response = self.client.get('/production/offcuts/?status=available')
        offcuts = list(response.context['offcuts'])
        self.assertTrue(all(o.is_available for o in offcuts))

    def test_status_used_filters_correctly(self):
        response = self.client.get('/production/offcuts/?status=used')
        offcuts = list(response.context['offcuts'])
        self.assertTrue(all(not o.is_available for o in offcuts))


class OffcutAddViewTests(TestCase):
    def setUp(self):
        self.user = make_production_user('offcut_adder')
        self.client.login(username='offcut_adder', password='pw12345')
        self.profile = make_profile()

    def test_non_numeric_profile_id_does_not_crash(self):
        response = self.client.post(
            '/production/offcuts/add/', data={'profile': 'abc', 'length_mm': '500'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ReusableOffcut.objects.filter(length_mm=500).exists())

    def test_nonexistent_profile_id_is_rejected(self):
        response = self.client.post(
            '/production/offcuts/add/', data={'profile': '999999', 'length_mm': '500'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ReusableOffcut.objects.filter(length_mm=500).exists())

    def test_negative_length_is_rejected(self):
        response = self.client.post(
            '/production/offcuts/add/',
            data={'profile': self.profile.pk, 'length_mm': '-100'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ReusableOffcut.objects.filter(profile=self.profile, length_mm=-100).exists())

    def test_zero_length_is_rejected(self):
        response = self.client.post(
            '/production/offcuts/add/',
            data={'profile': self.profile.pk, 'length_mm': '0'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ReusableOffcut.objects.filter(profile=self.profile, length_mm=0).exists())

    def test_valid_offcut_is_created(self):
        response = self.client.post(
            '/production/offcuts/add/',
            data={'profile': self.profile.pk, 'length_mm': '1234'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            ReusableOffcut.objects.filter(profile=self.profile, length_mm=1234, is_available=True).exists())


class OffcutEditViewTests(TestCase):
    def setUp(self):
        self.user = make_production_user('offcut_editor')
        self.client.login(username='offcut_editor', password='pw12345')
        self.profile = make_profile()
        self.offcut = ReusableOffcut.objects.create(
            profile=self.profile, length_mm=1000, is_available=True)

    def test_non_numeric_length_keeps_previous_value(self):
        response = self.client.post(
            f'/production/offcuts/{self.offcut.pk}/edit/',
            data={'length_mm': 'abc'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.offcut.refresh_from_db()
        self.assertEqual(self.offcut.length_mm, 1000)

    def test_negative_length_keeps_previous_value(self):
        response = self.client.post(
            f'/production/offcuts/{self.offcut.pk}/edit/',
            data={'length_mm': '-50'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.offcut.refresh_from_db()
        self.assertEqual(self.offcut.length_mm, 1000)

    def test_valid_edit_updates_length(self):
        response = self.client.post(
            f'/production/offcuts/{self.offcut.pk}/edit/',
            data={'length_mm': '2500'}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.offcut.refresh_from_db()
        self.assertEqual(self.offcut.length_mm, 2500)


class GenerateItemsPermissionTests(TestCase):
    """
    Regression tests for generate_items, which previously raised a raw
    AttributeError for users without a profile once the project was locked
    (the can_edit() check failing forced evaluation of `.profile.is_admin`).
    """

    def setUp(self):
        self.customer = Customer.objects.create(name='Gen Items Customer')
        self.project = Project.objects.create(
            reference='GENITEMS-001', name='Gen Items Test', customer=self.customer)
        self.job = ProductionJob.objects.create(project=self.project, job_no='GENJOB-001')

    def test_user_without_profile_on_locked_project_is_denied_not_crashed(self):
        admin = User.objects.create_superuser('genitems_admin', 'a@x.com', 'pw12345')
        self.project.lock(admin, 'testing')

        user = User.objects.create_user('genitems_noprofile', password='pw12345')
        UserProfile.objects.filter(user=user).delete()
        user.refresh_from_db()
        self.assertFalse(hasattr(user, 'profile'))

        self.client.login(username='genitems_noprofile', password='pw12345')
        response = self.client.get(f'/production/{self.job.pk}/generate/', follow=True)
        self.assertEqual(response.status_code, 200)

    def test_superuser_can_generate_items_on_locked_project(self):
        admin = User.objects.create_superuser('genitems_admin2', 'a@x.com', 'pw12345')
        self.project.lock(admin, 'testing')
        self.client.login(username='genitems_admin2', password='pw12345')
        response = self.client.get(f'/production/{self.job.pk}/generate/', follow=True)
        self.assertEqual(response.status_code, 200)

    def test_regular_user_on_unlocked_project_can_generate_items(self):
        user = make_salesman('genitems_regular')
        self.client.login(username='genitems_regular', password='pw12345')
        response = self.client.get(f'/production/{self.job.pk}/generate/', follow=True)
        self.assertEqual(response.status_code, 200)
