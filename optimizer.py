"""Room-assignment optimizer.

After the graph engine assigns classes to timeslots, this module chooses the
best room for each class inside every timeslot.  It uses an exact dynamic
programming method for normal-sized data and a safe greedy fallback if the
room count becomes very large.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from models import ClassMap, ClassUnit, Room, RoomMap, ScheduleEntry, ScheduleMap


@dataclass(frozen=True)
class OptimizerStats:
    """Diagnostic information used for final reporting."""

    timeslots_processed: int
    exact_dp_slots: int
    greedy_slots: int
    skipped_slots: int


LAST_OPTIMIZER_STATS = OptimizerStats(0, 0, 0, 0)


def _room_waste(class_unit: ClassUnit, room: Room) -> int:
    """Return wasted seats or a very large value when the class cannot fit."""
    return room.waste_for(class_unit)


def _prepare_room_list(rooms: RoomMap) -> List[Room]:
    """Sort rooms by capacity first, then id, for stable low-waste choices."""
    return sorted(rooms.values(), key=lambda room: (room.capacity, room.room_id))


def _dp_assign(classes: List[ClassUnit], rooms: List[Room]) -> Optional[List[Tuple[str, str]]]:
    """Exact subset-DP assignment for one timeslot.

    ``dp[mask]`` stores the minimum wasted capacity after assigning the first
    ``popcount(mask)`` classes using the rooms represented by the set bits in
    ``mask``.  This is exact, deterministic, and easy to explain as dynamic
    programming.
    """
    class_count = len(classes)
    room_count = len(rooms)

    if class_count == 0:
        return []
    if class_count > room_count:
        return None

    INF = 10**12
    state_count = 1 << room_count
    dp = [INF] * state_count
    parent: List[Optional[Tuple[int, int]]] = [None] * state_count
    dp[0] = 0

    for mask in range(state_count):
        if dp[mask] == INF:
            continue

        class_index = mask.bit_count()
        if class_index >= class_count:
            continue

        current_class = classes[class_index]
        for room_index, room in enumerate(rooms):
            if mask & (1 << room_index):
                continue
            if not room.can_fit(current_class):
                continue

            next_mask = mask | (1 << room_index)
            new_cost = dp[mask] + _room_waste(current_class, room)
            if new_cost < dp[next_mask]:
                dp[next_mask] = new_cost
                parent[next_mask] = (mask, room_index)

    best_mask: Optional[int] = None
    best_cost = INF
    for mask, cost in enumerate(dp):
        if mask.bit_count() == class_count and cost < best_cost:
            best_mask = mask
            best_cost = cost

    if best_mask is None or best_cost == INF:
        return None

    assignment: List[Tuple[str, str]] = [("", "")] * class_count
    mask = best_mask
    while parent[mask] is not None:
        previous_mask, room_index = parent[mask]
        class_index = previous_mask.bit_count()
        assignment[class_index] = (classes[class_index].class_id, rooms[room_index].room_id)
        mask = previous_mask

    return assignment


def _greedy_assign(classes: List[ClassUnit], rooms: List[Room]) -> Optional[List[Tuple[str, str]]]:
    """Fast fallback assignment for a single timeslot.

    The class with the largest size is assigned first, and each class gets
    the currently available room with the smallest possible waste.
    """
    if len(classes) > len(rooms):
        return None

    sorted_classes = sorted(classes, key=lambda class_unit: class_unit.priority_key())
    free_rooms = list(rooms)
    assignment: List[Tuple[str, str]] = []

    for class_unit in sorted_classes:
        feasible_rooms = [room for room in free_rooms if room.can_fit(class_unit)]
        if not feasible_rooms:
            return None

        chosen = min(feasible_rooms, key=lambda room: (room.waste_for(class_unit), room.capacity, room.room_id))
        assignment.append((class_unit.class_id, chosen.room_id))
        free_rooms.remove(chosen)

    return assignment


def _group_by_timeslot(timeslot_map: Dict[str, str], classes: ClassMap) -> Dict[str, List[ClassUnit]]:
    """Convert ``class_id -> timeslot`` into ``timeslot -> classes``."""
    grouped: Dict[str, List[ClassUnit]] = {}
    for class_id, timeslot in timeslot_map.items():
        grouped.setdefault(timeslot, []).append(classes[class_id])
    return grouped


def _make_schedule_entries(
    assignment: List[Tuple[str, str]],
    timeslot: str,
    classes: ClassMap,
    rooms: RoomMap,
) -> ScheduleMap:
    """Convert raw assignment pairs into ScheduleEntry objects."""
    rows: ScheduleMap = {}
    for class_id, room_id in assignment:
        class_unit = classes[class_id]
        room = rooms[room_id]
        rows[class_id] = ScheduleEntry(
            class_id=class_id,
            timeslot=timeslot,
            room_id=room_id,
            waste=room.waste_for(class_unit),
        )
    return rows


def optimize_room_assignments(
    timeslot_map: Dict[str, str],
    classes: ClassMap,
    rooms: RoomMap,
    use_dp: bool = True,
    dp_room_limit: int = 20,
) -> Tuple[ScheduleMap, int]:
    """Assign rooms to all coloured classes and minimize wasted capacity.

    The function returns the standard project output: a schedule dictionary and
    the total unused-seat count for the room assignments.
    """
    global LAST_OPTIMIZER_STATS

    classes_by_timeslot = _group_by_timeslot(timeslot_map, classes)
    room_list = _prepare_room_list(rooms)

    schedule: ScheduleMap = {}
    total_waste = 0
    exact_dp_slots = 0
    greedy_slots = 0
    skipped_slots = 0

    for timeslot in sorted(classes_by_timeslot.keys()):
        slot_classes = sorted(classes_by_timeslot[timeslot], key=lambda class_unit: class_unit.priority_key())

        if use_dp and len(room_list) <= dp_room_limit:
            assignment = _dp_assign(slot_classes, room_list)
            exact_dp_slots += 1
        else:
            assignment = _greedy_assign(slot_classes, room_list)
            greedy_slots += 1

        if assignment is None:
            skipped_slots += 1
            continue

        entries = _make_schedule_entries(assignment, timeslot, classes, rooms)
        schedule.update(entries)
        total_waste += sum(entry.waste for entry in entries.values())

    LAST_OPTIMIZER_STATS = OptimizerStats(
        timeslots_processed=len(classes_by_timeslot),
        exact_dp_slots=exact_dp_slots,
        greedy_slots=greedy_slots,
        skipped_slots=skipped_slots,
    )
    return schedule, total_waste
