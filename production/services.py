"""
CutFlow – Production Service
Orchestrates:
1. Computing profile cuts for each production item via formula engine
2. Generating hardware requirements via system rules
3. Running bar optimization via optimizer
4. Persisting all results to DB
"""
import logging
from typing import Dict, List, Tuple

from django.db import transaction
from decimal import Decimal

from catalog.models import Profile, ProfileFormula, SystemHardwareRule, CompanySettings
from core.formula_engine import evaluate_formula, build_formula_context
from core.optimizer import optimize_cuts, CutRequest
from .models import (
    ProductionJob, ProductionItem, ProductionCutItem,
    HardwareRequirement, OptimizationRun, OptimizationSegment,
    OptimizedCut, ReusableOffcut, ProductionJobStatus
)

logger = logging.getLogger(__name__)


def _formula_applicable(item: ProductionItem, formula: ProfileFormula, ctx: dict) -> Tuple[bool, str]:
    if formula.min_width is not None and item.width < formula.min_width:
        return False, f"skipped formula {formula.position}: width {item.width} < min_width {formula.min_width}"
    if formula.max_width is not None and item.width > formula.max_width:
        return False, f"skipped formula {formula.position}: width {item.width} > max_width {formula.max_width}"
    if formula.min_height is not None and item.height < formula.min_height:
        return False, f"skipped formula {formula.position}: height {item.height} < min_height {formula.min_height}"
    if formula.max_height is not None and item.height > formula.max_height:
        return False, f"skipped formula {formula.position}: height {item.height} > max_height {formula.max_height}"
    if formula.panel_condition:
        try:
            condition = evaluate_formula(formula.panel_condition, ctx)
            if not bool(condition):
                return False, f"skipped formula {formula.position}: condition false"
        except ValueError as exc:
            return False, f"invalid condition on {formula.position}: {exc}"
    return True, ''


def _normalize_position_code(role: str | None, formula_position: str) -> str:
    if not role:
        return formula_position.upper()
    role = role.lower()
    position = formula_position.lower() if formula_position else ''
    if role.startswith('outer_frame_'):
        return role.replace('outer_frame_', 'FRAME_').upper()
    if role == 'shutter_vertical':
        return 'SASH_LEFT' if 'height' in position else 'SASH_TOP'
    if role == 'shutter_horizontal':
        return 'SASH_TOP' if 'width' in position else 'SASH_LEFT'
    if role == 'bead_horizontal':
        return 'BEAD_TOP' if 'width' in position else 'BEAD_LEFT'
    if role == 'bead_vertical':
        return 'BEAD_LEFT' if 'height' in position else 'BEAD_TOP'
    if role in ('interlock', 'mullion', 'track'):
        return role.upper()
    return role.upper()


def _evaluate_formula_value(formula: str, ctx: dict, field_name: str) -> float:
    try:
        return float(evaluate_formula(formula, ctx))
    except Exception as exc:
        raise ValueError(f"Formula '{field_name}' failed: {formula} -> {exc}")


def _build_item_context(item: ProductionItem) -> dict:
    if item.system is None:
        raise ValueError(f"Production item {item.line_no} has no system assigned.")
    if item.width <= 0 or item.height <= 0:
        raise ValueError(
            f"Invalid dimensions for production item {item.line_no}: width={item.width}, height={item.height}."
        )
    if item.qty <= 0:
        raise ValueError(f"Invalid quantity for production item {item.line_no}: qty={item.qty}.")

    return build_formula_context(
        width=item.width,
        height=item.height,
        n_panels=item.n_panels,
        qty=item.qty,
        offset_l=0,
        offset_r=0,
        offset_t=0,
        offset_b=0,
    )


