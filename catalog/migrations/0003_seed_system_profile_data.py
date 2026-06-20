from django.db import migrations


def seed_system_profile_data(apps, schema_editor):
    Brand = apps.get_model('catalog', 'Brand')
    System = apps.get_model('catalog', 'System')
    Profile = apps.get_model('catalog', 'Profile')
    SystemProfile = apps.get_model('catalog', 'SystemProfile')
    ProfileFormula = apps.get_model('catalog', 'ProfileFormula')
    Hardware = apps.get_model('catalog', 'Hardware')
    SystemHardwareRule = apps.get_model('catalog', 'SystemHardwareRule')

    brand, _ = Brand.objects.get_or_create(name='CutFlow Standard', defaults={'description': 'Default system brand', 'is_active': True})

    systems_data = [
        ('SY01', 'Hinge Int Glz System', 'casement'),
        ('SY02', 'Sliding 2-Track System', 'sliding'),
        ('SY03', 'Sliding 3-Track System', 'sliding'),
    ]
    systems = {}
    for code, name, category in systems_data:
        system, _ = System.objects.get_or_create(
            code=code,
            defaults={'name': name, 'category': category, 'brand': brand, 'is_active': True}
        )
        systems[code] = system

    profiles_data = [
        ('OF004W', 'Outer Frame', 'outer_frame', 6000, 1.2, 320, 0, 0, 0, 0),
        ('TS001W', 'T Sash', 'sash', 6000, 0.9, 240, 3, 3, 3, 3),
        ('TM001W', 'T Transom', 'mullion', 6000, 0.85, 220, 0, 0, 0, 0),
        ('ZM001W', 'Z Mullion', 'mullion', 6000, 0.88, 230, 0, 0, 0, 0),
        ('WM_GB15W', 'Glass Bead 15mm', 'bead', 6000, 0.12, 35, 0, 0, 0, 0),
        ('WM_GB17W', 'Glass Bead 17mm', 'bead', 6000, 0.14, 38, 0, 0, 0, 0),
        ('SOF01W', '2T Slider Frame', 'slider_frame', 6000, 1.1, 300, 0, 0, 0, 0),
        ('SS001W', 'Slider Sash', 'slider_sash', 6000, 0.95, 255, 3, 3, 3, 3),
        ('INTL01W', 'Interlock Profile', 'mullion', 6000, 0.87, 225, 0, 0, 0, 0),
        ('TRK001W', 'Sliding Track', 'slider_frame', 6000, 1.3, 330, 0, 0, 0, 0),
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

    profile_link_data = [
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
    for system_code, profile_code, role, sort_order in profile_link_data:
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
        ('SY01', 'TS001W', 'sash_width', 'W - offset_l - offset_r', 'n_panels', 90, 90),
        ('SY01', 'TS001W', 'sash_height', 'H - offset_t - offset_b', 'n_panels', 90, 90),
        ('SY01', 'INTL01W', 'interlock_length', 'H - offset_t - offset_b', 'n_panels - 1', 90, 90),
        ('SY01', 'TM001W', 'mullion_length', 'H - offset_t - offset_b', 'n_panels - 1', 90, 90),
        ('SY01', 'WM_GB15W', 'bead_horizontal', 'W - 20', '2 * n_panels', 90, 90),
        ('SY01', 'WM_GB15W', 'bead_vertical', 'H - 20', '2 * n_panels', 90, 90),
        ('SY01', 'TRK001W', 'track_length', 'W', '1', 90, 90),
        ('SY02', 'SOF01W', 'outer_top', 'W', '1', 90, 90),
        ('SY02', 'SOF01W', 'outer_bottom', 'W', '1', 90, 90),
        ('SY02', 'SOF01W', 'outer_left', 'H', '1', 90, 90),
        ('SY02', 'SOF01W', 'outer_right', 'H', '1', 90, 90),
        ('SY02', 'SS001W', 'sash_width', 'round((W / n_panels) - 35, 2)', 'n_panels', 90, 90),
        ('SY02', 'SS001W', 'sash_height', 'H - offset_t - offset_b', '2 * n_panels', 90, 90),
        ('SY02', 'INTL01W', 'interlock_length', 'H - offset_t - offset_b', 'n_panels - 1', 90, 90),
        ('SY02', 'ZM001W', 'mullion_length', 'H - offset_t - offset_b', 'n_panels - 1', 90, 90),
        ('SY02', 'WM_GB17W', 'bead_horizontal', 'W - 20', '2 * n_panels', 90, 90),
        ('SY02', 'WM_GB17W', 'bead_vertical', 'H - 20', '2 * n_panels', 90, 90),
        ('SY02', 'TRK001W', 'track_length', 'W', '1', 90, 90),
        ('SY03', 'SOF01W', 'outer_top', 'W', '1', 90, 90),
        ('SY03', 'SOF01W', 'outer_bottom', 'W', '1', 90, 90),
        ('SY03', 'SOF01W', 'outer_left', 'H', '1', 90, 90),
        ('SY03', 'SOF01W', 'outer_right', 'H', '1', 90, 90),
        ('SY03', 'SS001W', 'sash_width', 'round((W / n_panels) - 35, 2)', 'n_panels', 90, 90),
        ('SY03', 'SS001W', 'sash_height', 'H - offset_t - offset_b', '2 * n_panels', 90, 90),
        ('SY03', 'INTL01W', 'interlock_length', 'H - offset_t - offset_b', 'n_panels - 1', 90, 90),
        ('SY03', 'ZM001W', 'mullion_length', 'H - offset_t - offset_b', 'n_panels - 1', 90, 90),
        ('SY03', 'WM_GB17W', 'bead_horizontal', 'W - 20', '2 * n_panels', 90, 90),
        ('SY03', 'WM_GB17W', 'bead_vertical', 'H - 20', '2 * n_panels', 90, 90),
        ('SY03', 'TRK001W', 'track_length', 'W', '1', 90, 90),
    ]
    for system_code, profile_code, position, formula, qty_formula, la, ra in formulas_data:
        system = systems[system_code]
        profile = profiles[profile_code]
        system_profile = SystemProfile.objects.filter(system=system, profile=profile).first()
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
        ('ROLLER1', 'Slider Roller 1', 'roller', 'pcs', 150, 0.05),
        ('SLHNDL1AWHT', 'Slider Handle A White', 'handle', 'pcs', 110, 0.65),
        ('SLESG1SS6', '7.5 SLD SSEspag 1200', 'lock', 'pcs', 277, 0.57),
        ('BUTTHNGWHT', 'Butt Hinge (2D) White', 'hinge', 'pcs', 140, 0.65),
        ('HNDL1-L-WHT', 'Cockspur Handle LK L White', 'handle', 'pcs', 125, 0.40),
        ('Shootbolt1', 'FR Window Shootbolt', 'lock', 'pcs', 164, 0.39),
        ('WM_SCREW2', 'Reinforcement Screw', 'screw', 'pcs', 1, 0.0),
        ('GASKET-SL', 'Sliding Gasket', 'gasket', 'm', 25, 0.01),
        ('GASKET-HN', 'Hinge Gasket', 'gasket', 'm', 30, 0.01),
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


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0002_alter_profileformula_options_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_system_profile_data, migrations.RunPython.noop),
    ]
