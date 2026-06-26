"""Shared utility functions for loading, validating, and reporting data.

Every algorithm file uses this module for the common hard-constraint rules.
Keeping these checks in one place makes the project easier to explain in a
presentation and prevents the greedy solver, optimizer, and backtracker from
accidentally using different rules.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

from models import (
    ClassMap,
    ClassUnit,
    GroupMap,
    Room,
    RoomMap,
    ScheduleEntry,
    ScheduleMap,
    StudentGroup,
)


ClassGroupIndex = Dict[str, set[str]]


def _require_keys(item: dict, required: Sequence[str], section: str) -> None:
    """Raise a helpful error if a JSON object is missing required fields."""
    missing = [key for key in required if key not in item]
    if missing:
        raise ValueError(f"{section} entry is missing required key(s): {', '.join(missing)}")


def _check_unique(values: Iterable[str], label: str) -> None:
    """Validate that IDs are unique before building dictionaries."""
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    if duplicates:
        duplicate_text = ", ".join(sorted(duplicates))
        raise ValueError(f"Duplicate {label} id(s) found: {duplicate_text}")


def load_constraints(path: Path) -> Tuple[List[str], ClassMap, RoomMap, GroupMap]:
    """Load and validate the scheduling problem from ``constraints.json``.

    The function expects this JSON schema:
    ``timeslots``, ``rooms``, ``classes``, and ``student_groups``.  The
    validation also gives PyCharm a clear message if the JSON data is edited
    incorrectly.
    """
    if not path.exists():
        raise FileNotFoundError(f"Could not find constraints file: {path}")

    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    for section in ("timeslots", "rooms", "classes", "student_groups"):
        if section not in data:
            raise ValueError(f"constraints.json is missing the '{section}' section")

    timeslots = [str(timeslot) for timeslot in data["timeslots"]]
    if not timeslots:
        raise ValueError("At least one timeslot is required")
    _check_unique(timeslots, "timeslot")

    _check_unique((str(item.get("id")) for item in data["classes"]), "class")
    _check_unique((str(item.get("id")) for item in data["rooms"]), "room")
    _check_unique((str(item.get("group_id")) for item in data["student_groups"]), "student group")

    classes: ClassMap = {}
    for item in data["classes"]:
        _require_keys(item, ("id", "students", "professor"), "classes")
        students = int(item["students"])
        if students <= 0:
            raise ValueError(f"Class {item['id']} must have a positive student count")
        classes[str(item["id"])] = ClassUnit(
            class_id=str(item["id"]),
            students=students,
            professor=str(item["professor"]),
        )

    rooms: RoomMap = {}
    for item in data["rooms"]:
        _require_keys(item, ("id", "capacity"), "rooms")
        capacity = int(item["capacity"])
        if capacity <= 0:
            raise ValueError(f"Room {item['id']} must have a positive capacity")
        rooms[str(item["id"])] = Room(room_id=str(item["id"]), capacity=capacity)

    groups: GroupMap = {}
    for item in data["student_groups"]:
        _require_keys(item, ("group_id", "class_ids"), "student_groups")
        group_classes = {str(class_id) for class_id in item["class_ids"]}
        unknown = sorted(group_classes - set(classes.keys()))
        if unknown:
            raise ValueError(
                f"Student group {item['group_id']} references unknown class id(s): "
                f"{', '.join(unknown)}"
            )
        groups[str(item["group_id"])] = StudentGroup(
            group_id=str(item["group_id"]),
            class_ids=group_classes,
        )

    max_class_size = max(cls.students for cls in classes.values())
    max_room_capacity = max(room.capacity for room in rooms.values())
    if max_class_size > max_room_capacity:
        raise ValueError(
            "At least one class is larger than every room. "
            f"Largest class={max_class_size}, largest room={max_room_capacity}."
        )

    return timeslots, classes, rooms, groups


def build_class_group_index(groups: GroupMap) -> ClassGroupIndex:
    """Create a fast lookup: class id -> set of student group ids."""
    index: ClassGroupIndex = {}
    for group in groups.values():
        for class_id in group.class_ids:
            index.setdefault(class_id, set()).add(group.group_id)
    return index


def get_class_groups(class_id: str, groups: GroupMap) -> List[str]:
    """Return the ids of every student group that contains this class."""
    index = build_class_group_index(groups)
    return sorted(index.get(class_id, set()))


def conflict_reason(class_a: ClassUnit, class_b: ClassUnit, groups: GroupMap) -> str | None:
    """Return the reason two classes conflict, or ``None`` if they do not."""
    if class_a.professor == class_b.professor:
        return f"same professor ({class_a.professor})"

    index = build_class_group_index(groups)
    shared_groups = sorted(index.get(class_a.class_id, set()) & index.get(class_b.class_id, set()))
    if shared_groups:
        return f"shared student group ({', '.join(shared_groups)})"
    return None


def class_conflicts(class_a: ClassUnit, class_b: ClassUnit, groups: GroupMap) -> bool:
    """True if two classes cannot be scheduled in the same timeslot."""
    return conflict_reason(class_a, class_b, groups) is not None


def is_valid_placement(
    entry: ScheduleEntry,
    classes: ClassMap,
    rooms: RoomMap,
    groups: GroupMap,
    current_schedule: ScheduleMap,
) -> Tuple[bool, str]:
    """Check whether a proposed placement satisfies all hard constraints."""
    cls = classes.get(entry.class_id)
    if cls is None:
        return False, f"Unknown class '{entry.class_id}'"

    room = rooms.get(entry.room_id)
    if room is None:
        return False, f"Unknown room '{entry.room_id}'"

    if not room.can_fit(cls):
        return False, (
            f"Room {room.room_id} capacity ({room.capacity}) is smaller than "
            f"class size ({cls.students})"
        )

    for other in current_schedule.values():
        if other.timeslot != entry.timeslot:
            continue

        other_cls = classes[other.class_id]
        if other.room_id == entry.room_id:
            return False, f"Room {entry.room_id} already booked by {other.class_id}"

        reason = conflict_reason(cls, other_cls, groups)
        if reason is not None:
            return False, f"Conflict with {other.class_id}: {reason}"

    return True, "OK"


def compute_waste(entry: ScheduleEntry, classes: ClassMap, rooms: RoomMap) -> int:
    """Compute the unused seat count for one schedule entry."""
    return rooms[entry.room_id].waste_for(classes[entry.class_id])


def schedule_to_entries(schedule: ScheduleMap) -> List[ScheduleEntry]:
    """Return schedule rows in a stable order for consistent output."""
    return [schedule[class_id] for class_id in sorted(schedule.keys())]


def summarize_inputs(timeslots: List[str], classes: ClassMap, rooms: RoomMap, groups: GroupMap) -> Dict[str, int]:
    """Small helper used by main.py for a clean project summary."""
    professors = {class_unit.professor for class_unit in classes.values()}
    return {
        "timeslots": len(timeslots),
        "rooms": len(rooms),
        "classes": len(classes),
        "professors": len(professors),
        "student_groups": len(groups),
    }
