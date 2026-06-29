"""
Fix track quantity formulas:
  SY02 (2-Track): track_length formula quantity was '1', should be '2'
  SY03 (3-Track): track_length formula quantity was '1', should be '3'
Also fix SY03 sash_height quantity: '2 * n_panels' is correct for top+bottom
rails per sash, but the interlock/mullion panel_condition should exclude n_panels=1
to avoid a zero-quantity cut being produced (and silently skipped) when users
enter a single-panel measurement against a sliding system.
"""
from django.db import migrations


def fix_track_and_interlock_formulas(apps, schema_editor):
    ProfileFormula = apps.get_model('catalog', 'ProfileFormula')
    System = apps.get_model('catalog', 'System')

    # ── Fix track quantity ───────────────────────────────────────────────────
    track_fixes = {
        'SY02': '2',  # 2-Track System needs 2 track lengths
        'SY03': '3',  # 3-Track System needs 3 track lengths
    }
    for sys_code, qty_formula in track_fixes.items():
        try:
            system = System.objects.get(code=sys_code)
        except System.DoesNotExist:
            continue
        ProfileFormula.objects.filter(
            system=system,
            position='track_length',
        ).update(quantity_formula=qty_formula)

    # ── Fix interlock/mullion panel_condition ────────────────────────────────
    # These profiles produce quantity = n_panels - 1. When n_panels = 1,
    # quantity evaluates to 0, which services.py rejects with a diagnostic
    # message but no hard error — the cut is silently dropped.
    # Adding panel_condition = 'n_panels - 1' (truthy when > 0) makes the
    # formula engine skip the formula cleanly instead of computing a zero cut.
    interlock_positions = ['interlock_length', 'mullion_length']
    for sys_code in ('SY01', 'SY02', 'SY03'):
        try:
            system = System.objects.get(code=sys_code)
        except System.DoesNotExist:
            continue
        ProfileFormula.objects.filter(
            system=system,
            position__in=interlock_positions,
        ).update(panel_condition='n_panels - 1')


def reverse_track_and_interlock_formulas(apps, schema_editor):
    ProfileFormula = apps.get_model('catalog', 'ProfileFormula')
    System = apps.get_model('catalog', 'System')

    for sys_code in ('SY02', 'SY03'):
        try:
            system = System.objects.get(code=sys_code)
        except System.DoesNotExist:
            continue
        ProfileFormula.objects.filter(
            system=system,
            position='track_length',
        ).update(quantity_formula='1')

    for sys_code in ('SY01', 'SY02', 'SY03'):
        try:
            system = System.objects.get(code=sys_code)
        except System.DoesNotExist:
            continue
        ProfileFormula.objects.filter(
            system=system,
            position__in=['interlock_length', 'mullion_length'],
        ).update(panel_condition='')


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0006_add_system_material'),
    ]

    operations = [
        migrations.RunPython(
            fix_track_and_interlock_formulas,
            reverse_track_and_interlock_formulas,
        ),
    ]
