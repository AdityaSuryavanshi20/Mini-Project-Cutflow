"""
Tests for core.optimizer — the bar-cutting optimization engine.

This is the highest-stakes module in CutFlow: a bug here doesn't just crash
a page, it produces a wrong cutting list that gets handed to a fabricator,
or silently wastes material. These tests pin down the behaviors that were
manually verified during the original audit, so future changes can't
regress them without a test failing.
"""
from django.test import SimpleTestCase

from core.optimizer import CutRequest, optimize_cuts


def make_request(profile_id=1, length=1000, qty=1, stock_no='P1', name='Profile 1'):
    return CutRequest(
        profile_id=profile_id, profile_stock_no=stock_no, profile_name=name,
        length=length, qty=qty,
    )


class BasicPackingTests(SimpleTestCase):
    """Sanity checks on straightforward, single-stock-length packing."""

    def test_cuts_that_fit_exactly_use_one_bar(self):
        # 3 x 1990mm + 2 kerfs (5mm) + 10mm end waste = 5990mm, fits in a 6000mm bar.
        reqs = [make_request(length=1990, qty=3)]
        result = optimize_cuts(reqs, bar_length=6000, kerf=5, end_waste=10)
        r = result[1]
        self.assertEqual(r.total_bars, 1)
        self.assertEqual(r.bars[0].cuts.__len__(), 3)

    def test_cuts_that_overflow_split_across_bars(self):
        # 3 x 2000mm + 2 kerfs + 10mm end waste = 6020mm > 6000mm bar -> needs 2 bars.
        reqs = [make_request(length=2000, qty=3)]
        result = optimize_cuts(reqs, bar_length=6000, kerf=5, end_waste=10)
        r = result[1]
        self.assertEqual(r.total_bars, 2)
        total_cut_count = sum(len(b.cuts) for b in r.bars)
        self.assertEqual(total_cut_count, 3)

    def test_multiple_profiles_get_separate_results(self):
        reqs = [
            make_request(profile_id=1, length=1000, qty=2, stock_no='A'),
            make_request(profile_id=2, length=2000, qty=2, stock_no='B'),
        ]
        result = optimize_cuts(reqs, bar_length=6000, kerf=5, end_waste=10)
        self.assertEqual(set(result.keys()), {1, 2})
        self.assertEqual(sum(len(b.cuts) for b in result[1].bars), 2)
        self.assertEqual(sum(len(b.cuts) for b in result[2].bars), 2)

    def test_empty_request_list_returns_empty_result(self):
        result = optimize_cuts([], bar_length=6000)
        self.assertEqual(result, {})


class InputValidationTests(SimpleTestCase):
    """
    Regression tests for the validation added after the original audit found
    that zero/negative lengths and quantities were silently packed into
    bars, corrupting utilisation and waste calculations.
    """

    def test_zero_length_cut_is_rejected(self):
        reqs = [make_request(length=0, qty=1)]
        with self.assertRaises(ValueError):
            optimize_cuts(reqs, bar_length=6000)

    def test_negative_length_cut_is_rejected(self):
        reqs = [make_request(length=-100, qty=1)]
        with self.assertRaises(ValueError):
            optimize_cuts(reqs, bar_length=6000)

    def test_negative_quantity_is_rejected(self):
        reqs = [make_request(length=1000, qty=-1)]
        with self.assertRaises(ValueError):
            optimize_cuts(reqs, bar_length=6000)

    def test_zero_quantity_is_rejected(self):
        reqs = [make_request(length=1000, qty=0)]
        with self.assertRaises(ValueError):
            optimize_cuts(reqs, bar_length=6000)

    def test_invalid_cut_mixed_with_valid_cuts_still_raises(self):
        # A single bad request anywhere in the batch must reject the whole
        # batch rather than silently packing the bad one in among good ones.
        reqs = [make_request(length=2000, qty=2), make_request(length=-50, qty=1)]
        with self.assertRaises(ValueError):
            optimize_cuts(reqs, bar_length=6000, kerf=5, end_waste=10)

    def test_oversize_cut_raises_value_error(self):
        # A cut longer than any available stock length cannot be fulfilled.
        reqs = [make_request(length=7000, qty=1)]
        with self.assertRaises(ValueError):
            optimize_cuts(reqs, bar_length=6000, kerf=5, end_waste=10)


class MultiStockLengthTests(SimpleTestCase):
    """Tests for the multi-bar-length stock selection feature."""

    def test_picks_from_multiple_available_stock_lengths(self):
        reqs = [make_request(profile_id=3, length=5800, qty=2, stock_no='P3')]
        result = optimize_cuts(
            reqs, bar_length={3: [5950, 6000, 6500]}, kerf=5, end_waste=10
        )
        r = result[3]
        used_lengths = {b.bar_length for b in r.bars}
        # Every bar used must be one of the declared stock lengths.
        self.assertTrue(used_lengths.issubset({5950, 6000, 6500}))

    def test_dict_keyed_by_stock_no_also_works(self):
        reqs = [make_request(profile_id=9, length=3000, qty=1, stock_no='STK9')]
        result = optimize_cuts(
            reqs, bar_length={'STK9': [4000, 6000]}, kerf=5, end_waste=10
        )
        r = result[9]
        self.assertEqual(r.total_bars, 1)
        self.assertIn(r.bars[0].bar_length, (4000, 6000))

    def test_unmapped_profile_falls_back_to_default_length(self):
        reqs = [make_request(profile_id=42, length=3000, qty=1, stock_no='UNMAPPED')]
        result = optimize_cuts(
            reqs, bar_length={1: [6000]}, kerf=5, end_waste=10
        )
        r = result[42]
        self.assertEqual(r.bars[0].bar_length, 6000)  # the documented default


class OffcutReuseTests(SimpleTestCase):
    """Tests for reusable offcut consumption."""

    class FakeOffcut:
        def __init__(self, id, profile_id, length_mm):
            self.id = id
            self.profile_id = profile_id
            self.length_mm = length_mm

    def test_offcut_large_enough_is_used_instead_of_a_new_bar(self):
        reqs = [make_request(profile_id=4, length=1000, qty=2, stock_no='P4')]
        offcuts = [self.FakeOffcut(101, 4, 2500)]
        result = optimize_cuts(
            reqs, bar_length=6000, kerf=5, end_waste=10, available_offcuts=offcuts
        )
        r = result[4]
        self.assertIn(101, r.used_offcut_ids)
        # No fresh 6000mm bars should have been required for 2x1000mm cuts
        # that fit comfortably on a 2500mm offcut.
        fresh_bars = [b for b in r.bars if b.source_offcut_id is None]
        self.assertEqual(len(fresh_bars), 0)

    def test_offcut_too_small_is_left_unused(self):
        reqs = [make_request(profile_id=5, length=2000, qty=1, stock_no='P5')]
        offcuts = [self.FakeOffcut(202, 5, 500)]  # too short for a 2000mm cut
        result = optimize_cuts(
            reqs, bar_length=6000, kerf=5, end_waste=10, available_offcuts=offcuts
        )
        r = result[5]
        self.assertNotIn(202, r.used_offcut_ids)

    def test_offcut_for_different_profile_is_ignored(self):
        reqs = [make_request(profile_id=6, length=1000, qty=1, stock_no='P6')]
        offcuts = [self.FakeOffcut(303, profile_id=999, length_mm=5000)]
        result = optimize_cuts(
            reqs, bar_length=6000, kerf=5, end_waste=10, available_offcuts=offcuts
        )
        r = result[6]
        self.assertNotIn(303, r.used_offcut_ids)
        self.assertEqual(r.total_bars, 1)  # had to use a fresh bar


class UtilisationAndWasteMathTests(SimpleTestCase):
    """
    Pin down the arithmetic in OptimizedBar/OptimizationResult so a future
    refactor can't silently change what "utilisation" or "waste" means.
    """

    def test_utilisation_pct_accounts_for_kerf(self):
        # Single 1000mm cut on a 2000mm bar, 5mm kerf (irrelevant with 1 cut),
        # 10mm end waste. Material consumed = 1000 + 0 (no kerf, only 1 cut) + 10 = 1010.
        # Utilisation uses cut_length + kerf only (not end waste): 1000/2000 = 50%.
        reqs = [make_request(length=1000, qty=1)]
        result = optimize_cuts(reqs, bar_length=2000, kerf=5, end_waste=10)
        bar = result[1].bars[0]
        self.assertEqual(bar.utilisation_pct, 50.0)

    def test_remaining_never_goes_negative(self):
        reqs = [make_request(length=1990, qty=3)]
        result = optimize_cuts(reqs, bar_length=6000, kerf=5, end_waste=10)
        for bar in result[1].bars:
            self.assertGreaterEqual(bar.remaining, 0)

    def test_total_bars_used_matches_sum_of_per_profile_bars(self):
        reqs = [
            make_request(profile_id=1, length=2000, qty=3, stock_no='A'),
            make_request(profile_id=2, length=1500, qty=2, stock_no='B'),
        ]
        result = optimize_cuts(reqs, bar_length=6000, kerf=5, end_waste=10)
        total = sum(r.total_bars for r in result.values())
        self.assertEqual(total, result[1].total_bars + result[2].total_bars)


class ConsolidationTests(SimpleTestCase):
    """The post-pass that tries to reduce bar count by repacking leftovers."""

    def test_consolidation_does_not_increase_bar_count(self):
        reqs = [
            make_request(length=3000, qty=1),
            make_request(length=2000, qty=1),
            make_request(length=500, qty=1),
        ]
        no_consolidate = optimize_cuts(
            reqs, bar_length=6000, kerf=5, end_waste=10, consolidate=False
        )
        consolidate = optimize_cuts(
            reqs, bar_length=6000, kerf=5, end_waste=10, consolidate=True
        )
        self.assertLessEqual(consolidate[1].total_bars, no_consolidate[1].total_bars)

    def test_consolidation_never_loses_a_cut(self):
        reqs = [
            make_request(length=4000, qty=1),
            make_request(length=1900, qty=1),
            make_request(length=3990, qty=1),
            make_request(length=1900, qty=1),
        ]
        result = optimize_cuts(reqs, bar_length=6000, kerf=5, end_waste=10, consolidate=True)
        total_cuts = sum(len(b.cuts) for b in result[1].bars)
        self.assertEqual(total_cuts, 4)
