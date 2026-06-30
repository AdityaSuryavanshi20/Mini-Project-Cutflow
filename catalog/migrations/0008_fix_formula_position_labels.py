"""
Fix two related data bugs found in production job J00007's cutting list:

Bug A — every ProfileFormula for OF004W (SY01) and SOF01W (SY02/SY03) was
linked to the SAME SystemProfile (the 'top' role) regardless of whether the
formula's `position` was top/bottom/left/right. The four correct, distinct
SystemProfile role rows already exist — they were just never wired up to the
matching formula. This made every cut on these profiles render as FRAME_TOP
in the cutting list, no matter which edge it actually was.

Bug B — OF004W (SY01) has a second, redundant set of active cut formulas
(position = frame_width_top / frame_width_bottom / frame_height_left /
frame_height_right) that duplicate formulas 1-4 but compute length without
subtracting profile offsets (formula='W' instead of 'W - offset_l - offset_r'),
and have no system_profile link at all (hence raw, inconsistent labels).
These produce a second, slightly-wrong set of Outer Frame cuts on every job
that uses SY01. They are deactivated rather than deleted, to preserve
history on any already-generated production jobs.
"""
from django.db import migrations


# position substring -> role suffix, used to match each formula to its
# correct SystemProfile role for a given profile/system pair.
POSITION_ROLE_MAP = [
    ('top', 'outer_frame_top'),
    ('bottom', 'outer_frame_bottom'),
    ('left', 'outer_frame_left'),
    ('right', 'outer_frame_right'),
]


def fix_formula_links(apps, schema_editor):
    ProfileFormula = apps.get_model('catalog', 'ProfileFormula')
    SystemProfile = apps.get_model('catalog', 'SystemProfile')

    # ── Bug A: re-link each outer-frame formula to its correct role ────────
    targets = ProfileFormula.objects.filter(
        profile__stock_no__in=['OF004W', 'SOF01W'],
        position__in=['outer_top', 'outer_bottom', 'outer_left', 'outer_right'],
    ).select_related('system', 'profile')

    for formula in targets:
        position = (formula.position or '').lower()
        matched_role = None
        for substr, role in POSITION_ROLE_MAP:
            if substr in position:
                matched_role = role
                break
        if not matched_role:
            continue
        try:
            correct_sp = SystemProfile.objects.get(
                system=formula.system,
                profile=formula.profile,
                role=matched_role,
            )
        except SystemProfile.DoesNotExist:
            continue
        if formula.system_profile_id != correct_sp.id:
            formula.system_profile = correct_sp
            formula.save(update_fields=['system_profile'])

    # ── Bug B: deactivate the redundant, offset-less OF004W formula set ────
    ProfileFormula.objects.filter(
        profile__stock_no='OF004W',
        position__in=[
            'frame_width_top', 'frame_width_bottom',
            'frame_height_left', 'frame_height_right',
        ],
        system_profile__isnull=True,
    ).update(is_active=False)


def reverse_fix_formula_links(apps, schema_editor):
    ProfileFormula = apps.get_model('catalog', 'ProfileFormula')

    # Reactivate the duplicate set.
    ProfileFormula.objects.filter(
        profile__stock_no='OF004W',
        position__in=[
            'frame_width_top', 'frame_width_bottom',
            'frame_height_left', 'frame_height_right',
        ],
        system_profile__isnull=True,
    ).update(is_active=True)

    # Revert all four outer-frame formulas per profile/system back to
    # pointing at the 'top' role SystemProfile (restores original bug).
    SystemProfile = apps.get_model('catalog', 'SystemProfile')
    targets = ProfileFormula.objects.filter(
        profile__stock_no__in=['OF004W', 'SOF01W'],
        position__in=['outer_top', 'outer_bottom', 'outer_left', 'outer_right'],
    ).select_related('system', 'profile')
    for formula in targets:
        try:
            top_sp = SystemProfile.objects.get(
                system=formula.system,
                profile=formula.profile,
                role='outer_frame_top',
            )
        except SystemProfile.DoesNotExist:
            continue
        formula.system_profile = top_sp
        formula.save(update_fields=['system_profile'])


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0007_fix_track_quantity_formula'),
    ]

    operations = [
        migrations.RunPython(
            fix_formula_links,
            reverse_fix_formula_links,
        ),
    ]
