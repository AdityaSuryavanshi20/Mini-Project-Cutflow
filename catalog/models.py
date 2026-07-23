from django.db import models
from django.core.validators import MinValueValidator


class Brand(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Color(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, blank=True, help_text='RAL or hex code')
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.code})" if self.code else self.name


class SystemCategory(models.TextChoices):
    CASEMENT = 'casement', 'Casement'
    SLIDING = 'sliding', 'Sliding'
    FIXED = 'fixed', 'Fixed'
    DOOR_SWING = 'door_swing', 'Swing Door'
    DOOR_SLIDING = 'door_sliding', 'Sliding Door'
    LOUVER = 'louver', 'Louver'
    COMPOSITE = 'composite', 'Composite'


class SystemMaterial(models.TextChoices):
    ALUMINIUM = 'aluminium', 'Aluminium'
    UPVC = 'upvc', 'uPVC'


class System(models.Model):
    """Window/door system type (e.g. SY01 Hinge Int Glz System)"""
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=150)
    category = models.CharField(max_length=30, choices=SystemCategory.choices)
    material = models.CharField(max_length=20, choices=SystemMaterial.choices,
                                 default=SystemMaterial.UPVC)
    brand = models.ForeignKey(Brand, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    markup_percent = models.DecimalField(max_digits=5, decimal_places=2, default=15,
                                         help_text='Standard system markup %')
    premium_markup_percent = models.DecimalField(max_digits=5, decimal_places=2, default=25,
                                                 help_text='Premium system markup %')
    budget_markup_percent = models.DecimalField(max_digits=5, decimal_places=2, default=10,
                                               help_text='Budget system markup %')

    class Meta:
        ordering = ['sort_order', 'code']

    def __str__(self):
        material_label = self.get_material_display()
        return f"{self.code} – {self.name} ({material_label})"

    def get_markup_percent(self, variant='standard'):
        if variant == 'premium':
            return float(self.premium_markup_percent)
        if variant == 'budget':
            return float(self.budget_markup_percent)
        return float(self.markup_percent)


class SystemProfileRole(models.TextChoices):
    OUTER_FRAME_TOP = 'outer_frame_top', 'Outer Frame Top'
    OUTER_FRAME_BOTTOM = 'outer_frame_bottom', 'Outer Frame Bottom'
    OUTER_FRAME_LEFT = 'outer_frame_left', 'Outer Frame Left'
    OUTER_FRAME_RIGHT = 'outer_frame_right', 'Outer Frame Right'
    SHUTTER_VERTICAL = 'shutter_vertical', 'Shutter Vertical'
    SHUTTER_HORIZONTAL = 'shutter_horizontal', 'Shutter Horizontal'
    INTERLOCK = 'interlock', 'Interlock'
    MULLION = 'mullion', 'Mullion'
    TRACK = 'track', 'Track'
    BEAD_HORIZONTAL = 'bead_horizontal', 'Bead Horizontal'
    BEAD_VERTICAL = 'bead_vertical', 'Bead Vertical'
    ANCILLARY = 'ancillary', 'Ancillary'


class SystemProfile(models.Model):
    system = models.ForeignKey(System, on_delete=models.CASCADE,
                               related_name='system_profiles')
    profile = models.ForeignKey('Profile', on_delete=models.CASCADE,
                                related_name='system_profiles')
    role = models.CharField(max_length=40, choices=SystemProfileRole.choices)
    formula_group = models.CharField(max_length=50, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_required = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['system', 'sort_order', 'role', 'profile__stock_no']
        unique_together = [('system', 'profile', 'role')]

    def __str__(self):
        return f"{self.system.code} / {self.profile.stock_no} [{self.role}]"


class ProfileCategory(models.TextChoices):
    OUTER_FRAME = 'outer_frame', 'Outer Frame'
    SASH = 'sash', 'Sash'
    TRANSOM = 'transom', 'Transom'
    MULLION = 'mullion', 'Mullion'
    BEAD = 'bead', 'Glass Bead'
    SLIDER_FRAME = 'slider_frame', 'Slider Frame'
    SLIDER_SASH = 'slider_sash', 'Slider Sash'
    REINFORCEMENT = 'reinforcement', 'Reinforcement'
    GASKET = 'gasket', 'Gasket'
    ANCILLARY = 'ancillary', 'Ancillary'


class Profile(models.Model):
    """Individual aluminium/uPVC profile"""
    stock_no = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=150)
    category = models.CharField(max_length=30, choices=ProfileCategory.choices)
    system = models.ForeignKey(System, on_delete=models.SET_NULL, null=True, blank=True, related_name='profiles')
    brand = models.ForeignKey(Brand, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.TextField(blank=True)
    
    # Physical properties
    weight_per_meter = models.DecimalField(max_digits=8, decimal_places=4, default=0,
                                           help_text='kg/m')
    cost_per_meter = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                         help_text='INR per metre')
    standard_bar_length = models.IntegerField(default=6000, help_text='mm')

    # Cutting offsets stored per profile
    offset_left = models.IntegerField(default=0, help_text='mm')
    offset_right = models.IntegerField(default=0, help_text='mm')
    offset_top = models.IntegerField(default=0, help_text='mm')
    offset_bottom = models.IntegerField(default=0, help_text='mm')

    # Default cut angles
    default_left_angle = models.DecimalField(max_digits=5, decimal_places=1, default=90)
    default_right_angle = models.DecimalField(max_digits=5, decimal_places=1, default=90)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category', 'stock_no']

    def __str__(self):
        return f"{self.stock_no} – {self.name}"

    def available_stock_lengths(self):
        """
        All stock lengths (mm) this profile is carried in, including the
        primary `standard_bar_length`. Used by the bar optimizer to pick the
        most economical stock length per bar instead of always assuming a
        single fixed length.
        """
        extra = list(
            self.stock_lengths.filter(is_active=True).values_list('length_mm', flat=True)
        )
        lengths = {int(self.standard_bar_length)} | {int(v) for v in extra}
        return sorted(lengths)


class ProfileStockLength(models.Model):
    """Additional stock bar length a profile is carried in, beyond standard_bar_length"""
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='stock_lengths')
    length_mm = models.IntegerField(help_text='Stock bar length in mm')
    cost_per_meter_override = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text='Leave blank to use the profile\u2019s standard cost per metre')
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['profile', 'length_mm']
        unique_together = [('profile', 'length_mm')]

    def __str__(self):
        return f"{self.profile.stock_no} @ {self.length_mm}mm"