def compute_cuts_for_item(production_item: ProductionItem) -> Tuple[list, list]:
    """
    Evaluate all ProfileFormula entries for the item's system.
    Returns (cut_list, diagnostics).
    """
    system = production_item.system
    m = production_item
    ctx = _build_item_context(m)

    formulas = ProfileFormula.objects.filter(
        system=system,
        is_active=True,
        formula_type=ProfileFormula.FormulaType.CUT,
    ).select_related('profile', 'system_profile').order_by('profile__category', 'sort_order')
    results = []
    diagnostics = []

    if not formulas.exists():
        message = f"No active cut formulas found for system {system.code}."
        diagnostics.append(message)
        logger.warning(
            "%s on production item %s (%s).",
            message, production_item.line_no, production_item.pk
        )

    for formula in formulas:
        if not formula.profile.is_active:
            diagnostics.append(f"Skipping inactive profile {formula.profile.stock_no}.")
            continue
        if formula.system_profile and not formula.system_profile.is_active:
            diagnostics.append(
                f"Skipping inactive system-profile mapping for {formula.profile.stock_no}."
            )
            continue

        profile = formula.profile
        profile_ctx = ctx.copy()
        profile_ctx.update({
            'offset_l': profile.offset_left,
            'offset_r': profile.offset_right,
            'offset_t': profile.offset_top,
            'offset_b': profile.offset_bottom,
        })

        applicable, message = _formula_applicable(m, formula, profile_ctx)
        if not applicable:
            diagnostics.append(message)
            continue

        try:
            length = _evaluate_formula_value(formula.formula, profile_ctx, formula.position)
            quantity = _evaluate_formula_value(formula.quantity_formula, profile_ctx, f"{formula.position}.quantity")
        except ValueError as exc:
            diagnostics.append(str(exc))
            continue

        if length <= 0 or quantity <= 0:
            diagnostics.append(
                f"Formula produced non-positive values for {formula.position}: length={length}, quantity={quantity}."
            )
            continue

        # Multiply by the measurement's ordered quantity (number of identical
        # window/door units on this line). Without this, a line ordered with
        # qty=2 (or more) only ever produces the cut pieces for a single unit,
        # silently shorting every profile on the cutting list for that item.
        total_quantity = int(round(quantity)) * int(m.qty)

        position_code = _normalize_position_code(
            formula.system_profile.role if formula.system_profile else None,
            formula.position,
        )
        results.append({
            'profile': profile,
            'position': formula.position,
            'cut_length_mm': int(round(length)),
            'left_angle': float(formula.cut_angle_left),
            'right_angle': float(formula.cut_angle_right),
            'quantity': total_quantity,
            'position_code': position_code[:20],
        })

    return results, diagnostics


def compute_hardware_for_item(production_item: ProductionItem) -> Tuple[list, list]:
    """
    Evaluate SystemHardwareRule entries for the item's system.
    Returns (hardware_list, diagnostics).
    """
    system = production_item.system
    m = production_item
    ctx = _build_item_context(m)

    rules = SystemHardwareRule.objects.filter(
        system=system, is_active=True
    ).select_related('hardware')

    results = []
    diagnostics = []
    if not rules.exists():
        diagnostics.append(f"No hardware rules defined for system {system.code}.")

    for rule in rules:
        try:
            qty = _evaluate_formula_value(rule.quantity_formula, ctx, rule.hardware.stock_no)
        except ValueError as exc:
            diagnostics.append(str(exc))
            continue
        if qty <= 0:
            diagnostics.append(
                f"Hardware rule {rule.hardware.stock_no} returned zero quantity for item {production_item.line_no}."
            )
            continue
        results.append({
            'hardware': rule.hardware,
            'quantity': Decimal(str(round(qty, 2))),
            'unit': rule.hardware.unit,
        })
    return results, diagnostics


@transaction.atomic
def generate_production_items(production_job: ProductionJob):
    """
    For a job with no items yet, create ProductionItem + ProductionCutItem + HardwareRequirement
    from the project's MeasurementItems.
    """
    project = production_job.project
    measurements = project.measurements.select_related(
        'system', 'glass', 'color').all()

    if not measurements:
        raise ValueError(f"Production job {production_job.job_no} has no measurements to generate items.")

    # Deactivate previous optimization runs when production definitions change
    OptimizationRun.objects.filter(production_job=production_job, is_active=True).update(is_active=False)
    production_job.items.all().delete()

    for i, m in enumerate(measurements):
        if m.system is None:
            raise ValueError(f"Measurement {m.line_no} is missing a system.")
        if m.effective_width <= 0 or m.effective_height <= 0:
            raise ValueError(
                f"Measurement {m.line_no} has invalid dimensions: width={m.effective_width}, height={m.effective_height}."
            )

        item = ProductionItem.objects.create(
            job=production_job,
            measurement=m,
            line_no=m.line_no,
            reference=m.reference,
            location=m.location,
            system=m.system,
            glass=m.glass,
            color=m.color,
            width=m.effective_width,
            height=m.effective_height,
            qty=m.qty,
            n_panels=m.n_panels,
            description=m.description,
            sort_order=i,
        )

        cut_items, cut_diagnostics = compute_cuts_for_item(item)
        for c in cut_items:
            ProductionCutItem.objects.create(
                production_item=item,
                profile=c['profile'],
                position=c['position'],
                cut_length_mm=c['cut_length_mm'],
                left_angle=c['left_angle'],
                right_angle=c['right_angle'],
                quantity=c['quantity'],
                position_code=c['position_code'],
            )

        hw_items, hw_diagnostics = compute_hardware_for_item(item)
        for h in hw_items:
            HardwareRequirement.objects.create(
                production_item=item,
                hardware=h['hardware'],
                quantity=h['quantity'],
                unit=h['unit'],
            )

        item.diagnostics = '\n'.join(cut_diagnostics + hw_diagnostics)
        item.is_complete = bool(cut_items)
        item.save()

    production_job.status = ProductionJobStatus.IN_PROGRESS
    production_job.save()


