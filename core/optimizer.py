"""
CutFlow – Bar Optimization Engine

Implements best-fit decreasing (BFD) cutting optimization with kerf, end
waste, profile grouping, reusable offcut tracking, multi-length stock bar
selection, and a post-pass bar consolidation step to reduce bar count.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union


@dataclass
class CutRequest:
    profile_id: int
    profile_stock_no: str
    profile_name: str
    length: int
    left_angle: float = 90.0
    right_angle: float = 90.0
    position_code: str = ''
    source_ref: str = ''
    qty: int = 1


@dataclass
class OptimizedCut:
    cut_request: CutRequest
    bar_id: int
    start_pos: int
    end_pos: int


@dataclass
class OptimizedBar:
    bar_id: int
    profile_id: int
    profile_stock_no: str
    profile_name: str
    bar_length: int
    kerf: int = 5
    end_waste: int = 10
    min_reusable: int = 0
    cuts: List[OptimizedCut] = field(default_factory=list)
    source_offcut_id: Optional[int] = None

    @property
    def cut_length_mm(self) -> int:
        return sum(c.cut_request.length for c in self.cuts)

    @property
    def kerf_loss_mm(self) -> int:
        return max(0, (len(self.cuts) - 1) * self.kerf)

    @property
    def reserved_end_waste_mm(self) -> int:
        return self.end_waste if self.cuts else 0

    @property
    def material_consumed_mm(self) -> int:
        return self.cut_length_mm + self.kerf_loss_mm + self.reserved_end_waste_mm

    @property
    def remaining(self) -> int:
        return max(0, self.bar_length - self.material_consumed_mm)

    @property
    def reusable_mm(self) -> int:
        return self.remaining if self.remaining >= self.min_reusable else 0

    @property
    def scrap_mm(self) -> int:
        return self.remaining if self.remaining < self.min_reusable else 0

    @property
    def utilisation_pct(self) -> float:
        if self.bar_length == 0:
            return 0.0
        used = self.cut_length_mm + self.kerf_loss_mm
        return float(round(used / self.bar_length * 100, 2))

    def sort_cuts(self) -> None:
        self.cuts.sort(key=lambda c: c.cut_request.length, reverse=True)
        position = 0
        for index, cut in enumerate(self.cuts):
            cut.start_pos = position
            cut.end_pos = position + cut.cut_request.length
            if index < len(self.cuts) - 1:
                position += cut.cut_request.length + self.kerf


@dataclass
class OptimizationResult:
    profile_id: int
    profile_stock_no: str
    profile_name: str
    bars: List[OptimizedBar] = field(default_factory=list)
    min_reusable: int = 0
    used_offcut_ids: List[int] = field(default_factory=list)
    leftover_offcuts: List[Dict[str, Any]] = field(default_factory=list)
    offcut_scrap_mm: int = 0

    @property
    def total_bars(self) -> int:
        return len(self.bars)

    @property
    def total_bar_length_mm(self) -> int:
        return sum(bar.bar_length for bar in self.bars)

    @property
    def total_used_mm(self) -> int:
        return sum(c.cut_request.length for bar in self.bars for c in bar.cuts)

    @property
    def total_kerf_mm(self) -> int:
        return sum(bar.kerf_loss_mm for bar in self.bars)

    @property
    def total_scrap_mm(self) -> int:
        return sum(bar.scrap_mm for bar in self.bars)

    @property
    def total_offcuts_mm(self) -> int:
        return sum(bar.reusable_mm for bar in self.bars)

    @property
    def total_waste_mm(self) -> int:
        return self.total_scrap_mm

    @property
    def utilisation_pct(self) -> float:
        total_bar_length = self.total_bar_length_mm
        if not total_bar_length:
            return 0.0
        used = self.total_used_mm + self.total_kerf_mm
        return float(round(used / total_bar_length * 100, 2))


def _normalize_offcut_pool(available_offcuts: Optional[List[Any]]) -> Dict[int, List[Dict[str, Any]]]:
    pool: Dict[int, List[Dict[str, Any]]] = {}
    if not available_offcuts:
        return pool
    for candidate in available_offcuts:
        profile_id = getattr(candidate, 'profile_id', None)
        length = getattr(candidate, 'length_mm', None)
        offcut_id = getattr(candidate, 'id', None)
        if length is None:
            length = getattr(candidate, 'length', None)
        if profile_id is None or length is None:
            continue
        try:
            length = int(length)
        except (TypeError, ValueError):
            continue
        if length <= 0:
            continue
        pool.setdefault(profile_id, []).append({
            'offcut_id': offcut_id,
            'length': length,
            'used_cuts': 0,
        })
    for values in pool.values():
        values.sort(key=lambda item: item['length'])
    return pool


def _resolve_stock_lengths(
    bar_length: Union[int, Dict[Any, Any]],
    profile_id: int,
    profile_stock_no: str,
    default_length: int = 6000,
) -> List[int]:
    """
    Normalize the `bar_length` argument into a sorted list of available stock
    lengths (ascending) for a given profile.

    Accepts:
      - a single int (back-compat): one stock length for every profile.
      - a dict keyed by profile_id or profile_stock_no, whose value is either
        a single int or a list/tuple of ints (multiple stock lengths stocked
        for that profile, e.g. [5950, 6000, 6500]).
    Falls back to `default_length` if nothing matches.
    """
    if isinstance(bar_length, (int, float)):
        return [int(bar_length)]

    if isinstance(bar_length, dict):
        candidate = bar_length.get(profile_id, bar_length.get(profile_stock_no))
        if candidate is None:
            return [int(default_length)]
        if isinstance(candidate, (list, tuple, set)):
            lengths = sorted({int(v) for v in candidate if int(v) > 0})
            return lengths or [int(default_length)]
        return [int(candidate)]

    return [int(default_length)]


def _best_stock_length_for(remaining_requests: List[CutRequest], stock_lengths: List[int],
                            kerf: int, end_waste: int) -> int:
    """
    Choose the stock length that wastes the least material for the next bar,
    given the current queue of pending requests (longest-first). Tries to
    pack as many of the next pending cuts as possible into each candidate
    stock length and picks the one with the smallest leftover after that
    greedy fill, preferring the shortest stock length on ties (less capital
    tied up / less leftover offcut to store).
    """
    if len(stock_lengths) == 1:
        return stock_lengths[0]
    if not remaining_requests:
        return stock_lengths[0]

    mandatory_length = remaining_requests[0].length
    best_length = None
    best_leftover = None
    for length in stock_lengths:
        remaining = length - end_waste
        if remaining < mandatory_length:
            continue
        fitted_any = False
        for req in remaining_requests:
            needed = req.length + (kerf if fitted_any else 0)
            if needed <= remaining:
                remaining -= needed
                fitted_any = True
            else:
                break
        if best_leftover is None or remaining < best_leftover:
            best_leftover = remaining
            best_length = length

    if best_length is None:
        # Nothing fits the mandatory cut; let the caller's oversize check
        # raise a clear error rather than silently picking a too-small bar.
        return max(stock_lengths)

    return best_length


def _consolidate_bars(bars: List[OptimizedBar], kerf: int) -> List[OptimizedBar]:
    """
    Post-pass: try to fully drain the most under-filled bars into the spare
    capacity of other bars, eliminating bars outright when every one of
    their cuts can be relocated. Only ever merges into bars that have more
    free space than the donor (so end-waste accounting never changes for
    the receiving bar), and only commits a move if it actually reduces the
    total bar count. Safe no-op when nothing can be consolidated.
    """
    if len(bars) < 2:
        return bars

    changed = True
    while changed:
        changed = False
        # Try donors from the most empty (least utilised) bar first.
        donors = sorted(bars, key=lambda b: b.cut_length_mm)
        for donor in donors:
            if not donor.cuts:
                continue
            receivers = [b for b in bars if b is not donor]
            if not receivers:
                continue

            donor_cuts = sorted(donor.cuts, key=lambda c: c.cut_request.length, reverse=True)
            placement: Dict[int, OptimizedBar] = {}
            simulated_remaining = {id(b): b.remaining for b in receivers}
            simulated_has_cuts = {id(b): bool(b.cuts) for b in receivers}
            feasible = True

            for cut in donor_cuts:
                best_bar = None
                best_after = None
                for receiver in receivers:
                    key = id(receiver)
                    needed = cut.cut_request.length + (kerf if simulated_has_cuts[key] else 0)
                    if needed <= simulated_remaining[key]:
                        after = simulated_remaining[key] - needed
                        if best_after is None or after < best_after:
                            best_after = after
                            best_bar = receiver
                if best_bar is None:
                    feasible = False
                    break
                key = id(best_bar)
                simulated_remaining[key] -= (
                    cut.cut_request.length + (kerf if simulated_has_cuts[key] else 0)
                )
                simulated_has_cuts[key] = True
                placement[id(cut)] = best_bar

            if not feasible:
                continue

            # Commit: move every cut from donor into its chosen receiver.
            for cut in donor_cuts:
                target = placement[id(cut)]
                target.cuts.append(cut)
            bars = [b for b in bars if b is not donor]
            changed = True
            break

    return bars


def optimize_cuts(
    cut_requests: List[CutRequest],
    bar_length: Union[int, Dict[Any, Any]] = 6000,
    kerf: int = 5,
    end_waste: int = 10,
    min_reusable: int = 300,
    available_offcuts: Optional[List[Any]] = None,
    consolidate: bool = True,
) -> Dict[int, OptimizationResult]:
    """
    bar_length may be a single int (one stock length for every profile, the
    original behaviour) or a dict mapping profile_id/profile_stock_no to an
    int or list of ints describing the stock lengths available for that
    profile. When multiple lengths are available, the smallest length that
    still fits the next pending cuts with minimal leftover is chosen for
    each new bar.

    Raises ValueError if any cut_request has a non-positive length or qty,
    since such values would silently corrupt bar-packing and utilisation
    calculations downstream.
    """
    for request in cut_requests:
        if request.length <= 0:
            raise ValueError(
                f"Cut request for profile {request.profile_stock_no} has a non-positive "
                f"length ({request.length}mm); refusing to optimize invalid cut data."
            )
        if request.qty <= 0:
            raise ValueError(
                f"Cut request for profile {request.profile_stock_no} has a non-positive "
                f"quantity ({request.qty}); refusing to optimize invalid cut data."
            )

    profile_groups: Dict[int, List[CutRequest]] = {}
    for request in cut_requests:
        profile_groups.setdefault(request.profile_id, []).append(request)

    offcut_pool = _normalize_offcut_pool(available_offcuts)
    results: Dict[int, OptimizationResult] = {}

    for profile_id, requests in profile_groups.items():
        expanded: List[CutRequest] = []
        for request in requests:
            quantity = max(1, int(request.qty))
            for _ in range(quantity):
                expanded.append(request)

        if not expanded:
            continue

        sorted_requests = sorted(expanded, key=lambda r: r.length, reverse=True)
        sample = sorted_requests[0]
        stock_lengths = _resolve_stock_lengths(
            bar_length, profile_id, sample.profile_stock_no, default_length=6000
        )

        bars: List[OptimizedBar] = []
        next_bar_id = 1
        profile_offcuts = offcut_pool.get(profile_id, [])
        used_offcut_ids: List[int] = []
        leftover_offcuts: List[Dict[str, Any]] = []
        offcut_scrap_mm = 0

        def create_bar(pending_after_this: List[CutRequest]) -> OptimizedBar:
            nonlocal next_bar_id
            chosen_length = _best_stock_length_for(
                pending_after_this, stock_lengths, kerf, end_waste
            )
            bar = OptimizedBar(
                bar_id=next_bar_id,
                profile_id=profile_id,
                profile_stock_no=sample.profile_stock_no,
                profile_name=sample.profile_name,
                bar_length=chosen_length,
                kerf=kerf,
                end_waste=end_waste,
                min_reusable=min_reusable,
            )
            next_bar_id += 1
            return bar

        def allocate_from_offcut(request: CutRequest) -> bool:
            nonlocal offcut_scrap_mm
            best_index = None
            best_remaining = None
            for index, offcut in enumerate(profile_offcuts):
                extra = end_waste if offcut['used_cuts'] == 0 else kerf + end_waste
                if offcut['length'] >= request.length + extra:
                    remaining = offcut['length'] - request.length - extra
                    if best_remaining is None or remaining < best_remaining:
                        best_remaining = remaining
                        best_index = index
            if best_index is None:
                return False

            selected = profile_offcuts[best_index]
            selected['used_cuts'] += 1
            if selected['offcut_id'] is not None and selected['offcut_id'] not in used_offcut_ids:
                used_offcut_ids.append(selected['offcut_id'])
            selected['length'] = best_remaining
            if selected['length'] < min_reusable:
                offcut_scrap_mm += selected['length']
                del profile_offcuts[best_index]
            else:
                profile_offcuts.sort(key=lambda item: item['length'])
            return True

        for index, request in enumerate(sorted_requests):
            if allocate_from_offcut(request):
                continue

            best_bar = None
            best_after = None
            for bar in bars:
                needed = request.length + (kerf if bar.cuts else 0)
                if needed <= bar.remaining:
                    after = bar.remaining - needed
                    if best_after is None or after < best_after:
                        best_after = after
                        best_bar = bar

            if best_bar is not None:
                start_pos = best_bar.cut_length_mm + best_bar.kerf_loss_mm + (kerf if best_bar.cuts else 0)
                best_bar.cuts.append(OptimizedCut(
                    cut_request=request,
                    bar_id=best_bar.bar_id,
                    start_pos=start_pos,
                    end_pos=start_pos + request.length,
                ))
                continue

            longest_available_stock = max(stock_lengths)
            if request.length > longest_available_stock - end_waste:
                raise ValueError(
                    f"Cut length {request.length}mm exceeds available bar capacity "
                    f"{longest_available_stock - end_waste}mm for profile {request.profile_stock_no}."
                )
            bar = create_bar([request] + sorted_requests[index + 1:])
            bar.cuts.append(OptimizedCut(
                cut_request=request,
                bar_id=bar.bar_id,
                start_pos=0,
                end_pos=request.length,
            ))
            bars.append(bar)

        for offcut in profile_offcuts:
            if offcut['used_cuts'] > 0 and offcut['length'] >= min_reusable:
                leftover_offcuts.append({
                    'offcut_id': offcut['offcut_id'],
                    'profile_id': profile_id,
                    'length': offcut['length'],
                })
            elif offcut['used_cuts'] > 0:
                offcut_scrap_mm += offcut['length']

        if consolidate:
            bars = _consolidate_bars(bars, kerf=kerf)

        for bar in bars:
            bar.sort_cuts()

        used_bars = [bar for bar in bars if bar.cuts]
        results[profile_id] = OptimizationResult(
            profile_id=profile_id,
            profile_stock_no=sorted_requests[0].profile_stock_no,
            profile_name=sorted_requests[0].profile_name,
            bars=used_bars,
            min_reusable=min_reusable,
            used_offcut_ids=used_offcut_ids,
            leftover_offcuts=leftover_offcuts,
            offcut_scrap_mm=offcut_scrap_mm,
        )

    return results
