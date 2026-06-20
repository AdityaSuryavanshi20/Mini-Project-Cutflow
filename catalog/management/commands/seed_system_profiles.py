from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = 'Seed core system profile mappings, profile formulas, and hardware rules for production.'

    @transaction.atomic
    def handle(self, *args, **options):
        from catalog.models import (
            Brand, System, SystemCategory,
            Profile, ProfileCategory, SystemProfile, ProfileFormula,
            Hardware, HardwareCategory, SystemHardwareRule,
        )

        brand, _ = Brand.objects.get_or_create(
            name='CutFlow Standard',
            defaults={'description': 'Default system brand', 'is_active': True}
        )

        systems_data = [
            ('SY01', 'Hinge Int Glz System', SystemCategory.CASEMENT),
            ('SY02', 'Sliding 2-Track System', SystemCategory.SLIDING),
            ('SY03', 'Sliding 3-Track System', SystemCategory.SLIDING),
        ]
        systems = {}
        for code, name, category in systems_data:
            system, _ = System.objects.get_or_create(
                code=code,
                defaults={'name': name, 'category': category, 'brand': brand, 'is_active': True}
            )
            systems[code] = system

        profiles_data = [
            ('OF004W', 'Outer Frame', ProfileCategory.OUTER_FRAME, 6000, 1.2, 320, 0, 0, 0, 0),
            ('TS001W', 'T Sash', ProfileCategory.SASH, 6000, 0.9, 240, 3, 3, 3, 3),
            ('TM001W', 'T Transom', ProfileCategory.MULLION, 6000, 0.85, 220, 0, 0, 0, 0),
            ('ZM001W', 'Z Mullion', ProfileCategory.MULLION, 6000, 0.88, 230, 0, 0, 0, 0),
            ('WM_GB15W', 'Glass Bead 15mm', ProfileCategory.BEAD, 6000, 0.12, 35, 0, 0, 0, 0),
            ('WM_GB17W', 'Glass Bead 17mm', ProfileCategory.BEAD, 6000, 0.14, 38, 0, 0, 0, 0),
            ('SOF01W', '2T Slider Frame', ProfileCategory.SLIDER_FRAME, 6000, 1.1, 300, 0, 0, 0, 0),
            ('SS001W', 'Slider Sash', ProfileCategory.SLIDER_SASH, 6000, 0.95, 255, 3, 3, 3, 3),
            ('INTL01W', 'Interlock Profile', ProfileCategory.MULLION, 6000, 0.87, 225, 0, 0, 0, 0),
            ('TRK001W', 'Sliding Track', ProfileCategory.SLIDER_FRAME, 6000, 1.3, 330, 0, 0, 0, 0),
        ]
        profiles = {}
        for stock_no, name, category, bar_len, wt, cost, ol, orr, ot, ob in profiles_data:
            profile, _ = Profile.objects.get_or_create(
                stock_no=stock_no,
                defaults={
                    'name': name,
                    'category': category,
                    'brand': brand,
                    'standard_bar_length': bar_len,
                    'weight_per_meter': wt,
                    'cost_per_meter': cost,
                    'offset_left': ol,
                    'offset_right': orr,
                    'offset_top': ot,
                    'offset_bottom': ob,
                    'default_left_angle': 90,
                    'default_right_angle': 90,
                    'is_active': True,
                }
            )
            profiles[stock_no] = profile

        system_profile_data = [
            ('SY01', 'OF004W', 'outer_frame_top', 10),
            ('SY01', 'OF004W', 'outer_frame_bottom', 20),
            ('SY01', 'OF004W', 'outer_frame_left', 30),
            ('SY01', 'OF004W', 'outer_frame_right', 40),
            ('SY01', 'TS001W', 'shutter_vertical', 50),
            ('SY01', 'TS001W', 'shutter_horizontal', 60),
            ('SY01', 'INTL01W', 'interlock', 70),
            ('SY01', 'TM001W', 'mullion', 80),
            ('SY01', 'WM_GB15W', 'bead_horizontal', 90),
            ('SY01', 'WM_GB15W', 'bead_vertical', 100),
            ('SY01', 'TRK001W', 'track', 110),
            ('SY02', 'SOF01W', 'outer_frame_top', 10),
            ('SY02', 'SOF01W', 'outer_frame_bottom', 20),
            ('SY02', 'SOF01W', 'outer_frame_left', 30),
            ('SY02', 'SOF01W', 'outer_frame_right', 40),
            ('SY02', 'SS001W', 'shutter_vertical', 50),
            ('SY02', 'SS001W', 'shutter_horizontal', 60),
            ('SY02', 'INTL01W', 'interlock', 70),
            ('SY02', 'ZM001W', 'mullion', 80),
            ('SY02', 'WM_GB17W', 'bead_horizontal', 90),
            ('SY02', 'WM_GB17W', 'bead_vertical', 100),
            ('SY02', 'TRK001W', 'track', 110),
            ('SY03', 'SOF01W', 'outer_frame_top', 10),
            ('SY03', 'SOF01W', 'outer_frame_bottom', 20),
            ('SY03', 'SOF01W', 'outer_frame_left', 30),
            ('SY03', 'SOF01W', 'outer_frame_right', 40),
            ('SY03', 'SS001W', 'shutter_vertical', 50),
            ('SY03', 'SS001W', 'shutter_horizontal', 60),
            ('SY03', 'INTL01W', 'interlock', 70),
            ('SY03', 'ZM001W', 'mullion', 80),
            ('SY03', 'WM_GB17W', 'bead_horizontal', 90),
            ('SY03', 'WM_GB17W', 'bead_vertical', 100),
            ('SY03', 'TRK001W', 'track', 110),
        ]
        for system_code, profile_code, role, sort_order in system_profile_data:
            system = systems[system_code]
            profile = profiles[profile_code]
            SystemProfile.objects.get_or_create(
                system=system,
                profile=profile,
                role=role,
                defaults={'sort_order': sort_order, 'is_required': True, 'is_active': True}
            )

        formulas_data = [
            ('SY01', 'OF004W', 'outer_top', 'W - offset_l - offset_r', '1', 90, 90),
            ('SY01', 'OF004W', 'outer_bottom', 'W - offset_l - offset_r', '1', 90, 90),
            ('SY01', 'OF004W', 'outer_left', 'H - offset_t - offset_b', '1', 90, 90),
            ('SY01', 'OF004W', 'outer_right', 'H - offset_t - offset_b', '1', 90, 90),
            ('SY01', 'TS001W', 'sash_width', 'n_panels', 'W - offset_l - offset_r', 90, 90),
            ('SY01', 'TS001W', 'sash_height', 'H - offset_t - offset_b', 'n_panels', 90, 90),
            ('SY01', 'INTL01W', 'interlock_length', 'n_panels - 1', 'H - offset_t - offset_b', 90, 90),
            ('SY01', 'TM001W', 'mullion_length', 'n_panels - 1', 'H - offset_t - offset_b', 90, 90),
            ('SY01', 'WM_GB15W', 'bead_horizontal', '2 * n_panels', 'W - 20', 90, 90),
            ('SY01', 'WM_GB15W', 'bead_vertical', '2 * n_panels', 'H - 20', 90, 90),
            ('SY01', 'TRK001W', 'track_length', '1', 'W', 90, 90),
            ('SY02', 'SOF01W', 'outer_top', '1', 'W', 90, 90),
            ('SY02', 'SOF01W', 'outer_bottom', '1', 'W', 90, 90),
            ('SY02', 'SOF01W', 'outer_left', '1', 'H', 90, 90),
            ('SY02', 'SOF01W', 'outer_right', '1', 'H', 90, 90),
            ('SY02', 'SS001W', 'sash_width', 'n_panels', 'round((W / n_panels) - 35, 2)', 90, 90),
            ('SY02', 'SS001W', 'sash_height', '2 * n_panels', 'H - offset_t - offset_b', 90, 90),
            ('SY02', 'INTL01W', 'interlock_length', 'n_panels - 1', 'H - offset_t - offset_b', 90, 90),
            ('SY02', 'ZM001W', 'mullion_length', 'n_panels - 1', 'H - offset_t - offset_b', 90, 90),
            ('SY02', 'WM_GB17W', 'bead_horizontal', '2 * n_panels', 'W - 20', 90, 90),
            ('SY02', 'WM_GB17W', 'bead_vertical', '2 * n_panels', 'H - 20', 90, 90),
            ('SY02', 'TRK001W', 'track_length', '1', 'W', 90, 90),
            ('SY03', 'SOF01W', 'outer_top', '1', 'W', 90, 90),
            ('SY03', 'SOF01W', 'outer_bottom', '1', 'W', 90, 90),
            ('SY03', 'SOF01W', 'outer_left', '1', 'H', 90, 90),
            ('SY03', 'SOF01W', 'outer_right', '1', 'H', 90, 90),
            ('SY03', 'SS001W', 'sash_width', 'n_panels', 'round((W / n_panels) - 35, 2)', 90, 90),
            ('SY03', 'SS001W', 'sash_height', '2 * n_panels', 'H - offset_t - offset_b', 90, 90),
            ('SY03', 'INTL01W', 'interlock_length', 'n_panels - 1', 'H - offset_t - offset_b', 90, 90),
            ('SY03', 'ZM001W', 'mullion_length', 'n_panels - 1', 'H - offset_t - offset_b', 90, 90),
            ('SY03', 'WM_GB17W', 'bead_horizontal', '2 * n_panels', 'W - 20', 90, 90),
            ('SY03', 'WM_GB17W', 'bead_vertical', '2 * n_panels', 'H - 20', 90, 90),
            ('SY03', 'TRK001W', 'track_length', '1', 'W', 90, 90),
        ]
        for system_code, profile_code, position, qty_formula, formula, la, ra in formulas_data:
            system = systems[system_code]
            profile = profiles[profile_code]
            system_profile = SystemProfile.objects.filter(system=system, profile=profile, role__in=['outer_frame_top', 'outer_frame_bottom', 'outer_frame_left', 'outer_frame_right', 'shutter_vertical', 'shutter_horizontal', 'interlock', 'mullion', 'track', 'bead_horizontal', 'bead_vertical']).filter(profile=profile).first()
            ProfileFormula.objects.get_or_create(
                profile=profile,
                system=system,
                position=position,
                defaults={
                    'system_profile': system_profile,
                    'formula': formula,
                    'quantity_formula': qty_formula,
                    'cut_angle_left': la,
                    'cut_angle_right': ra,
                    'is_active': True,
                }
            )

        hardware_data = [
            ('ROLLER1', 'Slider Roller 1', HardwareCategory.ROLLER, 'pcs', 150, 0.05),
            ('SLHNDL1AWHT', 'Slider Handle A White', HardwareCategory.HANDLE, 'pcs', 110, 0.65),
            ('SLESG1SS6', '7.5 SLD SSEspag 1200', HardwareCategory.LOCK, 'pcs', 277, 0.57),
            ('BUTTHNGWHT', 'Butt Hinge (2D) White', HardwareCategory.HINGE, 'pcs', 140, 0.65),
            ('HNDL1-L-WHT', 'Cockspur Handle LK L White', HardwareCategory.HANDLE, 'pcs', 125, 0.40),
            ('Shootbolt1', 'FR Window Shootbolt', HardwareCategory.LOCK, 'pcs', 164, 0.39),
            ('WM_SCREW2', 'Reinforcement Screw', HardwareCategory.SCREW, 'pcs', 1, 0.0),
            ('GASKET-SL', 'Sliding Gasket', HardwareCategory.GASKET, 'm', 25, 0.01),
            ('GASKET-HN', 'Hinge Gasket', HardwareCategory.GASKET, 'm', 30, 0.01),
        ]
        hardware = {}
        for stock_no, name, category, unit, cost, wt in hardware_data:
            item, _ = Hardware.objects.get_or_create(
                stock_no=stock_no,
                defaults={
                    'name': name,
                    'category': category,
                    'unit': unit,
                    'unit_cost': cost,
                    'weight_per_unit': wt,
                    'brand': brand,
                    'is_active': True,
                }
            )
            hardware[stock_no] = item

        hardware_rule_data = [
            ('SY01', 'BUTTHNGWHT', 'n_panels * 3', 'Hinge pack'),
            ('SY01', 'HNDL1-L-WHT', '1', 'Handle set'),
            ('SY01', 'Shootbolt1', '1', 'Shootbolt package'),
            ('SY01', 'WM_SCREW2', '12 * n_panels', 'Screws for anchors'),
            ('SY01', 'GASKET-HN', 'n_panels * 4', 'Perimeter gasket'),
            ('SY02', 'ROLLER1', 'n_panels * 2', 'Rollers for sliding sash'),
            ('SY02', 'SLHNDL1AWHT', 'n_panels', 'Slider handle'),
            ('SY02', 'SLESG1SS6', '1', 'Espag lock per unit'),
            ('SY02', 'WM_SCREW2', '10 * n_panels', 'Fixing screws'),
            ('SY02', 'GASKET-SL', 'n_panels * 4', 'Sliding gasket'),
            ('SY03', 'ROLLER1', 'n_panels * 2', 'Rollers for sliding sash'),
            ('SY03', 'SLHNDL1AWHT', 'n_panels', 'Slider handle'),
            ('SY03', 'SLESG1SS6', '1', 'Espag lock per unit'),
            ('SY03', 'WM_SCREW2', '10 * n_panels', 'Fixing screws'),
            ('SY03', 'GASKET-SL', 'n_panels * 4', 'Sliding gasket'),
        ]
        for system_code, hw_code, qty_formula, notes in hardware_rule_data:
            system = systems[system_code]
            item = hardware[hw_code]
            SystemHardwareRule.objects.get_or_create(
                system=system,
                hardware=item,
                defaults={'quantity_formula': qty_formula, 'notes': notes, 'is_active': True}
            )

        self.stdout.write(self.style.SUCCESS('Seeded system profiles, profile formulas, and hardware rules.'))