@transaction.atomic
def run_optimization(
    production_job: ProductionJob,
    lock_project: bool = False,
    lock_user=None,
) -> OptimizationRun:
    """
    Collect all ProductionCutItem records for the job,
    run FFD optimization, persist results.
    """
    settings = CompanySettings.get()

    OptimizationRun.objects.filter(
        production_job=production_job, is_active=True
    ).update(is_active=False)

    # Re-running optimization for this job must be deterministic: it should
    # not feed the job its own leftover offcuts from a previous run of
    # itself (that would change the result on every click, since each run
    # both consumes and re-creates offcuts), and it must not permanently
    # lock out offcuts borrowed from OTHER jobs just because a now-discarded
    # earlier run of this job used them.
    #
    # 1. Release offcuts this job's previous run had marked as consumed —
    #    they belong to the shared pool and that run no longer exists.
    ReusableOffcut.objects.filter(used_in_job=production_job).update(
        is_available=True, used_in_job=None,
    )
    # 2. Remove offcuts this job's previous run generated — they describe
    #    leftovers from cut data that's about to be re-optimized and would
    #    otherwise be double-counted as "available" material for this same
    #    run.
    ReusableOffcut.objects.filter(source_job=production_job).delete()

    run = OptimizationRun.objects.create(
        production_job=production_job,
        bar_length_mm=settings.default_bar_length_mm,
        kerf_mm=settings.kerf_mm,
        end_waste_mm=settings.end_waste_mm,
        min_reusable_mm=settings.min_reusable_offcut_mm,
        is_active=True,
        created_by=lock_user if lock_project else None,
    )

    cut_requests = []
    profiles_by_id = {}
    production_items = list(production_job.items.all())
    if not production_items:
        run.delete()
        raise ValueError(
            f"Production job {production_job.job_no} has no production items. Generate items before optimization."
        )

    logger.debug(
        "Running optimization for job %s: %d production items found.",
        production_job.job_no, len(production_items)
    )
    for item in production_items:
        cuts = list(item.cut_items.select_related('profile').all())
        logger.debug(
            "Production item %s has %d cut items.", item.line_no, len(cuts)
        )
        for cut in cuts:
            if cut.quantity <= 0:
                continue
            profiles_by_id[cut.profile_id] = cut.profile
            cut_requests.append(CutRequest(
                profile_id=cut.profile.pk,
                profile_stock_no=cut.profile.stock_no,
                profile_name=cut.profile.name,
                length=cut.cut_length_mm,
                left_angle=float(cut.left_angle),
                right_angle=float(cut.right_angle),
                position_code=cut.position_code,
                source_ref=f"{production_job.job_no}/{item.line_no}",
                qty=cut.quantity,
            ))

    logger.debug(
        "Optimization job %s: %d total cut requests generated.",
        production_job.job_no, len(cut_requests)
    )

    if not cut_requests:
        run.delete()
        raise ValueError(
            "No production cuts available for optimization. "
            "Generate production items from measurements and ensure valid profile formulas exist for the system."
        )

    available_offcuts = list(
        ReusableOffcut.objects.filter(
            is_available=True,
            profile_id__in={request.profile_id for request in cut_requests},
        )
    )

    bar_length_by_profile = {
        profile_id: profile.available_stock_lengths()
        for profile_id, profile in profiles_by_id.items()
    }

    results = optimize_cuts(
        cut_requests,
        bar_length=bar_length_by_profile,
        kerf=settings.kerf_mm,
        end_waste=settings.end_waste_mm,
        min_reusable=settings.min_reusable_offcut_mm,
        available_offcuts=available_offcuts,
    )

    total_bars = 0
    total_material = 0
    total_used = 0
    total_kerf = 0
    total_waste = 0
    total_inventory_scrap = 0

    for profile_id, opt_result in results.items():
        try:
            profile = Profile.objects.get(pk=profile_id)
        except Profile.DoesNotExist:
            logger.warning(
                "Profile %s was referenced in optimization but no longer exists.", profile_id
            )
            continue

        # Most common stock bar length actually used for this profile's bars
        # (falls back to the company default if no bars were created, e.g.
        # an entirely offcut-fed segment).
        length_counts: Dict[int, int] = {}
        for bar in opt_result.bars:
            length_counts[bar.bar_length] = length_counts.get(bar.bar_length, 0) + 1
        primary_bar_length = (
            max(length_counts, key=length_counts.get)
            if length_counts else settings.default_bar_length_mm
        )

        segment = OptimizationSegment.objects.create(
            optimization_run=run,
            profile=profile,
            bars_required=opt_result.total_bars,
            bar_length_mm=primary_bar_length,
            total_cut_length_mm=opt_result.total_used_mm,
            waste_mm=opt_result.total_waste_mm,
            offcut_mm=opt_result.total_offcuts_mm,
            total_pieces=sum(len(bar.cuts) for bar in opt_result.bars),
        )

        for bar in opt_result.bars:
            for bar_cut in bar.cuts:
                prod_item = None
                src = bar_cut.cut_request.source_ref
                if '/' in src:
                    line = src.split('/')[-1]
                    prod_item = production_job.items.filter(line_no=line).first()

                OptimizedCut.objects.create(
                    segment=segment,
                    production_item=prod_item,
                    bar_number=bar.bar_id,
                    bar_length_mm=bar.bar_length,
                    cut_length_mm=bar_cut.cut_request.length,
                    left_angle=bar_cut.cut_request.left_angle,
                    right_angle=bar_cut.cut_request.right_angle,
                    position_code=bar_cut.cut_request.position_code,
                    start_position_mm=bar_cut.start_pos,
                )

        for bar in opt_result.bars:
            if bar.reusable_mm >= settings.min_reusable_offcut_mm:
                ReusableOffcut.objects.create(
                    profile=profile,
                    length_mm=bar.reusable_mm,
                    source_job=production_job,
                    is_available=True,
                )

        total_bars += opt_result.total_bars
        total_material += opt_result.total_bar_length_mm
        total_used += opt_result.total_used_mm
        total_kerf += opt_result.total_kerf_mm
        total_waste += opt_result.total_waste_mm

    used_offcut_ids = set()
    for opt_result in results.values():
        used_offcut_ids.update(opt_result.used_offcut_ids)
        total_inventory_scrap += opt_result.offcut_scrap_mm
        for leftover in opt_result.leftover_offcuts:
            if leftover['length'] >= settings.min_reusable_offcut_mm:
                ReusableOffcut.objects.create(
                    profile_id=leftover['profile_id'],
                    length_mm=leftover['length'],
                    source_job=production_job,
                    is_available=True,
                )

    if used_offcut_ids:
        ReusableOffcut.objects.filter(pk__in=used_offcut_ids).update(
            is_available=False,
            used_in_job=production_job,
        )

    if total_material < 0:
        raise ValueError(
            f"Invalid optimization total material: {total_material}mm."
        )
    if total_used < 0:
        raise ValueError(
            f"Invalid optimization total cut length: {total_used}mm."
        )
    if total_used > total_material:
        logger.error(
            "Optimization totals inconsistent: total_used=%s total_material=%s total_waste=%s",
            total_used,
            total_material,
            total_waste,
        )
        raise ValueError(
            f"Optimization used length {total_used}mm exceeds available material {total_material}mm."
        )

    utilisation = round((total_used + total_kerf) / total_material * 100, 2) if total_material else 0
    if utilisation > 100:
        logger.error(
            "Computed optimisation utilisation is greater than 100%%: %s%%", utilisation
        )
        raise ValueError(
            f"Optimization utilisation cannot exceed 100% ({utilisation}%)."
        )

    logger.debug(
        "Optimization totals: bars=%s material_mm=%s used_mm=%s waste_mm=%s utilisation_pct=%s",
        total_bars,
        total_material,
        total_used,
        total_waste,
        utilisation,
    )

    run.total_bars_used = total_bars
    run.total_material_mm = total_material
    run.total_cut_mm = total_used + total_kerf
    run.total_waste_mm = total_waste
    run.utilisation_pct = Decimal(str(utilisation))
    run_length_counts: Dict[int, int] = {}
    for segment in run.segments.all():
        run_length_counts[segment.bar_length_mm] = (
            run_length_counts.get(segment.bar_length_mm, 0) + segment.bars_required
        )
    if run_length_counts:
        run.bar_length_mm = max(run_length_counts, key=run_length_counts.get)
    run.save()

    production_job.status = ProductionJobStatus.OPTIMIZED
    production_job.save()

    if lock_project:
        if lock_user is None:
            raise ValueError('A user must be provided when locking the project.')
        production_job.project.lock(lock_user, reason='Production optimization completed')
        production_job.project.save()

    return run