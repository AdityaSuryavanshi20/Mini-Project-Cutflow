"""
CutFlow Initial Data Migration
Seeds: brands, colors, systems, profiles, profile formulas, glass types, hardware, company settings
Run after: python manage.py migrate
Command: python manage.py loaddata initial_data
Or: python manage.py shell < core/management/commands/seed_data.py
"""
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = 'Seed initial catalog data for CutFlow'

    @transaction.atomic
    def handle(self, *args, **options):
        from catalog.models import (
            Brand, Color, System, SystemCategory, SystemMaterial,
            Profile, ProfileCategory, ProfileFormula,
            Glass, GlassSpecification,
            Hardware, HardwareCategory,
            SystemHardwareRule, CompanySettings
        )

        self.stdout.write('Seeding brands...')
        brands = {}
        for name in ['Generic', 'Rehau', 'VEKA', 'Schuco', 'Aluplast', 'Fenesta']:
            b, _ = Brand.objects.get_or_create(name=name)
            brands[name] = b

        self.stdout.write('Seeding colors...')
        for name, code in [
            ('White', 'RAL 9016'), ('Ivory', 'RAL 1014'),
            ('Grey', 'RAL 7035'), ('Dark Grey', 'RAL 7016'),
            ('Black', 'RAL 9005'), ('Brown', 'RAL 8014'),
            ('Woodgrain Oak', ''), ('Woodgrain Mahogany', ''),
        ]:
            Color.objects.get_or_create(name=name, defaults={'code': code})

        self.stdout.write('Seeding systems...')
        systems_data = [
            ('SY01', 'Hinge Int Glz System', SystemCategory.CASEMENT, SystemMaterial.ALUMINIUM),
            ('SY02', 'Sliding 2-Track System', SystemCategory.SLIDING, SystemMaterial.ALUMINIUM),
            ('SY03', 'Sliding 3-Track System', SystemCategory.SLIDING, SystemMaterial.ALUMINIUM),
            ('SY04', 'Fixed Frame System', SystemCategory.FIXED, SystemMaterial.ALUMINIUM),
            ('SY05', 'Tilt & Turn System', SystemCategory.CASEMENT, SystemMaterial.ALUMINIUM),
            ('SY06', 'Super System Door', SystemCategory.DOOR_SWING, SystemMaterial.ALUMINIUM),
            ('SY07', 'Sliding Door System', SystemCategory.DOOR_SLIDING, SystemMaterial.ALUMINIUM),
            ('SY08', 'Louvre System', SystemCategory.LOUVER, SystemMaterial.ALUMINIUM),
            ('AL01', 'Aluminum Casement System', SystemCategory.CASEMENT, SystemMaterial.ALUMINIUM),
            ('UP01', 'uPVC Casement System', SystemCategory.CASEMENT, SystemMaterial.UPVC),
        ]
        systems = {}
        for code, name, cat, material in systems_data:
            s, created = System.objects.get_or_create(
                code=code, defaults={'name': name, 'category': cat, 'material': material, 'brand': brands['Generic']})
            if not created and s.material != material:
                s.material = material
                s.save(update_fields=['material'])
            systems[code] = s

        self.stdout.write('Seeding profiles...')
        profiles_data = [
            # (stock_no, name, category, bar_len, wt, cost, ol, or_, ot, ob, la, ra)
            ('OF004W', 'Outer Frame', ProfileCategory.OUTER_FRAME, 6000, 1.2, 320, 0, 0, 0, 0, 90, 90),
            ('TS001W', 'T Sash', ProfileCategory.SASH, 6000, 0.9, 240, 3, 3, 3, 3, 90, 90),
            ('TM001W', 'T Transom/Mullion', ProfileCategory.TRANSOM, 6000, 0.85, 220, 0, 0, 0, 0, 90, 90),
            ('ZM001W', 'Z Transom/Mullion', ProfileCategory.MULLION, 6000, 0.88, 230, 0, 0, 0, 0, 90, 90),
            ('ZS001W', 'Z Sash', ProfileCategory.SASH, 6000, 0.92, 250, 3, 3, 3, 3, 90, 90),
            ('ZS003W', 'Z Sash (Wide)', ProfileCategory.SASH, 6000, 0.98, 260, 3, 3, 3, 3, 90, 90),
            ('SOF01W', '2T Slider Frame', ProfileCategory.SLIDER_FRAME, 6000, 1.1, 300, 0, 0, 0, 0, 90, 90),
            ('SS001W', 'Slider Sash', ProfileCategory.SLIDER_SASH, 6000, 0.95, 255, 3, 3, 3, 3, 90, 90),
            ('FM001W', 'French Mullion', ProfileCategory.MULLION, 6000, 0.8, 210, 0, 0, 0, 0, 90, 90),
            ('WM_GB15W', 'Slp Co-ex Bead 15mm', ProfileCategory.BEAD, 6000, 0.12, 35, 0, 0, 0, 0, 90, 90),
            ('WM_GB17W', 'Slp Co-ex Bead 17mm', ProfileCategory.BEAD, 6000, 0.14, 38, 0, 0, 0, 0, 90, 90),
            ('WM_GB3W', 'Bv. Co-ex Bead', ProfileCategory.BEAD, 6000, 0.13, 36, 0, 0, 0, 0, 90, 90),
            ('AL-OF01', 'Aluminum Outer Frame', ProfileCategory.OUTER_FRAME, 6000, 1.3, 350, 0, 0, 0, 0, 45, 45),
            ('AL-S01', 'Aluminum Sash', ProfileCategory.SASH, 6000, 1.0, 270, 3, 3, 3, 3, 45, 45),
            ('UP-OF01', 'uPVC Outer Frame', ProfileCategory.OUTER_FRAME, 6000, 1.5, 300, 0, 0, 0, 0, 45, 45),
            ('UP-S01', 'uPVC Sash', ProfileCategory.SASH, 6000, 1.2, 250, 6, 6, 6, 6, 45, 45),
            ('AL-MSH01', 'Aluminum Mesh Frame', ProfileCategory.SASH, 6000, 0.6, 180, 0, 0, 0, 0, 45, 45),
            ('UP-MSH01', 'uPVC Mesh Frame', ProfileCategory.SASH, 6000, 0.7, 160, 0, 0, 0, 0, 45, 45),
        ]
        profiles = {}
        for row in profiles_data:
            sn, name, cat, bl, wt, cost, ol, orr, ot, ob, la, ra = row
            p, _ = Profile.objects.get_or_create(
                stock_no=sn,
                defaults=dict(
                    name=name, category=cat, brand=brands['Generic'],
                    standard_bar_length=bl,
                    weight_per_meter=wt, cost_per_meter=cost,
                    offset_left=ol, offset_right=orr, offset_top=ot, offset_bottom=ob,
                    default_left_angle=la, default_right_angle=ra,
                )
            )
            profiles[sn] = p

        self.stdout.write('Seeding profile formulas for SY01 Casement...')
        sy01 = systems['SY01']
        formulas_sy01 = [
            # (profile_sn, position, formula, qty_formula, l_angle, r_angle)
            ('OF004W', 'frame_width_top',    'W',    '1', 90, 90),
            ('OF004W', 'frame_width_bottom', 'W',    '1', 90, 90),
            ('OF004W', 'frame_height_left',  'H',    '1', 90, 90),
            ('OF004W', 'frame_height_right', 'H',    '1', 90, 90),
            ('TS001W', 'sash_width_top',     'W - offset_l - offset_r',  'n_panels', 90, 90),
            ('TS001W', 'sash_width_bottom',  'W - offset_l - offset_r',  'n_panels', 90, 90),
            ('TS001W', 'sash_height_left',   'H - offset_t - offset_b',  'n_panels', 90, 90),
            ('TS001W', 'sash_height_right',  'H - offset_t - offset_b',  'n_panels', 90, 90),
            ('TM001W', 'transom_width',       'W - offset_l - offset_r',  '1', 90, 90),
        ]
        for sn, pos, formula, qty_f, la, ra in formulas_sy01:
            if sn in profiles:
                ProfileFormula.objects.get_or_create(
                    profile=profiles[sn], system=sy01, position=pos,
                    defaults=dict(formula=formula, quantity_formula=qty_f,
                                  cut_angle_left=la, cut_angle_right=ra)
                )

        self.stdout.write('Seeding profile formulas for AL01 and UP01...')
        formulas_al01 = [
            ('AL-OF01', 'frame_width_top',    'W',    '1', 45, 45),
            ('AL-OF01', 'frame_width_bottom', 'W',    '1', 45, 45),
            ('AL-OF01', 'frame_height_left',  'H',    '1', 45, 45),
            ('AL-OF01', 'frame_height_right', 'H',    '1', 45, 45),
            ('AL-S01', 'sash_width_top',     'W - offset_l - offset_r',  'n_panels', 45, 45),
            ('AL-S01', 'sash_width_bottom',  'W - offset_l - offset_r',  'n_panels', 45, 45),
            ('AL-S01', 'sash_height_left',   'H - offset_t - offset_b',  'n_panels', 45, 45),
            ('AL-S01', 'sash_height_right',  'H - offset_t - offset_b',  'n_panels', 45, 45),
            ('AL-MSH01', 'mesh_width_top',    'W - 40', '1', 45, 45),
            ('AL-MSH01', 'mesh_width_bottom', 'W - 40', '1', 45, 45),
            ('AL-MSH01', 'mesh_height_left',  'H - 40', '1', 45, 45),
            ('AL-MSH01', 'mesh_height_right', 'H - 40', '1', 45, 45),
        ]
        for sn, pos, formula, qty_f, la, ra in formulas_al01:
            if sn in profiles:
                ProfileFormula.objects.get_or_create(
                    profile=profiles[sn], system=systems['AL01'], position=pos,
                    defaults=dict(formula=formula, quantity_formula=qty_f,
                                  cut_angle_left=la, cut_angle_right=ra)
                )

        formulas_up01 = [
            ('UP-OF01', 'frame_width_top',    'W',    '1', 45, 45),
            ('UP-OF01', 'frame_width_bottom', 'W',    '1', 45, 45),
            ('UP-OF01', 'frame_height_left',  'H',    '1', 45, 45),
            ('UP-OF01', 'frame_height_right', 'H',    '1', 45, 45),
            ('UP-S01', 'sash_width_top',     'W - offset_l - offset_r',  'n_panels', 45, 45),
            ('UP-S01', 'sash_width_bottom',  'W - offset_l - offset_r',  'n_panels', 45, 45),
            ('UP-S01', 'sash_height_left',   'H - offset_t - offset_b',  'n_panels', 45, 45),
            ('UP-S01', 'sash_height_right',  'H - offset_t - offset_b',  'n_panels', 45, 45),
            ('UP-MSH01', 'mesh_width_top',    'W - 40', '1', 45, 45),
            ('UP-MSH01', 'mesh_width_bottom', 'W - 40', '1', 45, 45),
            ('UP-MSH01', 'mesh_height_left',  'H - 40', '1', 45, 45),
            ('UP-MSH01', 'mesh_height_right', 'H - 40', '1', 45, 45),
        ]
        for sn, pos, formula, qty_f, la, ra in formulas_up01:
            if sn in profiles:
                ProfileFormula.objects.get_or_create(
                    profile=profiles[sn], system=systems['UP01'], position=pos,
                    defaults=dict(formula=formula, quantity_formula=qty_f,
                                  cut_angle_left=la, cut_angle_right=ra)
                )

        self.stdout.write('Seeding glass types...')
        glass_data = [
            ('G-5CL', '5mm Clear', GlassSpecification.CLEAR, '5mm', 45, 484, 12.5, False),
            ('G-6CL', '6mm Clear', GlassSpecification.CLEAR, '6mm', 55, 592, 15.0, False),
            ('G-5FR', '5mm Frosted', GlassSpecification.FROSTED, '5mm', 60, 646, 12.5, False),
            ('G-5TG', '5mm Toughened', GlassSpecification.TOUGHENED, '5mm', 90, 968, 12.5, True),
            ('G-6TG', '6mm Toughened', GlassSpecification.TOUGHENED, '6mm', 110, 1184, 15.0, True),
            ('G-5106CL', '5-10-6 Clear DGU', GlassSpecification.DGU, '5-10-6', 185, 1990, 26.0, False),
            ('G-5106TG', '5-10-6 Toughened DGU', GlassSpecification.DGU, '5-10-6 Toughened', 280, 3014, 26.0, True),
            ('G-6106TG', '6-10-6 Toughened DGU', GlassSpecification.DGU, '6-10-6 Toughened', 320, 3445, 29.0, True),
        ]
        for code, name, spec, thick, cpf, cpm, wt, tough in glass_data:
            Glass.objects.get_or_create(
                code=code,
                defaults=dict(name=name, specification=spec, thickness=thick,
                              cost_per_sqft=cpf, cost_per_sqm=cpm,
                              weight_per_sqm=wt, is_toughened=tough)
            )

        self.stdout.write('Seeding hardware...')
        hw_data = [
            ('BUTTHNGWHT',   'Butt Hinge (2D) White',     HardwareCategory.HINGE,     'pcs', 140, 0.65),
            ('FLGHNG-WHT',   'Flag/3D Hinge White',        HardwareCategory.HINGE,     'pcs', 190, 0.89),
            ('FRHSS14-L',    'Friction Hinge L 14" SS',    HardwareCategory.HINGE,     'pcs', 352, 0.61),
            ('FRHSS14-R',    'Friction Hinge R 14" SS',    HardwareCategory.HINGE,     'pcs', 352, 0.61),
            ('HNDL1-L-WHT',  'Cockspur Handle LK L White', HardwareCategory.HANDLE,    'pcs', 125, 0.40),
            ('HNDL1-R-WHT',  'Cockspur Handle LK R White', HardwareCategory.HANDLE,    'pcs', 125, 0.40),
            ('HNDL1A-WHT',   'Door Handle w/ Key White',   HardwareCategory.HANDLE,    'pcs', 135, 1.10),
            ('SLHNDL1AWHT',  'Slider Handle A White',      HardwareCategory.HANDLE,    'pcs', 110, 0.65),
            ('CDESPSS7',     '25 Door SSEspag 1800',        HardwareCategory.LOCK,      'pcs', 600, 1.23),
            ('SLESG1SS6',    '7.5 SLD SSEspag 1200',        HardwareCategory.LOCK,      'pcs', 277, 0.57),
            ('ROLLER1',      'Slider Roller 1',             HardwareCategory.ROLLER,    'pcs', 150, 0.05),
            ('KEEPER/STKR',  'Slider Striker',              HardwareCategory.ACCESSORY, 'pcs',  47, 0.05),
            ('STRKR3',       'Door Striker',                HardwareCategory.ACCESSORY, 'pcs',  40, 0.05),
            ('STRKR4',       'Door Center Striker',         HardwareCategory.ACCESSORY, 'pcs',  45, 0.05),
            ('Shootbolt1',   'FR Window Shootbolt',         HardwareCategory.LOCK,      'pcs', 164, 0.39),
            ('ShootboltKeep','Shootbolt Keeper',            HardwareCategory.ACCESSORY, 'pcs',  95, 0.02),
            ('BumpStp.',     'Bump Stop Base',              HardwareCategory.ACCESSORY, 'pcs',  25, 0.25),
            ('BumpStpRubber','Bump Stop Rubber',            HardwareCategory.ACCESSORY, 'pcs',  20, 0.15),
            ('CasementWedge','Casement Wedge',              HardwareCategory.ACCESSORY, 'pcs',   6, 0.02),
            ('CockspurWedge','Cockspur Wedge',              HardwareCategory.ACCESSORY, 'pcs',  70, 0.02),
            ('TR254',        'TurnRestrictor 254mm',        HardwareCategory.ACCESSORY, 'pcs', 180, 0.80),
            ('CBLOCK01',     'Cavity Locking Block',        HardwareCategory.ACCESSORY, 'pcs',  10, 0.01),
            ('GBRIDGE',      'Glazing Bridge',              HardwareCategory.ACCESSORY, 'pcs',  10, 0.06),
            ('RBLOCK01',     'Run Up Block',                HardwareCategory.ACCESSORY, 'pcs',  12, 0.02),
            ('FR01C',        'French End Caps',             HardwareCategory.ACCESSORY, 'pcs', 108, 0.03),
            ('MSH-FIBER',    'Fiberglass Mesh Netting',     HardwareCategory.ACCESSORY, 'sqm', 80, 0.15),
            ('MSH-SPLINE',   'Mesh Rubber Spline/Gasket',   HardwareCategory.ACCESSORY, 'm', 15, 0.05),
            # Screws
            ('WM_SCREW2',    'Reinforcement Screw',         HardwareCategory.SCREW,     'pcs',   1, 0.0),
            ('CBLOCKSCRW',   'Cavity Locking Block Screw',  HardwareCategory.SCREW,     'pcs',   1, 0.0),
            ('WM_BUTTHNGSCRW','Butt Hinge Screw',           HardwareCategory.SCREW,     'pcs',   2, 0.0),
            # Installation
            ('BackROD',      'Foam/Backer Rod',             HardwareCategory.INSTALLATION, 'm',   0, 0.0),
            ('FScrew8x100',  'Install Screw 8×100',         HardwareCategory.INSTALLATION, 'pcs', 0, 0.0),
            ('Si280',        'Silicon Sealant 280ml',        HardwareCategory.INSTALLATION, 'pcs', 0, 0.0),
            ('MaskTape',     'Masking Tape',                HardwareCategory.INSTALLATION, 'm',   0, 0.0),
            ('UPacker',      'Installation Packer',         HardwareCategory.INSTALLATION, 'pcs', 0, 0.0),
            ('PS1',          'Packing Shim 1mm',            HardwareCategory.INSTALLATION, 'pcs', 0, 0.0),
            ('PS3',          'Packing Shim 3mm',            HardwareCategory.INSTALLATION, 'pcs', 0, 0.0),
            ('PS5',          'Packing Shim 5mm',            HardwareCategory.INSTALLATION, 'pcs', 0, 0.0),
        ]
        for sn, name, cat, unit, cost, wt in hw_data:
            Hardware.objects.get_or_create(
                stock_no=sn,
                defaults=dict(name=name, category=cat, unit=unit,
                              unit_cost=cost, weight_per_unit=wt,
                              brand=brands['Generic'])
            )

        self.stdout.write('Seeding hardware rules for SY01...')
        hw_rules = [
            ('BUTTHNGWHT',   'n_panels * 2'),
            ('HNDL1-L-WHT',  '1'),
            ('HNDL1-R-WHT',  '1'),
            ('Shootbolt1',   '1'),
            ('ShootboltKeep','1'),
            ('CasementWedge','n_panels'),
            ('CockspurWedge','n_panels'),
            ('CBLOCK01',     '4 * n_panels'),
            ('GBRIDGE',      '6 * n_panels'),
        ]
        from catalog.models import SystemHardwareRule
        for sn, qty_f in hw_rules:
            hw = Hardware.objects.filter(stock_no=sn).first()
            if hw:
                SystemHardwareRule.objects.get_or_create(
                    system=sy01, hardware=hw,
                    defaults={'quantity_formula': qty_f}
                )

        self.stdout.write('Seeding hardware rules for AL01 and UP01...')
        mesh_hw_rules = [
            ('MSH-FIBER', '(W * H) / 1000000'),
            ('MSH-SPLINE', '((W + H) * 2) / 1000'),
        ]
        for sy in [systems['AL01'], systems['UP01']]:
            for sn, qty_f in hw_rules:
                hw = Hardware.objects.filter(stock_no=sn).first()
                if hw:
                    SystemHardwareRule.objects.get_or_create(
                        system=sy, hardware=hw,
                        defaults={'quantity_formula': qty_f}
                    )
            for sn, qty_f in mesh_hw_rules:
                hw = Hardware.objects.filter(stock_no=sn).first()
                if hw:
                    SystemHardwareRule.objects.get_or_create(
                        system=sy, hardware=hw,
                        defaults={'quantity_formula': qty_f}
                    )

        self.stdout.write('Seeding company settings...')
        CompanySettings.objects.get_or_create(
            pk=1,
            defaults=dict(
                company_name='CutFlow Fenestration Pvt. Ltd.',
                address_line1='D-27, Reva Park',
                address_line2='Near Exponential Complex, Old Padra Road',
                city='Vadodara',
                state='Gujarat',
                pincode='390 015',
                phone='+91 7575 009691',
                email='info@cutflow.com',
                sgst_rate=9,
                cgst_rate=9,
                igst_rate=18,
                quotation_validity_days=30,
                default_bar_length_mm=6000,
                kerf_mm=5,
                end_waste_mm=10,
                min_reusable_offcut_mm=300,
                default_payment_terms='50% advance with order.\n25% before dispatch.\n25% on delivery.',
                quotation_terms=(
                    'All aluminium profiles are powder-coated unless otherwise specified.\n'
                    'Glass is a bought-out item; actual glass sizes may vary ±2mm.\n'
                    'This quotation is valid for 30 days from the above date.\n'
                    'Prices are exclusive of GST unless specified.\n'
                    'Delivery timeline: 4-6 weeks from order confirmation & advance.'
                )
            )
        )

        self.stdout.write(self.style.SUCCESS(
            '\n✓ Initial data seeded successfully.\n'
            'Next steps:\n'
            '  1. Create superuser: python manage.py createsuperuser\n'
            '  2. Run server: python manage.py runserver\n'
            '  3. Login at /accounts/login/\n'
            '  4. Add profile formulas at /admin/catalog/profileformula/\n'
        ))
