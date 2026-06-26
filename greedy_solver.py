"""Balanced greedy baseline solver.

This file is intentionally kept separate from the exact optimizer because the
project demonstrates more than one algorithmic idea.  The greedy solver is the
fast first attempt: it places the hardest classes first and chooses the best
available room/timeslot according to a scoring function.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from models import ClassMap, ClassUnit, GroupMap, Room, RoomMap, ScheduleEntry, ScheduleMap
from utils import compute_waste, get_class_groups, is_valid_placement


@dataclass(frozen=True)
class PlacementOption:
    """Candidate placement used internally by the greedy heuristic."""

    entry: ScheduleEntry
    score: tuple[int, int, int, str]


def _timeslot_load(schedule: ScheduleMap, timeslot: str) -> int:
    """Count how many classes are already scheduled in a timeslot."""
    return sum(1 for entry in schedule.values() if entry.timeslot == timeslot)


def _professor_load(schedule: ScheduleMap, classes: ClassMap, professor: str) -> int:
    """Count how many classes of a professor are already placed."""
    return sum(1 for entry in schedule.values() if classes[entry.class_id].professor == professor)


def _candidate_rooms(cls: ClassUnit, rooms: RoomMap) -> List[Room]:
    """Return only rooms that can hold the class, ordered by tightest fit."""
    feasible = [room for room in rooms.values() if room.can_fit(cls)]
    return sorted(feasible, key=lambda room: (room.waste_for(cls), room.capacity, room.room_id))


def _score_candidate(
    entry: ScheduleEntry,
    cls: ClassUnit,
    schedule: ScheduleMap,
    classes: ClassMap,
    groups: GroupMap,
) -> tuple[int, int, int, str]:
    """Create a readable greedy score.

    Lower score is better.  The order is:
    1. Lower room waste.
    2. Less crowded timeslot.
    3. Fewer already placed classes for the same professor.
    4. Deterministic room id tie-break.
    """
    group_count = len(get_class_groups(cls.class_id, groups))
    return (
        entry.waste,
        _timeslot_load(schedule, entry.timeslot),
        _professor_load(schedule, classes, cls.professor) + group_count,
        entry.room_id,
    )


def _best_greedy_placement(
    cls: ClassUnit,
    timeslots: List[str],
    rooms: RoomMap,
    classes: ClassMap,
    groups: GroupMap,
    schedule: ScheduleMap,
) -> Tuple[ScheduleEntry | None, str]:
    """Find the best valid greedy placement for a single class."""
    best: PlacementOption | None = None
    last_reason = "No feasible room/timeslot found"

    for timeslot in timeslots:
        for room in _candidate_rooms(cls, rooms):
            entry = ScheduleEntry(
                class_id=cls.class_id,
                timeslot=timeslot,
                room_id=room.room_id,
                waste=room.waste_for(cls),
            )
            valid, reason = is_valid_placement(entry, classes, rooms, groups, schedule)
            if not valid:
                last_reason = reason
                continue

            option = PlacementOption(
                entry=entry,
                score=_score_candidate(entry, cls, schedule, classes, groups),
            )
            if best is None or option.score < best.score:
                best = option

    if best is None:
        return None, last_reason
    return best.entry, "OK"


def greedy_schedule(
    timeslots: List[str],
    classes: ClassMap,
    rooms: RoomMap,
    groups: GroupMap,
) -> Tuple[ScheduleMap, List[Tuple[ClassUnit, str]]]:
    """Build a quick valid schedule using a balanced greedy heuristic.

    The solver checks valid candidate placements and chooses the one with the
    smallest room waste while also keeping timeslot load balanced.  This keeps
    the method easy to explain and useful as a fast baseline.
    """
    sorted_classes = sorted(classes.values(), key=lambda class_unit: class_unit.priority_key())
    schedule: ScheduleMap = {}
    unscheduled: List[Tuple[ClassUnit, str]] = []

    for cls in sorted_classes:
        placement, reason = _best_greedy_placement(
            cls=cls,
            timeslots=timeslots,
            rooms=rooms,
            classes=classes,
            groups=groups,
            schedule=schedule,
        )

        if placement is None:
            unscheduled.append((cls, reason))
            continue

        placement = ScheduleEntry(
            class_id=placement.class_id,
            timeslot=placement.timeslot,
            room_id=placement.room_id,
            waste=compute_waste(placement, classes, rooms),
        )
        schedule[cls.class_id] = placement

    return schedule, unscheduled
