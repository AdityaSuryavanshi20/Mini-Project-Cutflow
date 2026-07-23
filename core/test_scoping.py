"""
Regression tests for salesman data isolation.

Run with:
    python manage.py test core.test_scoping
"""
from django.contrib.auth.models import User
from django.test import TestCase, Client

from accounts.models import UserRole
from projects.models import Customer, Project


class SalesmanScopingTests(TestCase):
    def setUp(self):
        self.sales1 = User.objects.create_user('sales1', password='test1234')
        self.sales1.profile.role = UserRole.SALESMAN
        self.sales1.profile.save()

        self.sales2 = User.objects.create_user('sales2', password='test1234')
        self.sales2.profile.role = UserRole.SALESMAN
        self.sales2.profile.save()

        self.admin = User.objects.create_user('admin1', password='test1234')
        self.admin.profile.role = UserRole.ADMIN
        self.admin.profile.save()

        self.customer1 = Customer.objects.create(name='Alice', created_by=self.sales1)
        self.customer2 = Customer.objects.create(name='Bob', created_by=self.sales2)

        self.project1 = Project.objects.create(
            reference='R1', name='P1', customer=self.customer1,
            salesman=self.sales1, created_by=self.sales1)
        self.project2 = Project.objects.create(
            reference='R2', name='P2', customer=self.customer2,
            salesman=self.sales2, created_by=self.sales2)

    def test_salesman_sees_only_own_customers_in_list(self):
        c = Client()
        c.force_login(self.sales1)
        resp = c.get('/projects/customers/')
        names = {cust.name for cust in resp.context['customers']}
        self.assertEqual(names, {'Alice'})

    def test_salesman_sees_only_own_projects_in_list(self):
        c = Client()
        c.force_login(self.sales1)
        resp = c.get('/projects/')
        refs = {p.reference for p in resp.context['projects']}
        self.assertEqual(refs, {'R1'})

    def test_salesman_cannot_open_another_salesmans_project(self):
        c = Client()
        c.force_login(self.sales1)
        resp = c.get(f'/projects/{self.project2.pk}/')
        self.assertEqual(resp.status_code, 404)

    def test_salesman_can_open_own_project(self):
        c = Client()
        c.force_login(self.sales1)
        resp = c.get(f'/projects/{self.project1.pk}/')
        self.assertEqual(resp.status_code, 200)

    def test_salesman_cannot_open_another_salesmans_customer(self):
        c = Client()
        c.force_login(self.sales1)
        resp = c.get(f'/projects/customers/{self.customer2.pk}/')
        self.assertEqual(resp.status_code, 404)

    def test_admin_sees_everything(self):
        c = Client()
        c.force_login(self.admin)
        resp = c.get('/projects/')
        refs = {p.reference for p in resp.context['projects']}
        self.assertEqual(refs, {'R1', 'R2'})

    def test_salesman_cannot_assign_project_to_customer_they_dont_own(self):
        """A crafted POST shouldn't let sales1 create a project under sales2's customer."""
        c = Client()
        c.force_login(self.sales1)
        resp = c.post('/projects/new/', {
            'reference': 'HACK1',
            'name': 'Sneaky project',
            'customer': self.customer2.pk,
        })
        self.assertFalse(Project.objects.filter(reference='HACK1').exists())
