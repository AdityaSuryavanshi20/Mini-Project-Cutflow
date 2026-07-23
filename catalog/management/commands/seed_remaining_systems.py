"""
CutFlow - Seed data for systems that exist in the `System` dropdown but were
never given profiles / cut formulas / hardware rules:

    SY04  Fixed Frame System
    SY05  Tilt & Turn System
    SY06  Super System Door
    SY07  Sliding Door System
    SY08  Louvre System

Without ProfileFormula rows, `production/services.compute_cuts_for_item()`
returns zero cut requests and `run_optimization()` raises
"No production cuts available for optimization" - which is why quotations/
production jobs for these systems silently fail while SY01, SY02, SY03,
AL01 and UP01 (which do have formulas from seed_system_profiles.py /
seed_data.py) work fine.

This command only INSERTS missing rows (get_or_create), so it is safe to
run on a database that already has SY01-03/AL01/UP01 seeded.

Run after `python manage.py migrate` and after `seed_data`:
    python manage.py seed_remaining_systems

The cut formulas below are reasonable starting points that mirror the
patterns already used for SY01 (hinge casement) and SY02/SY03 (sliding).
They should be reviewed against your actual profile catalogue/spec sheets
in /admin/catalog/profileformula/ and adjusted (offsets, deduction
constants, hardware quantities) to match real fabrication tolerances.
"""
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = 'Seed profiles, cut formulas, and hardware rules for SY04-SY08 (Fixed Frame, Tilt & Turn, Super System Door, Sliding Door, Louvre)'

    @transaction.atomic
    def handle(self, *args, **options):
        from catalog.models import (
            Brand, System, SystemCategory, SystemMaterial,
            Profile, ProfileCategory, SystemProfile, SystemProfileRole,
            ProfileFormula, Hardware, HardwareCategory, SystemHardwareRule,
        )

        brand, _ = Brand.objects.get_or_create(
            name='CutFlow Standard',
            defaults={'description': 'Default system brand', 'is_active': True}
        )

        # ------------------------------------------------------------------
        # Make sure SY04-SY08 exist (in case seed_data was never run either).
        # ------------------------------------------------------------------
        systems_data = [
            ('SY04', 'Fixed Frame System', SystemCategory.FIXED),
            ('SY05', 'Tilt & Turn System', SystemCategory.CASEMENT),
            ('SY06', 'Super System Door', SystemCategory.DOOR_SWING),
            ('SY07', 'Sliding Door System', SystemCategory.DOOR_SLIDING),
            ('SY08', 'Louvre System', SystemCategory.LOUVER),
        ]
        systems = {}
        for code, name, category in systems_data:
            system, created = System.objects.get_or_create(
                code=code,
                defaults={'name': name, 'category': category, 'material': SystemMaterial.ALUMINIUM,
                          'brand': brand, 'is_active': True}
            )
            if not created and system.material != SystemMaterial.ALUMINIUM:
                system.material = SystemMaterial.ALUMINIUM
                system.save(update_fields=['material'])
            systems[code] = system

        # ------------------------------------------------------------------
        # New profiles needed by these systems (reusing existing bead /
        # interlock / track / screw / gasket stock where the part is
        # genuinely identical across systems).
        # ------------------------------------------------------------------
        profiles_data = [
            # stock_no,   name,                        category,                bar_len, wt,   cost, ol, or, ot, ob, la, ra
            ('FX-OF01',  'Fixed Frame Outer',           ProfileCategory.OUTER_FRAME,  6000, 1.15, 300, 0, 0, 0, 0, 90, 90),
            ('DR-OF01',  'Door Outer Frame (Heavy)',    ProfileCategory.OUTER_FRAME,  6000, 1.9,  480, 0, 0, 0, 0, 90, 90),
            ('DR-SH01',  'Door Shutter/Sash',           ProfileCategory.SASH,         6000, 1.7,  430, 5, 5, 5, 5, 90, 90),
            ('DR-TH01',  'Door Threshold',              ProfileCategory.ANCILLARY,    6000, 1.4,  360, 0, 0, 0, 0, 90, 90),
            ('SDF01W',   'Sliding Door Frame (Heavy)',  ProfileCategory.SLIDER_FRAME, 6000, 1.6,  420, 0, 0, 0, 0, 90, 90),
            ('SDS01W',   'Sliding Door Sash (Heavy)',   ProfileCategory.SLIDER_SASH,  6000, 1.35, 360, 3, 3, 3, 3, 90, 90),
            ('LV-OF01',  'Louvre Outer Frame',          ProfileCategory.OUTER_FRAME,  6000, 1.2,  320, 0, 0, 0, 0, 90, 90),
            ('LV-BLD01', 'Louvre Blade',                ProfileCategory.ANCILLARY,    6000, 0.55, 150, 0, 0, 0, 0, 90, 90),
        ]
        profiles = {}
        for stock_no, name, category, bar_len, wt, cost, ol, orr, ot, ob, la, ra in profiles_data:
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
                    'default_left_angle': la,
                    'default_right_angle': ra,
                    'is_active': True,
                }
            )
            profiles[stock_no] = profile

        # Pull in existing shared profiles (created by seed_system_profiles /
        # seed_data). If they don't exist yet, create minimal versions so
        # this command works standalone too.
        shared_defaults = {
            'TM001W': dict(name='T Transom', category=ProfileCategory.MULLION, bar_len=6000, wt=0.85, cost=220, ol=0, orr=0, ot=0, ob=0, la=90, ra=90),
            'INTL01W': dict(name='Interlock Profile', category=ProfileCategory.MULLION, bar_len=6000, wt=0.87, cost=225, ol=0, orr=0, ot=0, ob=0, la=90, ra=90),
            'TRK001W': dict(name='Sliding Track', category=ProfileCategory.SLIDER_FRAME, bar_len=6000, wt=1.3, cost=330, ol=0, orr=0, ot=0, ob=0, la=90, ra=90),
            'WM_GB17W': dict(name='Glass Bead 17mm', category=ProfileCategory.BEAD, bar_len=6000, wt=0.14, cost=38, ol=0, orr=0, ot=0, ob=0, la=90, ra=90),
            'OF004W': dict(name='Outer Frame', category=ProfileCategory.OUTER_FRAME, bar_len=6000, wt=1.2, cost=320, ol=0, orr=0, ot=0, ob=0, la=90, ra=90),
            'TS001W': dict(name='T Sash', category=ProfileCategory.SASH, bar_len=6000, wt=0.9, cost=240, ol=3, orr=3, ot=3, ob=3, la=90, ra=90),
        }
        for stock_no, d in shared_defaults.items():
            profile, _ = Profile.objects.get_or_create(
                stock_no=stock_no,
                defaults={
                    'name': d['name'], 'category': d['category'], 'brand': brand,
                    'standard_bar_length': d['bar_len'], 'weight_per_meter': d['wt'],
                    'cost_per_meter': d['cost'], 'offset_left': d['ol'], 'offset_right': d['orr'],
                    'offset_top': d['ot'], 'offset_bottom': d['ob'],
                    'default_left_angle': d['la'], 'default_right_angle': d['ra'], 'is_active': True,
                }
            )
            profiles[stock_no] = profile

        # ------------------------------------------------------------------
        # SystemProfile role mappings (profile <-> role per system)
        # ------------------------------------------------------------------
        system_profile_data = [
            # SY04 - Fixed Frame
            ('SY04', 'FX-OF01', SystemProfileRole.OUTER_FRAME_TOP, 10),
            ('SY04', 'FX-OF01', SystemProfileRole.OUTER_FRAME_BOTTOM, 20),
            ('SY04', 'FX-OF01', SystemProfileRole.OUTER_FRAME_LEFT, 30),
            ('SY04', 'FX-OF01', SystemProfileRole.OUTER_FRAME_RIGHT, 40),
            ('SY04', 'TM001W', SystemProfileRole.MULLION, 50),
            ('SY04', 'WM_GB17W', SystemProfileRole.BEAD_HORIZONTAL, 60),
            ('SY04', 'WM_GB17W', SystemProfileRole.BEAD_VERTICAL, 70),
            # SY05 - Tilt & Turn (same skeleton as SY01 hinge casement)
            ('SY05', 'OF004W', SystemProfileRole.OUTER_FRAME_TOP, 10),
            ('SY05', 'OF004W', SystemProfileRole.OUTER_FRAME_BOTTOM, 20),
            ('SY05', 'OF004W', SystemProfileRole.OUTER_FRAME_LEFT, 30),
            ('SY05', 'OF004W', SystemProfileRole.OUTER_FRAME_RIGHT, 40),
            ('SY05', 'TS001W', SystemProfileRole.SHUTTER_VERTICAL, 50),
            ('SY05', 'TS001W', SystemProfileRole.SHUTTER_HORIZONTAL, 60),
            ('SY05', 'INTL01W', SystemProfileRole.INTERLOCK, 70),
            ('SY05', 'TM001W', SystemProfileRole.MULLION, 80),
            ('SY05', 'WM_GB17W', SystemProfileRole.BEAD_HORIZONTAL, 90),
            ('SY05', 'WM_GB17W', SystemProfileRole.BEAD_VERTICAL, 100),
            # SY06 - Super System Door
            ('SY06', 'DR-OF01', SystemProfileRole.OUTER_FRAME_TOP, 10),
            ('SY06', 'DR-TH01', SystemProfileRole.OUTER_FRAME_BOTTOM, 20),
            ('SY06', 'DR-OF01', SystemProfileRole.OUTER_FRAME_LEFT, 30),
            ('SY06', 'DR-OF01', SystemProfileRole.OUTER_FRAME_RIGHT, 40),
            ('SY06', 'DR-SH01', SystemProfileRole.SHUTTER_VERTICAL, 50),
            ('SY06', 'DR-SH01', SystemProfileRole.SHUTTER_HORIZONTAL, 60),
            ('SY06', 'TM001W', SystemProfileRole.MULLION, 70),
            ('SY06', 'WM_GB17W', SystemProfileRole.BEAD_HORIZONTAL, 80),
            ('SY06', 'WM_GB17W', SystemProfileRole.BEAD_VERTICAL, 90),
            # SY07 - Sliding Door
            ('SY07', 'SDF01W', SystemProfileRole.OUTER_FRAME_TOP, 10),
            ('SY07', 'SDF01W', SystemProfileRole.OUTER_FRAME_BOTTOM, 20),
            ('SY07', 'SDF01W', SystemProfileRole.OUTER_FRAME_LEFT, 30),
            ('SY07', 'SDF01W', SystemProfileRole.OUTER_FRAME_RIGHT, 40),
            ('SY07', 'SDS01W', SystemProfileRole.SHUTTER_VERTICAL, 50),
            ('SY07', 'SDS01W', SystemProfileRole.SHUTTER_HORIZONTAL, 60),
            ('SY07', 'INTL01W', SystemProfileRole.INTERLOCK, 70),
            ('SY07', 'WM_GB17W', SystemProfileRole.BEAD_HORIZONTAL, 80),
            ('SY07', 'WM_GB17W', SystemProfileRole.BEAD_VERTICAL, 90),
            ('SY07', 'TRK001W', SystemProfileRole.TRACK, 100),
            # SY08 - Louvre
            ('SY08', 'LV-OF01', SystemProfileRole.OUTER_FRAME_TOP, 10),
            ('SY08', 'LV-OF01', SystemProfileRole.OUTER_FRAME_BOTTOM, 20),
            ('SY08', 'LV-OF01', SystemProfileRole.OUTER_FRAME_LEFT, 30),
            ('SY08', 'LV-OF01', SystemProfileRole.OUTER_FRAME_RIGHT, 40),
            ('SY08', 'LV-BLD01', SystemProfileRole.ANCILLARY, 50),
        ]
        system_profiles = {}
        for system_code, profile_code, role, sort_order in system_profile_data:
            sp, _ = SystemProfile.objects.get_or_create(
                system=systems[system_code],
                profile=profiles[profile_code],
                role=role,
                defaults={'sort_order': sort_order, 'is_required': True, 'is_active': True}
            )
            system_profiles[(system_code, profile_code, role)] = sp

        # ------------------------------------------------------------------
        # Cut formulas. quantity_formula resolving to 0 (e.g. 'n_panels - 1'
        # on a single-panel unit) makes compute_cuts_for_item() skip that
        # row automatically - same pattern already used by SY01/SY02/SY03 -
        # so a single-light Fixed/Tilt&Turn/Door unit simply omits the
        # mullion/interlock cut without erroring.
        # ------------------------------------------------------------------
        formulas_data = [
            # system, profile, position, quantity_formula, formula, l_angle, r_angle, sp_key
            # -- SY04 Fixed Frame --
            ('SY04', 'FX-OF01', 'outer_top', '1', 'W', 90, 90, ('SY04', 'FX-OF01', SystemProfileRole.OUTER_FRAME_TOP)),
            ('SY04', 'FX-OF01', 'outer_bottom', '1', 'W', 90, 90, ('SY04', 'FX-OF01', SystemProfileRole.OUTER_FRAME_BOTTOM)),
            ('SY04', 'FX-OF01', 'outer_left', '1', 'H', 90, 90, ('SY04', 'FX-OF01', SystemProfileRole.OUTER_FRAME_LEFT)),
            ('SY04', 'FX-OF01', 'outer_right', '1', 'H', 90, 90, ('SY04', 'FX-OF01', SystemProfileRole.OUTER_FRAME_RIGHT)),
            ('SY04', 'TM001W', 'mullion_length', 'n_panels - 1', 'H', 90, 90, ('SY04', 'TM001W', SystemProfileRole.MULLION)),
            ('SY04', 'WM_GB17W', 'bead_horizontal', '2 * n_panels', 'W - 20', 90, 90, ('SY04', 'WM_GB17W', SystemProfileRole.BEAD_HORIZONTAL)),
            ('SY04', 'WM_GB17W', 'bead_vertical', '2 * n_panels', 'H - 20', 90, 90, ('SY04', 'WM_GB17W', SystemProfileRole.BEAD_VERTICAL)),

            # -- SY05 Tilt & Turn (same cut geometry as SY01) --
            ('SY05', 'OF004W', 'outer_top', '1', 'W - offset_l - offset_r', 90, 90, ('SY05', 'OF004W', SystemProfileRole.OUTER_FRAME_TOP)),
            ('SY05', 'OF004W', 'outer_bottom', '1', 'W - offset_l - offset_r', 90, 90, ('SY05', 'OF004W', SystemProfileRole.OUTER_FRAME_BOTTOM)),
            ('SY05', 'OF004W', 'outer_left', '1', 'H - offset_t - offset_b', 90, 90, ('SY05', 'OF004W', SystemProfileRole.OUTER_FRAME_LEFT)),
            ('SY05', 'OF004W', 'outer_right', '1', 'H - offset_t - offset_b', 90, 90, ('SY05', 'OF004W', SystemProfileRole.OUTER_FRAME_RIGHT)),
            ('SY05', 'TS001W', 'sash_width', 'n_panels', 'W - offset_l - offset_r', 90, 90, ('SY05', 'TS001W', SystemProfileRole.SHUTTER_HORIZONTAL)),
            ('SY05', 'TS001W', 'sash_height', 'n_panels', 'H - offset_t - offset_b', 90, 90, ('SY05', 'TS001W', SystemProfileRole.SHUTTER_VERTICAL)),
            ('SY05', 'INTL01W', 'interlock_length', 'n_panels - 1', 'H - offset_t - offset_b', 90, 90, ('SY05', 'INTL01W', SystemProfileRole.INTERLOCK)),
            ('SY05', 'TM001W', 'mullion_length', 'n_panels - 1', 'H - offset_t - offset_b', 90, 90, ('SY05', 'TM001W', SystemProfileRole.MULLION)),
            ('SY05', 'WM_GB17W', 'bead_horizontal', '2 * n_panels', 'W - 20', 90, 90, ('SY05', 'WM_GB17W', SystemProfileRole.BEAD_HORIZONTAL)),
            ('SY05', 'WM_GB17W', 'bead_vertical', '2 * n_panels', 'H - 20', 90, 90, ('SY05', 'WM_GB17W', SystemProfileRole.BEAD_VERTICAL)),

            # -- SY06 Super System Door --
            ('SY06', 'DR-OF01', 'frame_top', '1', 'W', 90, 90, ('SY06', 'DR-OF01', SystemProfileRole.OUTER_FRAME_TOP)),
            ('SY06', 'DR-TH01', 'threshold', '1', 'W', 90, 90, ('SY06', 'DR-TH01', SystemProfileRole.OUTER_FRAME_BOTTOM)),
            ('SY06', 'DR-OF01', 'frame_left', '1', 'H', 90, 90, ('SY06', 'DR-OF01', SystemProfileRole.OUTER_FRAME_LEFT)),
            ('SY06', 'DR-OF01', 'frame_right', '1', 'H', 90, 90, ('SY06', 'DR-OF01', SystemProfileRole.OUTER_FRAME_RIGHT)),
            ('SY06', 'DR-SH01', 'shutter_width', 'n_panels', 'W - offset_l - offset_r', 90, 90, ('SY06', 'DR-SH01', SystemProfileRole.SHUTTER_HORIZONTAL)),
            ('SY06', 'DR-SH01', 'shutter_height', 'n_panels', 'H - offset_t - offset_b', 90, 90, ('SY06', 'DR-SH01', SystemProfileRole.SHUTTER_VERTICAL)),
            ('SY06', 'TM001W', 'mullion_length', 'n_panels - 1', 'H - offset_t - offset_b', 90, 90, ('SY06', 'TM001W', SystemProfileRole.MULLION)),
            ('SY06', 'WM_GB17W', 'bead_horizontal', '2 * n_panels', 'W - 20', 90, 90, ('SY06', 'WM_GB17W', SystemProfileRole.BEAD_HORIZONTAL)),
            ('SY06', 'WM_GB17W', 'bead_vertical', '2 * n_panels', 'H - 20', 90, 90, ('SY06', 'WM_GB17W', SystemProfileRole.BEAD_VERTICAL)),

            # -- SY07 Sliding Door --
            ('SY07', 'SDF01W', 'outer_top', '1', 'W', 90, 90, ('SY07', 'SDF01W', SystemProfileRole.OUTER_FRAME_TOP)),
            ('SY07', 'SDF01W', 'outer_bottom', '1', 'W', 90, 90, ('SY07', 'SDF01W', SystemProfileRole.OUTER_FRAME_BOTTOM)),
            ('SY07', 'SDF01W', 'outer_left', '1', 'H', 90, 90, ('SY07', 'SDF01W', SystemProfileRole.OUTER_FRAME_LEFT)),
            ('SY07', 'SDF01W', 'outer_right', '1', 'H', 90, 90, ('SY07', 'SDF01W', SystemProfileRole.OUTER_FRAME_RIGHT)),
            ('SY07', 'SDS01W', 'sash_width', 'n_panels', 'round((W / n_panels) - 40, 2)', 90, 90, ('SY07', 'SDS01W', SystemProfileRole.SHUTTER_HORIZONTAL)),
            ('SY07', 'SDS01W', 'sash_height', '2 * n_panels', 'H - offset_t - offset_b', 90, 90, ('SY07', 'SDS01W', SystemProfileRole.SHUTTER_VERTICAL)),
            ('SY07', 'INTL01W', 'interlock_length', 'n_panels - 1', 'H - offset_t - offset_b', 90, 90, ('SY07', 'INTL01W', SystemProfileRole.INTERLOCK)),
            ('SY07', 'WM_GB17W', 'bead_horizontal', '2 * n_panels', 'W - 20', 90, 90, ('SY07', 'WM_GB17W', SystemProfileRole.BEAD_HORIZONTAL)),
            ('SY07', 'WM_GB17W', 'bead_vertical', '2 * n_panels', 'H - 20', 90, 90, ('SY07', 'WM_GB17W', SystemProfileRole.BEAD_VERTICAL)),
            ('SY07', 'TRK001W', 'track_length', '1', 'W', 90, 90, ('SY07', 'TRK001W', SystemProfileRole.TRACK)),

            # -- SY08 Louvre --
            ('SY08', 'LV-OF01', 'outer_top', '1', 'W', 90, 90, ('SY08', 'LV-OF01', SystemProfileRole.OUTER_FRAME_TOP)),
            ('SY08', 'LV-OF01', 'outer_bottom', '1', 'W', 90, 90, ('SY08', 'LV-OF01', SystemProfileRole.OUTER_FRAME_BOTTOM)),
            ('SY08', 'LV-OF01', 'outer_left', '1', 'H', 90, 90, ('SY08', 'LV-OF01', SystemProfileRole.OUTER_FRAME_LEFT)),
            ('SY08', 'LV-OF01', 'outer_right', '1', 'H', 90, 90, ('SY08', 'LV-OF01', SystemProfileRole.OUTER_FRAME_RIGHT)),
            # ~100mm blade pitch, 60mm top/bottom margin - tune to your blade spec
            ('SY08', 'LV-BLD01', 'blade_length', 'round((H - 60) / 100)', 'W - 30', 90, 90, ('SY08', 'LV-BLD01', SystemProfileRole.ANCILLARY)),
        ]
        for system_code, profile_code, position, qty_formula, formula, la, ra, sp_key in formulas_data:
            system = systems[system_code]
            profile = profiles[profile_code]
            ProfileFormula.objects.get_or_create(
                profile=profile,
                system=system,
                position=position,
                defaults={
                    'system_profile': system_profiles.get(sp_key),
                    'formula': formula,
                    'quantity_formula': qty_formula,
                    'cut_angle_left': la,
                    'cut_angle_right': ra,
                    'is_active': True,
                }
            )

        # ------------------------------------------------------------------
        # Hardware. Reuses stock already seeded by seed_data.py/
        # seed_system_profiles.py where the part is genuinely shared, adds
        # new stock items only where the system needs something distinct
        # (tilt & turn espagnolette, door lock/hinge set, louvre actuator).
        # ------------------------------------------------------------------
        new_hardware_data = [
            # stock_no,      name,                              category,                    unit, cost, wt
            ('TTESPAG1',    'Tilt & Turn Espagnolette 1600mm',  HardwareCategory.LOCK,        'pcs', 450, 1.10),
            ('TTHNDL1WHT',  'Tilt & Turn Handle White',         HardwareCategory.HANDLE,      'pcs', 180, 0.45),
            ('TTHINGE1',    'Tilt & Turn Corner Hinge Set',     HardwareCategory.HINGE,       'pcs', 320, 0.90),
            ('TTSTAY1',     'Tilt Restrictor Stay',             HardwareCategory.ACCESSORY,   'pcs',  95, 0.20),
            ('DRSEAL1',     'Door Bottom Drop Seal',            HardwareCategory.ACCESSORY,   'pcs', 220, 0.30),
            ('DRHINGE1',    'Heavy Duty Door Hinge',            HardwareCategory.HINGE,       'pcs', 260, 0.75),
            ('ROLLERHD1',   'Heavy Duty Sliding Door Roller',   HardwareCategory.ROLLER,      'pcs', 320, 0.15),
            ('SLDRLOCK1',   'Sliding Door Multipoint Lock',     HardwareCategory.LOCK,        'pcs', 650, 1.40),
            ('FLRGUIDE1',   'Sliding Door Floor Guide',         HardwareCategory.ACCESSORY,   'pcs',  60, 0.10),
            ('LVACT1',      'Louvre Actuator/Control Handle',   HardwareCategory.HANDLE,      'pcs', 280, 0.60),
            ('LVCLIP1',     'Louvre Blade Clip',                HardwareCategory.ACCESSORY,   'pcs',  15, 0.02),
        ]
        hardware = {}
        for stock_no, name, category, unit, cost, wt in new_hardware_data:
            item, _ = Hardware.objects.get_or_create(
                stock_no=stock_no,
                defaults={
                    'name': name, 'category': category, 'unit': unit,
                    'unit_cost': cost, 'weight_per_unit': wt, 'brand': brand, 'is_active': True,
                }
            )
            hardware[stock_no] = item

        # Existing shared hardware this command depends on - create minimal
        # fallbacks if they don't already exist (e.g. this command was run
        # before seed_data/seed_system_profiles).
        shared_hardware_defaults = {
            'WM_SCREW2': dict(name='Reinforcement Screw', category=HardwareCategory.SCREW, unit='pcs', cost=1, wt=0.0),
            'GASKET-HN': dict(name='Hinge Gasket', category=HardwareCategory.GASKET, unit='m', cost=30, wt=0.01),
            'GASKET-SL': dict(name='Sliding Gasket', category=HardwareCategory.GASKET, unit='m', cost=25, wt=0.01),
            'SLHNDL1AWHT': dict(name='Slider Handle A White', category=HardwareCategory.HANDLE, unit='pcs', cost=110, wt=0.65),
            'CDESPSS7': dict(name='25 Door SSEspag 1800', category=HardwareCategory.LOCK, unit='pcs', cost=600, wt=1.23),
            'HNDL1A-WHT': dict(name='Door Handle w/ Key White', category=HardwareCategory.HANDLE, unit='pcs', cost=135, wt=1.10),
            'STRKR3': dict(name='Door Striker', category=HardwareCategory.ACCESSORY, unit='pcs', cost=40, wt=0.05),
        }
        for stock_no, d in shared_hardware_defaults.items():
            item, _ = Hardware.objects.get_or_create(
                stock_no=stock_no,
                defaults={
                    'name': d['name'], 'category': d['category'], 'unit': d['unit'],
                    'unit_cost': d['cost'], 'weight_per_unit': d['wt'], 'brand': brand, 'is_active': True,
                }
            )
            hardware[stock_no] = item

        hardware_rule_data = [
            # -- SY04 Fixed Frame: no opening hardware, just glazing/sealing --
            ('SY04', 'WM_SCREW2', '8', 'Frame fixing screws'),

            # -- SY05 Tilt & Turn --
            ('SY05', 'TTESPAG1', 'n_panels', 'Tilt & turn espagnolette per sash'),
            ('SY05', 'TTHNDL1WHT', 'n_panels', 'Tilt & turn handle per sash'),
            ('SY05', 'TTHINGE1', 'n_panels', 'Corner hinge set per sash'),
            ('SY05', 'TTSTAY1', 'n_panels', 'Tilt restrictor stay per sash'),
            ('SY05', 'WM_SCREW2', '12 * n_panels', 'Screws for anchors'),
            ('SY05', 'GASKET-HN', 'n_panels * 4', 'Perimeter gasket'),

            # -- SY06 Super System Door --
            ('SY06', 'CDESPSS7', '1', 'Multipoint espag lock'),
            ('SY06', 'HNDL1A-WHT', '1', 'Door handle with key'),
            ('SY06', 'DRHINGE1', 'n_panels * 3', 'Heavy duty hinge set'),
            ('SY06', 'STRKR3', '1', 'Door striker'),
            ('SY06', 'DRSEAL1', 'n_panels', 'Bottom drop seal'),
            ('SY06', 'WM_SCREW2', '14 * n_panels', 'Fixing screws'),
            ('SY06', 'GASKET-HN', 'n_panels * 4', 'Perimeter gasket'),

            # -- SY07 Sliding Door --
            ('SY07', 'ROLLERHD1', 'n_panels * 2', 'Heavy duty rollers'),
            ('SY07', 'SLHNDL1AWHT', 'n_panels', 'Slider handle'),
            ('SY07', 'SLDRLOCK1', '1', 'Multipoint lock'),
            ('SY07', 'FLRGUIDE1', 'n_panels', 'Floor guide'),
            ('SY07', 'WM_SCREW2', '10 * n_panels', 'Fixing screws'),
            ('SY07', 'GASKET-SL', 'n_panels * 4', 'Sliding gasket'),

            # -- SY08 Louvre --
            ('SY08', 'LVACT1', '1', 'Louvre control handle/actuator'),
            ('SY08', 'LVCLIP1', 'round((H - 60) / 100) * 2', 'Blade end clips'),
            ('SY08', 'WM_SCREW2', '8', 'Frame fixing screws'),
        ]
        for system_code, hw_code, qty_formula, notes in hardware_rule_data:
            system = systems[system_code]
            item = hardware[hw_code]
            SystemHardwareRule.objects.get_or_create(
                system=system,
                hardware=item,
                defaults={'quantity_formula': qty_formula, 'notes': notes, 'is_active': True}
            )

        self.stdout.write(self.style.SUCCESS(
            'Seeded profiles, cut formulas, and hardware rules for SY04 (Fixed Frame), '
            'SY05 (Tilt & Turn), SY06 (Super System Door), SY07 (Sliding Door), '
            'SY08 (Louvre). Review /admin/catalog/profileformula/ and '
            '/admin/catalog/systemhardwarerule/ and adjust to your real spec sheets.'
        ))
