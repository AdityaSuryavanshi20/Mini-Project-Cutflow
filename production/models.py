from django.db import models
from django.contrib.auth.models import User
from projects.models import Project, MeasurementItem
from catalog.models import Profile


class ProductionJobStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    IN_PROGRESS = 'in_progress', 'In Progress'
    OPTIMIZED = 'optimized', 'Optimized'
    CUTTING = 'cutting', 'Cutting'
    ASSEMBLY = 'assembly', 'Assembly'
    QC = 'qc', 'Quality Check'
    COMPLETE = 'complete', 'Complete'


class ProductionJob(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='production_jobs')
    job_no = models.CharField(max_length=30, unique=True)
    status = models.CharField(max_length=20, choices=ProductionJobStatus.choices,
                               default=ProductionJobStatus.PENDING)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='production_jobs')
    scheduled_date = models.DateField(null=True, blank=True)
    completed_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                    related_name='production_jobs_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.job_no} – {self.project.reference}"


class ProductionItem(models.Model):
    """One window/door unit in a production job"""
    job = models.ForeignKey(ProductionJob, on_delete=models.CASCADE, related_name='items')
    measurement = models.ForeignKey(MeasurementItem, on_delete=models.SET_NULL,
                                     null=True, blank=True)
    line_no = models.CharField(max_length=10)
    reference = models.CharField(max_length=20, blank=True)
    location = models.CharField(max_length=100, blank=True)
    system = models.ForeignKey('catalog.System', on_delete=models.PROTECT)
    glass = models.ForeignKey('catalog.Glass', on_delete=models.SET_NULL, null=True, blank=True)
    color = models.ForeignKey('catalog.Color', on_delete=models.SET_NULL, null=True, blank=True)
    width = models.IntegerField()
    height = models.IntegerField()
    qty = models.PositiveIntegerField(default=1)
    n_panels = models.PositiveSmallIntegerField(default=1)
    description = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    diagnostics = models.TextField(blank=True, help_text='System warnings or formula diagnostics for this item')
    is_complete = models.BooleanField(default=False)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'line_no']

    def __str__(self):
        return f"{self.job.job_no}/{self.line_no} {self.reference}"

    @property
    def area_sqft(self):
        return round((self.width * self.height) / (304.8 ** 2) * self.qty, 3)


class ProductionCutItem(models.Model):
    """A computed profile cut for a production item"""
    production_item = models.ForeignKey(ProductionItem, on_delete=models.CASCADE,
                                         related_name='cut_items')
    profile = models.ForeignKey(Profile, on_delete=models.PROTECT)
    position = models.CharField(max_length=50, help_text='formula position key')
    cut_length_mm = models.IntegerField()
    left_angle = models.DecimalField(max_digits=5, decimal_places=1, default=90)
    right_angle = models.DecimalField(max_digits=5, decimal_places=1, default=90)
    quantity = models.PositiveSmallIntegerField(default=1)
    position_code = models.CharField(max_length=20, blank=True, help_text='e.g. F^A, S<B2')

    class Meta:
        ordering = ['profile__category', 'position']

    def __str__(self):
        return f"{self.profile.stock_no} {self.cut_length_mm}mm × {self.quantity}"


class HardwareRequirement(models.Model):
    """Hardware BOQ for a production item"""
    production_item = models.ForeignKey(ProductionItem, on_delete=models.CASCADE,
                                         related_name='hardware_items')
    hardware = models.ForeignKey('catalog.Hardware', on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.CharField(max_length=20, default='pcs')
    notes = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"{self.hardware.stock_no} × {self.quantity}"


class OptimizationRun(models.Model):
    """One optimization execution for a production job"""
    production_job = models.ForeignKey(ProductionJob, on_delete=models.CASCADE,
                                        related_name='optimization_runs')
    run_date = models.DateTimeField(auto_now_add=True)
    bar_length_mm = models.IntegerField(
        default=6000,
        help_text='Most common stock bar length used across this run. '
                   'Individual profiles/cuts may use other available stock lengths; '
                   'see OptimizationSegment and OptimizedCut for exact values.')
    kerf_mm = models.IntegerField(default=5)
    end_waste_mm = models.IntegerField(default=10)
    min_reusable_mm = models.IntegerField(default=300)
    total_bars_used = models.IntegerField(default=0)
    total_material_mm = models.IntegerField(default=0)
    total_cut_mm = models.IntegerField(default=0)
    total_waste_mm = models.IntegerField(default=0)
    utilisation_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True,
                                     help_text='Only one active run per job at a time')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"OptRun {self.pk} for {self.production_job.job_no}"


class OptimizationSegment(models.Model):
    """Per-profile optimization result within a run"""
    optimization_run = models.ForeignKey(OptimizationRun, on_delete=models.CASCADE,
                                          related_name='segments')
    profile = models.ForeignKey(Profile, on_delete=models.PROTECT)
    bars_required = models.IntegerField(default=0)
    bar_length_mm = models.IntegerField(
        default=6000,
        help_text='Most common stock bar length used in this segment. '
                   'See individual OptimizedCut.bar_length_mm for exact per-bar lengths '
                   'when multiple stock lengths were used.')
    total_cut_length_mm = models.IntegerField(default=0)
    waste_mm = models.IntegerField(default=0)
    offcut_mm = models.IntegerField(default=0)
    total_pieces = models.IntegerField(default=0)

    class Meta:
        ordering = ['profile__category', 'profile__stock_no']

    def __str__(self):
        return f"{self.profile.stock_no} – {self.bars_required} bars"


class OptimizedCut(models.Model):
    """Individual cut assignment in an optimization segment"""
    segment = models.ForeignKey(OptimizationSegment, on_delete=models.CASCADE,
                                 related_name='cuts')
    production_item = models.ForeignKey(ProductionItem, on_delete=models.SET_NULL,
                                         null=True, blank=True)
    bar_number = models.PositiveSmallIntegerField()
    bar_length_mm = models.IntegerField(
        default=6000, help_text='Actual stock bar length this cut was placed on')
    cut_length_mm = models.IntegerField()
    left_angle = models.DecimalField(max_digits=5, decimal_places=1, default=90)
    right_angle = models.DecimalField(max_digits=5, decimal_places=1, default=90)
    position_code = models.CharField(max_length=20, blank=True)
    start_position_mm = models.IntegerField(default=0)

    class Meta:
        ordering = ['bar_number', 'start_position_mm']

    def __str__(self):
        return f"Bar {self.bar_number} ({self.bar_length_mm}mm): {self.cut_length_mm}mm"


class ReusableOffcut(models.Model):
    """Leftover bar pieces large enough to reuse in future jobs"""
    profile = models.ForeignKey(Profile, on_delete=models.PROTECT)
    length_mm = models.IntegerField()
    source_job = models.ForeignKey(ProductionJob, on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name='offcuts_generated')
    used_in_job = models.ForeignKey(ProductionJob, on_delete=models.SET_NULL,
                                     null=True, blank=True, related_name='offcuts_used')
    is_available = models.BooleanField(default=True)
    location_notes = models.CharField(max_length=200, blank=True, help_text='Rack/shelf location')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-length_mm']

    def __str__(self):
        status = 'Available' if self.is_available else 'Used'
        return f"{self.profile.stock_no} {self.length_mm}mm [{status}]"
