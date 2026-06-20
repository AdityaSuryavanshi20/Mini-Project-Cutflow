"""
CutFlow – Bar Optimization Engine

Implements first-fit decreasing cutting optimization with kerf, end waste,
profile grouping, and reusable offcut tracking.
"""
from bisect import insort
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


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


def optimize_cuts(
    cut_requests: List[CutRequest],
    bar_length: int = 6000,
    kerf: int = 5,
    end_waste: int = 10,
    min_reusable: int = 300,
    available_offcuts: Optional[List[Any]] = None,
) -> Dict[int, OptimizationResult]:
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
        bars: List[OptimizedBar] = []
        next_bar_id = 1
        available_offcuts = offcut_pool.get(profile_id, [])
        used_offcut_ids: List[int] = []
        leftover_offcuts: List[Dict[str, Any]] = []
        offcut_scrap_mm = 0

        def create_bar() -> OptimizedBar:
            nonlocal next_bar_id
            sample = sorted_requests[0]
            bar = OptimizedBar(
                bar_id=next_bar_id,
                profile_id=profile_id,
                profile_stock_no=sample.profile_stock_no,
                profile_name=sample.profile_name,
                bar_length=bar_length,
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
            for index, offcut in enumerate(available_offcuts):
                extra = end_waste if offcut['used_cuts'] == 0 else kerf + end_waste
                if offcut['length'] >= request.length + extra:
                    remaining = offcut['length'] - request.length - extra
                    if best_remaining is None or remaining < best_remaining:
                        best_remaining = remaining
                        best_index = index
            if best_index is None:
                return False

            selected = available_offcuts[best_index]
            selected['used_cuts'] += 1
            if selected['offcut_id'] is not None and selected['offcut_id'] not in used_offcut_ids:
                used_offcut_ids.append(selected['offcut_id'])
            selected['length'] = best_remaining
            if selected['length'] < min_reusable:
                offcut_scrap_mm += selected['length']
                del available_offcuts[best_index]
            else:
                available_offcuts.sort(key=lambda item: item['length'])
            return True

        for request in sorted_requests:
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

            if request.length > bar_length - end_waste:
                raise ValueError(
                    f"Cut length {request.length}mm exceeds available bar capacity "
                    f"{bar_length - end_waste}mm for profile {request.profile_stock_no}."
                )
            bar = create_bar()
            bar.cuts.append(OptimizedCut(
                cut_request=request,
                bar_id=bar.bar_id,
                start_pos=0,
                end_pos=request.length,
            ))
            bars.append(bar)

        for offcut in available_offcuts:
            if offcut['used_cuts'] > 0 and offcut['length'] >= min_reusable:
                leftover_offcuts.append({
                    'offcut_id': offcut['offcut_id'],
                    'profile_id': profile_id,
                    'length': offcut['length'],
                })
            elif offcut['used_cuts'] > 0:
                offcut_scrap_mm += offcut['length']

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