class ProfileFormula(models.Model):
    """Dynamic formula for computing cut length of a profile in a system"""
    class FormulaType(models.TextChoices):
        CUT = 'cut', 'Cut'
        QUANTITY = 'quantity', 'Quantity'
        GLASS = 'glass', 'Glass'
        HARDWARE = 'hardware', 'Hardware'
        OTHER = 'other', 'Other'

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='formulas')
    system = models.ForeignKey(System, on_delete=models.CASCADE, related_name='profile_formulas')
    system_profile = models.ForeignKey(SystemProfile, null=True, blank=True,
                                       on_delete=models.CASCADE, related_name='formulas')
    position = models.CharField(max_length=50, help_text='e.g. frame_width, frame_height, sash_width')
    formula_type = models.CharField(max_length=20, choices=FormulaType.choices,
                                    default=FormulaType.CUT)
    panel_condition = models.CharField(max_length=255, blank=True,
                                       help_text='Optional boolean condition using W, H, n_panels')
    min_width = models.IntegerField(null=True, blank=True, help_text='Minimum W to apply formula')
    max_width = models.IntegerField(null=True, blank=True, help_text='Maximum W to apply formula')
    min_height = models.IntegerField(null=True, blank=True, help_text='Minimum H to apply formula')
    max_height = models.IntegerField(null=True, blank=True, help_text='Maximum H to apply formula')
    formula = models.CharField(max_length=255,
                               help_text='Expression using W, H, offset_l, offset_r, offset_t, offset_b, n_panels')
    quantity_formula = models.CharField(max_length=100, default='1',
                                        help_text='Expression for piece count, e.g. 2 or n_panels*2')
    cut_angle_left = models.DecimalField(max_digits=5, decimal_places=1, default=90)
    cut_angle_right = models.DecimalField(max_digits=5, decimal_places=1, default=90)
    remarks = models.CharField(max_length=255, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['system', 'profile__category', 'sort_order']
        unique_together = [('profile', 'system', 'position')]

    def __str__(self):
        return f"{self.system.code} / {self.profile.stock_no} [{self.position}]: {self.formula}"


class GlassSpecification(models.TextChoices):
    CLEAR = 'clear', 'Clear'
    TINTED = 'tinted', 'Tinted'
    FROSTED = 'frosted', 'Frosted'
    TOUGHENED = 'toughened', 'Toughened'
    LAMINATED = 'laminated', 'Laminated'
    DGU = 'dgu', 'DGU (Double Glazed)'
    LOW_E = 'low_e', 'Low-E'
    REFLECTIVE = 'reflective', 'Reflective'


class Glass(models.Model):
    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=150)
    specification = models.CharField(max_length=20, choices=GlassSpecification.choices)
    thickness = models.CharField(max_length=30, help_text='e.g. 5-10-6 or 6mm')
    cost_per_sqft = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cost_per_sqm = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    weight_per_sqm = models.DecimalField(max_digits=8, decimal_places=3, default=0)
    is_toughened = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Glasses'
        ordering = ['specification', 'name']

    def __str__(self):
        return f"{self.code} – {self.name} ({self.thickness})"


