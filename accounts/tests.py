"""
Tests for the accounts app -- login behavior, profile auto-creation, and
the role-defaulting fix (new superusers get role='admin' instead of the
'viewer' default that previously locked them out of admin-only actions).

Also covers a login_view crash found while writing this suite: it accessed
user.profile.is_active unguarded, so a user without a profile (e.g. one
created via a path that bypasses the post_save signal, or whose profile
was later deleted) got an unhandled 500 trying to log in at all.
"""
from django.contrib.auth.models import User
from django.test import TestCase

from .models import UserProfile, UserRole


class ProfileAutoCreationTests(TestCase):
    """Tests for the post_save signal in accounts/signals.py."""

    def test_regular_user_gets_a_profile_automatically(self):
        user = User.objects.create_user('regular_user', password='pw12345')
        self.assertTrue(hasattr(user, 'profile'))
        self.assertEqual(user.profile.role, UserRole.VIEWER)

    def test_superuser_gets_admin_role_automatically(self):
        # Regression test: previously every new user, including
        # superusers created via `createsuperuser`, defaulted to 'viewer',
        # which locked them out of admin-only actions on first login.
        admin = User.objects.create_superuser('new_admin', 'a@x.com', 'pw12345')
        self.assertTrue(hasattr(admin, 'profile'))
        self.assertEqual(admin.profile.role, UserRole.ADMIN)
        self.assertTrue(admin.profile.is_admin)

    def test_profile_is_not_recreated_or_reset_on_subsequent_saves(self):
        user = User.objects.create_user('persist_user', password='pw12345')
        user.profile.role = UserRole.PRODUCTION
        user.profile.save()
        # Saving the User again (e.g. updating email) must not reset the
        # role back to the post_save default.
        user.email = 'updated@example.com'
        user.save()
        user.refresh_from_db()
        self.assertEqual(user.profile.role, UserRole.PRODUCTION)


class LoginViewTests(TestCase):
    def test_valid_credentials_log_in_successfully(self):
        User.objects.create_user('login_good', password='pw12345')
        response = self.client.post(
            '/accounts/login/', data={'username': 'login_good', 'password': 'pw12345'},
            follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['user'].is_authenticated)

    def test_invalid_password_is_rejected_without_crashing(self):
        User.objects.create_user('login_badpw', password='pw12345')
        response = self.client.post(
            '/accounts/login/', data={'username': 'login_badpw', 'password': 'wrong'},
            follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['user'].is_authenticated)

    def test_nonexistent_username_is_rejected_without_crashing(self):
        response = self.client.post(
            '/accounts/login/', data={'username': 'does_not_exist', 'password': 'x'},
            follow=True)
        self.assertEqual(response.status_code, 200)

    def test_inactive_profile_blocks_login(self):
        user = User.objects.create_user('login_inactive', password='pw12345')
        user.profile.is_active = False
        user.profile.save()
        response = self.client.post(
            '/accounts/login/', data={'username': 'login_inactive', 'password': 'pw12345'},
            follow=True)
        self.assertFalse(response.context['user'].is_authenticated)

    def test_user_without_profile_is_denied_login_not_crashed(self):
        # Regression test for the unguarded `user.profile.is_active` access
        # that 500'd the login page for any user lacking a profile.
        user = User.objects.create_user('login_noprofile', password='pw12345')
        UserProfile.objects.filter(user=user).delete()
        user.refresh_from_db()
        self.assertFalse(hasattr(user, 'profile'))

        response = self.client.post(
            '/accounts/login/', data={'username': 'login_noprofile', 'password': 'pw12345'},
            follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['user'].is_authenticated)

    def test_already_authenticated_user_is_redirected_away_from_login(self):
        User.objects.create_user('already_in', password='pw12345')
        self.client.login(username='already_in', password='pw12345')
        response = self.client.get('/accounts/login/', follow=True)
        self.assertEqual(response.status_code, 200)
        # Should land on the dashboard, not see the login form again.
        self.assertNotIn(b'name="password"', response.content)


class ProfileViewTests(TestCase):
    """
    Regression tests for the profile page, whose template
    (accounts/profile.html) was missing entirely -- every visit 500'd with
    TemplateDoesNotExist, for every user, on a page reachable from the main
    navigation.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            'profile_view_user', password='pw12345',
            first_name='Jane', last_name='Doe', email='jane@example.com')
        self.client.login(username='profile_view_user', password='pw12345')

    def test_profile_page_renders_on_get(self):
        response = self.client.get('/accounts/profile/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'jane@example.com')

    def test_profile_update_saves_changes(self):
        response = self.client.post('/accounts/profile/', data={
            'first_name': 'Janet', 'last_name': 'Doe', 'email': 'janet@example.com',
            'phone': '555-1234',
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Janet')
        self.assertEqual(self.user.profile.phone, '555-1234')

    def test_profile_page_renders_with_blank_name(self):
        # A user with no first/last name set falls back to username in the
        # topbar (the get_full_name|default:username pattern) -- make sure
        # the profile page itself handles this fine too.
        blank_user = User.objects.create_user('blank_name_user', password='pw12345')
        self.client.login(username='blank_name_user', password='pw12345')
        response = self.client.get('/accounts/profile/')
        self.assertEqual(response.status_code, 200)


class ChangePasswordTemplateTests(TestCase):
    """
    Regression test for the change-password page, whose template
    (accounts/change_password.html) was also missing entirely.
    """

    def setUp(self):
        self.user = User.objects.create_user('changepw_get_user', password='pw12345')
        self.client.login(username='changepw_get_user', password='pw12345')

    def test_change_password_page_renders_on_get(self):
        response = self.client.get('/accounts/change-password/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Current Password')
    def setUp(self):
        self.user = User.objects.create_user('pwchange_user', password='oldpassword123')
        self.client.login(username='pwchange_user', password='oldpassword123')

    def test_mismatched_confirmation_is_rejected(self):
        response = self.client.post('/accounts/change-password/', data={
            'old_password': 'oldpassword123', 'new_password': 'newpass456',
            'confirm_password': 'different456',
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('oldpassword123'))

    def test_wrong_old_password_is_rejected(self):
        response = self.client.post('/accounts/change-password/', data={
            'old_password': 'totally-wrong', 'new_password': 'newpass456',
            'confirm_password': 'newpass456',
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('oldpassword123'))

    def test_valid_password_change_succeeds(self):
        response = self.client.post('/accounts/change-password/', data={
            'old_password': 'oldpassword123', 'new_password': 'newpass456',
            'confirm_password': 'newpass456',
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('newpass456'))

    def test_missing_old_password_does_not_crash(self):
        response = self.client.post('/accounts/change-password/', data={
            'new_password': 'newpass456', 'confirm_password': 'newpass456',
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('oldpassword123'))
