from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Customer(models.Model):
    name = models.CharField(max_length=200)
    company = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    address_line1 = models.CharField(max_length=255, blank=True)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    pincode = models.CharField(max_length=10, blank=True)
    delivery_address = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                   related_name='customers_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    @property
    def full_address(self):
        parts = [self.address_line1, self.address_line2, self.city, self.state, self.pincode]
        return ', '.join(p for p in parts if p)


class ProjectStatus(models.TextChoices):
    DRAFT = 'draft', 'Draft'
    SURVEY = 'survey', 'Survey Pending'
    QUOTED = 'quoted', 'Quoted'
    ORDERED = 'ordered', 'Order Confirmed'
    PRODUCTION = 'production', 'In Production'
    DELIVERED = 'delivered', 'Delivered'
    INSTALLED = 'installed', 'Installed'
    LOCKED = 'locked', 'Locked'
    CANCELLED = 'cancelled', 'Cancelled'


class Project(models.Model):
    reference = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='projects')
    status = models.CharField(max_length=20, choices=ProjectStatus.choices,
                               default=ProjectStatus.DRAFT)
    salesman = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='projects_sales')
    site_address = models.TextField(blank=True)
    survey_date = models.DateField(null=True, blank=True)
    survey_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='projects_surveyed')
    production_date = models.DateField(null=True, blank=True)
    delivery_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)
    is_locked = models.BooleanField(default=False)
    locked_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='projects_locked')
    locked_at = models.DateTimeField(null=True, blank=True)
    lock_reason = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                   related_name='projects_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.reference} – {self.name}"

    def can_edit(self, user):
        if self.is_locked:
            if user.is_superuser:
                return True
            return hasattr(user, 'profile') and user.profile.is_admin
        return True

    def lock(self, user, reason='Production approved'):
        self.is_locked = True
        self.locked_by = user
        self.locked_at = timezone.now()
        self.lock_reason = reason
        self.status = ProjectStatus.LOCKED
        self.save()

    def unlock(self, user):
        self.is_locked = False
        self.locked_by = None
        self.locked_at = None
        self.lock_reason = ''
        self.save()


class ProjectStatusHistory(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='status_history')
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class MeasurementItem(models.Model):
    """A single window/door opening measured on site"""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='measurements')
    line_no = models.CharField(max_length=10, help_text='e.g. 0001')
    reference = models.CharField(max_length=20, help_text='e.g. W1, D1')
    location = models.CharField(max_length=100, help_text='e.g. Living Room')
    system = models.ForeignKey('catalog.System', on_delete=models.PROTECT,
                               related_name='measurement_items')
    color = models.ForeignKey('catalog.Color', on_delete=models.SET_NULL, null=True, blank=True)
    glass = models.ForeignKey('catalog.Glass', on_delete=models.SET_NULL, null=True, blank=True)
    width = models.IntegerField(help_text='mm')
    height = models.IntegerField(help_text='mm')
    qty = models.PositiveIntegerField(default=1)
    description = models.CharField(max_length=255, blank=True)
    n_panels = models.PositiveSmallIntegerField(default=1)
    hinge_side = models.CharField(max_length=5, blank=True,
                                  choices=[('L', 'Left'), ('R', 'Right'), ('', 'N/A')])
    opening_angles = models.CharField(max_length=50, blank=True)
    flyscreen = models.BooleanField(default=False)
    drainage = models.BooleanField(default=False)
    is_toughened = models.BooleanField(default=False)
    surveyed_from = models.CharField(max_length=10, blank=True,
                                     choices=[('inside', 'Inside'), ('outside', 'Outside')])
    notes = models.TextField(blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    final_width = models.IntegerField(null=True, blank=True)
    final_height = models.IntegerField(null=True, blank=True)
    dimensions_confirmed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'line_no']

    def __str__(self):
        return f"{self.project.reference}/{self.line_no} {self.reference} {self.location}"

    @property
    def effective_width(self):
        return self.final_width if self.dimensions_confirmed and self.final_width else self.width

    @property
    def effective_height(self):
        return self.final_height if self.dimensions_confirmed and self.final_height else self.height

    @property
    def area_sqft(self):
        return round((self.effective_width * self.effective_height) / (304.8 ** 2) * self.qty, 3)

    @property
    def area_sqm(self):
        return round((self.effective_width * self.effective_height) / 1_000_000 * self.qty, 4)
