"""Domain models for the university timetable scheduler.

The project uses a small, easy-to-understand data model because the focus
of the coursework is the algorithm pipeline.  The JSON file contains rooms,
classes, timeslots, and student groups.  These dataclasses convert that raw
JSON into typed Python objects so the greedy solver, graph engine, optimizer,
and backtracker can work with clean inputs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Set


@dataclass(frozen=True)
class ClassUnit:
    """A single class that must be placed into one timeslot and one room.

    Attributes:
        class_id: Unique code for the class, for example ``CS101``.
        students: Number of enrolled students.
        professor: Professor assigned to teach the class.
    """

    class_id: str
    students: int
    professor: str

    @property
    def size_category(self) -> str:
        """Return a human-friendly size label used in reports and sorting."""
        if self.students >= 75:
            return "large"
        if self.students >= 45:
            return "medium"
        return "small"

    def priority_key(self) -> tuple[int, str, str]:
        """Priority used by algorithms: larger classes are harder to place."""
        return (-self.students, self.professor, self.class_id)

    def __hash__(self) -> int:
        """Class identity is based on the class code."""
        return hash(self.class_id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ClassUnit):
            return NotImplemented
        return self.class_id == other.class_id


@dataclass(frozen=True)
class Room:
    """A physical room with fixed seating capacity."""

    room_id: str
    capacity: int

    def can_fit(self, class_unit: ClassUnit) -> bool:
        """True when the room has enough seats for the class."""
        return self.capacity >= class_unit.students

    def waste_for(self, class_unit: ClassUnit) -> int:
        """Number of unused seats if the class is placed in this room."""
        if not self.can_fit(class_unit):
            return 10**9
        return self.capacity - class_unit.students

    @property
    def capacity_category(self) -> str:
        """Simple room-size label for readable diagnostics."""
        if self.capacity >= 90:
            return "lecture hall"
        if self.capacity >= 50:
            return "standard room"
        return "seminar room"


@dataclass(frozen=True)
class StudentGroup:
    """A group/cohort of students that attends multiple classes together.

    If two classes belong to the same group, they cannot be scheduled at
    the same time because the students would have a timetable clash.
    """

    group_id: str
    class_ids: Set[str] = field(default_factory=set)

    def contains(self, class_id: str) -> bool:
        """Check if this group attends the given class."""
        return class_id in self.class_ids


@dataclass(frozen=True)
class ScheduleEntry:
    """One final placement in the timetable."""

    class_id: str
    timeslot: str
    room_id: str
    waste: int

    @property
    def is_perfect_fit(self) -> bool:
        return self.waste == 0

    def report_text(self) -> str:
        """Return the exact style of row used in the final output table."""
        if self.is_perfect_fit:
            fit_text = "Perfect Fit"
        else:
            seat_word = "seat" if self.waste == 1 else "seats"
            fit_text = f"Wasted {self.waste} {seat_word}"
        return f"Scheduled {self.class_id} {self.timeslot} {self.room_id} {fit_text}"


# Type aliases keep algorithm signatures short and readable.
ClassMap = Dict[str, ClassUnit]
RoomMap = Dict[str, Room]
GroupMap = Dict[str, StudentGroup]
ScheduleMap = Dict[str, ScheduleEntry]
