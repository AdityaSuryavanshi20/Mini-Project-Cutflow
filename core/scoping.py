"""
Central place for "who can see what" queryset scoping.

Only the 'salesman' role is restricted (per product decision). Admins,
production, viewer, and superuser accounts always see everything.

Ownership chain:
  Customer.created_by  — a salesman only sees customers they created
  Project.salesman      — a salesman only sees projects assigned to them
  Quotation / ProductionJob — inherited from their project's `salesman` FK

Import models lazily inside each function to avoid circular imports
(this module is imported by projects/quotations/production/core views).
"""


def is_restricted_salesman(user):
    """
    True when `user` should only see their own customers/projects — i.e.
    they hold the 'salesman' role and are not an admin or superuser.
    """
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return False
    profile = getattr(user, 'profile', None)
    if profile is None:
        return False
    if profile.is_admin:
        return False
    return profile.is_salesman


def scoped_customers(user):
    from projects.models import Customer
    qs = Customer.objects.all()
    if is_restricted_salesman(user):
        qs = qs.filter(created_by=user)
    return qs


def scoped_projects(user):
    from projects.models import Project
    qs = Project.objects.all()
    if is_restricted_salesman(user):
        qs = qs.filter(salesman=user)
    return qs


def scoped_quotations(user):
    from quotations.models import Quotation
    qs = Quotation.objects.all()
    if is_restricted_salesman(user):
        qs = qs.filter(project__salesman=user)
    return qs


def scoped_jobs(user):
    from production.models import ProductionJob
    qs = ProductionJob.objects.all()
    if is_restricted_salesman(user):
        qs = qs.filter(project__salesman=user)
    return qs
