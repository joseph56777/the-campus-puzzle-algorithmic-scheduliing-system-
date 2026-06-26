"""Recursive backtracker for classes still not scheduled.

The graph + DP stages normally schedule almost everything.  This file gives
the project a final completeness layer: if a class is left over, the search
tries valid placements using pruning so the program still produces the best
possible final timetable.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from models import ClassMap, ClassUnit, GroupMap, RoomMap, ScheduleEntry, ScheduleMap
from utils import is_valid_placement


MAX_LOG_LINES = 80


def _log(logs: List[str], message: str) -> None:
    """Avoid flooding the console when the data set becomes large."""
    if len(logs) < MAX_LOG_LINES:
        logs.append(message)


def _candidate_placements(
    cls: ClassUnit,
    timeslots: List[str],
    rooms: RoomMap,
    classes: ClassMap,
    groups: GroupMap,
    schedule: ScheduleMap,
) -> List[ScheduleEntry]:
    """Return valid placements ordered by smallest waste first."""
    candidates: List[ScheduleEntry] = []

    for timeslot in timeslots:
        for room in sorted(rooms.values(), key=lambda room: (room.capacity, room.room_id)):
            if not room.can_fit(cls):
                continue

            entry = ScheduleEntry(
                class_id=cls.class_id,
                timeslot=timeslot,
                room_id=room.room_id,
                waste=room.waste_for(cls),
            )
            valid, _reason = is_valid_placement(entry, classes, rooms, groups, schedule)
            if valid:
                candidates.append(entry)

    return sorted(candidates, key=lambda entry: (entry.waste, entry.timeslot, entry.room_id))


def _select_next_class(
    remaining: List[ClassUnit],
    timeslots: List[str],
    classes: ClassMap,
    rooms: RoomMap,
    groups: GroupMap,
    schedule: ScheduleMap,
) -> Tuple[ClassUnit, List[ScheduleEntry]]:
    """Minimum Remaining Values heuristic.

    The next class chosen is the one with the fewest currently valid places.
    This is a standard backtracking improvement because it detects dead ends
    earlier than a simple left-to-right order.
    """
    best_class = remaining[0]
    best_candidates = _candidate_placements(best_class, timeslots, rooms, classes, groups, schedule)

    for class_unit in remaining[1:]:
        candidates = _candidate_placements(class_unit, timeslots, rooms, classes, groups, schedule)
        if len(candidates) < len(best_candidates):
            best_class = class_unit
            best_candidates = candidates
        elif len(candidates) == len(best_candidates) and class_unit.students > best_class.students:
            best_class = class_unit
            best_candidates = candidates

    return best_class, best_candidates


def _backtrack(
    remaining: List[ClassUnit],
    schedule: ScheduleMap,
    timeslots: List[str],
    classes: ClassMap,
    rooms: RoomMap,
    groups: GroupMap,
    unresolved: Dict[str, str],
    logs: List[str],
) -> bool:
    """Depth-first search with MRV class selection and early pruning."""
    if not remaining:
        return True

    current_class, candidates = _select_next_class(remaining, timeslots, classes, rooms, groups, schedule)
    next_remaining = [class_unit for class_unit in remaining if class_unit.class_id != current_class.class_id]

    if not candidates:
        unresolved[current_class.class_id] = "No valid placement after checking room, professor, and group constraints"
        _log(logs, f"Could not schedule {current_class.class_id}: no valid candidate")
        return _backtrack(next_remaining, schedule, timeslots, classes, rooms, groups, unresolved, logs)

    for entry in candidates:
        schedule[current_class.class_id] = entry
        _log(logs, f"Placed {current_class.class_id} at {entry.timeslot} in {entry.room_id}")

        if _backtrack(next_remaining, schedule, timeslots, classes, rooms, groups, unresolved, logs):
            return True

        del schedule[current_class.class_id]
        _log(logs, f"Backtracked {current_class.class_id} from {entry.timeslot}/{entry.room_id}")

    unresolved[current_class.class_id] = "All candidate placements led to conflicts later"
    return _backtrack(next_remaining, schedule, timeslots, classes, rooms, groups, unresolved, logs)


def backtrack_unscheduled(
    partial_schedule: ScheduleMap,
    unscheduled_classes: List[ClassUnit],
    timeslots: List[str],
    classes: ClassMap,
    rooms: RoomMap,
    groups: GroupMap,
) -> Tuple[ScheduleMap, List[str], Dict[str, str]]:
    """Try to insert leftover classes into an already valid partial schedule."""
    schedule = dict(partial_schedule)
    logs: List[str] = []
    unresolved: Dict[str, str] = {}

    remaining = sorted(unscheduled_classes, key=lambda class_unit: class_unit.priority_key())
    _backtrack(remaining, schedule, timeslots, classes, rooms, groups, unresolved, logs)

    if not logs:
        logs.append("No leftover classes were sent to the backtracker.")
    elif len(logs) == MAX_LOG_LINES:
        logs.append("Log shortened because many search steps were generated.")

    return schedule, logs, unresolved