class HardwareCategory(models.TextChoices):
    HINGE = 'hinge', 'Hinge'
    HANDLE = 'handle', 'Handle'
    LOCK = 'lock', 'Lock & Espag'
    ROLLER = 'roller', 'Roller'
    GASKET = 'gasket', 'Gasket'
    SCREW = 'screw', 'Screw & Fastener'
    ACCESSORY = 'accessory', 'Accessory'
    INSTALLATION = 'installation', 'Installation Material'


class Hardware(models.Model):
    stock_no = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=150)
    category = models.CharField(max_length=20, choices=HardwareCategory.choices)
    brand = models.ForeignKey(Brand, on_delete=models.SET_NULL, null=True, blank=True)
    unit = models.CharField(max_length=20, default='pcs', help_text='pcs / m / set')
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    weight_per_unit = models.DecimalField(max_digits=8, decimal_places=3, default=0)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['category', 'stock_no']

    def __str__(self):
        return f"{self.stock_no} – {self.name}"


class SystemHardwareRule(models.Model):
    """Rules for how many hardware items a system needs per unit"""
    system = models.ForeignKey(System, on_delete=models.CASCADE, related_name='hardware_rules')
    hardware = models.ForeignKey(Hardware, on_delete=models.CASCADE)
    quantity_formula = models.CharField(max_length=100, default='1',
                                        help_text='Expression using n_panels, n_sashes, qty')
    notes = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [('system', 'hardware')]

    def __str__(self):
        return f"{self.system.code} – {self.hardware.stock_no} × {self.quantity_formula}"


class CompanySettings(models.Model):
    """Singleton – company branding and global config"""
    company_name = models.CharField(max_length=200, default='CutFlow Fenestration')
    address_line1 = models.CharField(max_length=200, blank=True)
    address_line2 = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    pincode = models.CharField(max_length=10, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    logo = models.ImageField(upload_to='company/', blank=True, null=True)
    gst_no = models.CharField(max_length=20, blank=True)
    sgst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=9)
    cgst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=9)
    igst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=18)
    quotation_validity_days = models.IntegerField(default=30)
    default_payment_terms = models.TextField(default='50% advance, balance before delivery.')
    quotation_terms = models.TextField(blank=True)
    default_bar_length_mm = models.IntegerField(default=6000)
    kerf_mm = models.IntegerField(default=5)
    end_waste_mm = models.IntegerField(default=10)
    min_reusable_offcut_mm = models.IntegerField(default=300)
    fabrication_rate_per_meter = models.DecimalField(max_digits=10, decimal_places=2, default=25,
                                                   help_text='Fabrication cost per running metre')
    material_wastage_percent = models.DecimalField(max_digits=5, decimal_places=2, default=8,
                                                   help_text='Default material wastage percentage')
    profit_margin_percent = models.DecimalField(max_digits=5, decimal_places=2, default=20,
                                               help_text='Default profit margin percentage')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Company Settings'
        verbose_name_plural = 'Company Settings'

    def __str__(self):
        return self.company_name

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj