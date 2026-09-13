"""Countdown -> position, and the rules that keep it from jittering."""

import pytest

from ttcmap.map import interpolate
from ttcmap.map.interpolate import advance, carry_floor, is_on_segment, progress_from_eta
from ttcmap.map.state import TrainPosition

SPAN = 120.0


@pytest.fixture(autouse=True)
def fixed_span(monkeypatch):
    monkeypatch.setattr(interpolate, "span_for", lambda *_: SPAN)


def train(eta_s, key="line-1|0|b|0", floor=0.0):
    return TrainPosition(
        line="line-1",
        direction=0,
        from_station="a",
        to_station="b",
        eta_s=eta_s,
        progress_floor=floor,
        key=key,
    )


def test_progress_is_the_fraction_of_the_segment_already_run():
    assert progress_from_eta(60, 120) == pytest.approx(0.5)
    assert progress_from_eta(30, 120) == pytest.approx(0.75)


def test_a_train_further_out_than_one_segment_has_not_left_the_origin():
    assert progress_from_eta(300, 120) == 0.0
    assert not is_on_segment(300, 120)
    assert is_on_segment(119, 120)


def test_sightings_from_further_back_are_dropped_not_stacked_at_the_origin():
    # Ignore duplicate sightings from stations farther ahead.
    assert advance([train(eta_s=300)], elapsed_s=0) == []


def test_a_train_already_on_the_segment_is_not_yanked_off_by_a_revised_eta():
    # An ETA revision must not remove a sighting already on this segment.
    [position] = advance([train(eta_s=300, floor=0.4)], elapsed_s=0)
    assert position.progress == pytest.approx(0.4)


def test_arrived_and_overdue_trains_pin_to_the_platform():
    assert progress_from_eta(0, 120) == 1.0
    assert progress_from_eta(-45, 120) == 1.0


def test_an_arrived_train_is_held_across_the_dwell():
    [position] = advance([train(eta_s=0)], elapsed_s=interpolate.ARRIVED_GRACE_S - 1)
    assert position.progress == 1.0


def test_an_arrived_train_is_released_once_the_next_segment_has_it():
    # Expired arrivals must not overlap the next segment.
    assert advance([train(eta_s=0)], elapsed_s=interpolate.ARRIVED_GRACE_S) == []


def test_the_floor_cannot_pin_a_train_to_a_platform_it_has_left():
    assert advance([train(eta_s=0, floor=1.0)], elapsed_s=interpolate.ARRIVED_GRACE_S) == []


def test_advance_ages_the_countdown():
    [position] = advance([train(eta_s=90)], elapsed_s=30)
    assert position.eta_s == pytest.approx(60)
    assert position.progress == pytest.approx(0.5)


def test_advance_does_not_mutate_the_snapshot():
    original = train(eta_s=90)
    advance([original], elapsed_s=30)
    assert original.eta_s == 90
    assert original.progress == 0.0


def test_schedule_positions_pass_through_untouched():
    scheduled = TrainPosition(
        line="line-1", direction=0, from_station="a", to_station="b", progress=0.4
    )
    [position] = advance([scheduled], elapsed_s=30)
    assert position is scheduled


def test_progress_never_falls_below_the_floor():
    [position] = advance([train(eta_s=120, floor=0.8)], elapsed_s=0)
    assert position.progress == pytest.approx(0.8)


def test_floor_carries_a_held_train_forward_instead_of_backwards():
    # A repeated ETA must preserve the previously projected progress.
    previous = [train(eta_s=120)]
    seeded = carry_floor([train(eta_s=120)], previous, elapsed_s=30)

    assert advance(seeded, elapsed_s=0)[0].progress == pytest.approx(0.25)
    assert advance([train(eta_s=120)], elapsed_s=0) == []


def test_floor_is_not_carried_when_the_queue_shifts():
    # After the queue shifts, the replacement train must not inherit the old floor.
    previous = [train(eta_s=30)]
    seeded = carry_floor([train(eta_s=120)], previous, elapsed_s=30)
    assert seeded[0].progress_floor == 0.0


def test_floor_survives_minute_rounding():
    previous = [train(eta_s=120)]
    seeded = carry_floor([train(eta_s=150)], previous, elapsed_s=30)
    assert seeded[0].progress_floor == pytest.approx(0.25)


def test_unmatched_keys_get_no_floor():
    previous = [train(eta_s=30, key="line-1|0|b|0")]
    seeded = carry_floor([train(eta_s=120, key="line-1|0|c|0")], previous, elapsed_s=30)
    assert seeded[0].progress_floor == 0.0


def test_a_train_that_leaves_the_feed_does_not_coast():
    previous = [train(eta_s=30)]
    assert carry_floor([], previous, elapsed_s=30) == []
