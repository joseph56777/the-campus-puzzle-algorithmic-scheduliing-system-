"""Executable pipeline for the advanced algorithm timetable project.

Run this file in PyCharm with:
    python src/main.py

The code follows a clear four-stage algorithm design:
    1. Greedy baseline for a fast initial answer.
    2. Conflict graph + DSATUR colouring for timeslots.
    3. Dynamic programming optimizer for room assignment.
    4. Backtracking for any remaining unscheduled classes.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Tuple

try:
    import matplotlib.pyplot as plt
    import networkx as nx
    _GRAPHING_AVAILABLE = True
except ImportError:
    _GRAPHING_AVAILABLE = False

# PyCharm can run a file from different working directories.  This makes the
# imports stable whether the user runs from the root folder or from src/main.py.
SRC_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SRC_DIR.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from backtracker import backtrack_unscheduled
from graph_engine import build_conflict_graph, color_schedule, conflict_edges_with_reasons, graph_statistics
from greedy_solver import greedy_schedule
from models import ClassMap, GroupMap, RoomMap, ScheduleMap
import optimizer
from optimizer import optimize_room_assignments
from utils import compute_waste, is_valid_placement, load_constraints, schedule_to_entries, summarize_inputs


def _total_waste(schedule: ScheduleMap, classes: ClassMap, rooms: RoomMap) -> int:
    """Sum unused seats across all scheduled classes."""
    return sum(compute_waste(entry, classes, rooms) for entry in schedule.values())


def _validate_schedule(schedule: ScheduleMap, classes: ClassMap, rooms: RoomMap, groups: GroupMap) -> List[str]:
    """Validate the complete timetable using the same rules as the solvers."""
    violations: List[str] = []
    partial: ScheduleMap = {}
    for entry in schedule_to_entries(schedule):
        valid, reason = is_valid_placement(entry, classes, rooms, groups, partial)
        if valid:
            partial[entry.class_id] = entry
        else:
            violations.append(f"{entry.class_id}: {reason}")
    return violations


def _build_report(schedule: ScheduleMap, unresolved: Dict[str, str]) -> List[str]:
    """Build final output rows in a simple readable format."""
    lines = [entry.report_text() for entry in schedule_to_entries(schedule)]
    for class_id in sorted(unresolved.keys()):
        lines.append(f"Unscheduled {class_id} N/A N/A")
    return lines


def _draw_conflict_graph(classes: ClassMap, groups: GroupMap, output_path: Path) -> None:
    """Save a visual conflict graph for the report folder.

    This step is optional.  If PyCharm does not have matplotlib/networkx
    installed, the algorithm still runs and the image step is skipped.
    """
    if not _GRAPHING_AVAILABLE:
        print("[Conflict graph] Optional packages missing; image export skipped.")
        print("                 Install matplotlib and networkx if you need the PNG.")
        return

    graph = nx.Graph()
    for class_id in classes:
        graph.add_node(class_id)

    for first_id, second_id, reason in conflict_edges_with_reasons(classes, groups):
        graph.add_edge(first_id, second_id, reason=reason)

    plt.figure(figsize=(14, 10))
    pos = nx.spring_layout(graph, seed=42, k=0.75)

    nx.draw_networkx_nodes(graph, pos, node_size=900, edgecolors="black")

    edge_colours = []
    for first_id, second_id in graph.edges():
        reason = graph[first_id][second_id].get("reason", "")
        edge_colours.append("red" if "professor" in reason else "green")

    nx.draw_networkx_edges(graph, pos, width=1.6, edge_color=edge_colours, alpha=0.65)
    nx.draw_networkx_labels(graph, pos, font_size=8, font_family="sans-serif")

    plt.title("Conflict Graph for University Timetable Dataset", fontsize=14)
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"[Conflict graph] Saved to {output_path.resolve()}")


def _print_input_summary(timeslots: List[str], classes: ClassMap, rooms: RoomMap, groups: GroupMap) -> None:
    """Print the dataset size for presentation and report evidence."""
    summary = summarize_inputs(timeslots, classes, rooms, groups)
    print("Input summary:")
    print(f"  Timeslots: {summary['timeslots']}")
    print(f"  Rooms: {summary['rooms']}")
    print(f"  Classes: {summary['classes']}")
    print(f"  Professors: {summary['professors']}")
    print(f"  Student groups: {summary['student_groups']}\n")

    largest_class = max(classes.values(), key=lambda class_unit: class_unit.students)
    largest_room = max(rooms.values(), key=lambda room: room.capacity)
    print("Capacity check:")
    print(f"  Largest class: {largest_class.class_id} with {largest_class.students} students")
    print(f"  Largest room: {largest_room.room_id} with {largest_room.capacity} seats\n")


def run_pipeline(timeslots: List[str], classes: ClassMap, rooms: RoomMap, groups: GroupMap) -> Tuple[ScheduleMap, Dict[str, str], int]:
    """Run all algorithm stages and return the final timetable."""
    print("Algorithm stages:")

    # Stage 1: Greedy baseline.
    greedy_result, greedy_unscheduled = greedy_schedule(timeslots, classes, rooms, groups)
    greedy_waste = _total_waste(greedy_result, classes, rooms)
    print(f"  1. Greedy solver     -> scheduled {len(greedy_result)}, "
          f"unscheduled {len(greedy_unscheduled)}, waste {greedy_waste}")

    # Stage 2: Graph colouring for conflict-free timeslots.
    graph = build_conflict_graph(classes, groups)
    stats = graph_statistics(graph)
    timeslot_map, overcolored = color_schedule(timeslots, classes, groups, algorithm="dsatur")
    print(f"  2. Graph engine      -> nodes {stats.nodes}, edges {stats.edges}, "
          f"max degree {stats.max_degree}, overcolored {len(overcolored)}")

    # Stage 3: DP optimizer for rooms.
    dp_schedule, dp_waste = optimize_room_assignments(timeslot_map, classes, rooms, use_dp=True, dp_room_limit=20)
    dp_scheduled_ids = set(dp_schedule.keys())
    dp_unplaced = [classes[class_id] for class_id in timeslot_map if class_id not in dp_scheduled_ids]
    opt_stats = optimizer.LAST_OPTIMIZER_STATS
    print(f"  3. DP optimizer      -> placed {len(dp_schedule)}, waste {dp_waste}, "
          f"exact DP slots {opt_stats.exact_dp_slots}, unplaced {len(dp_unplaced)}")

    # Stage 4: Backtracking for any unresolved classes.
    unresolved_classes = [classes[class_id] for class_id in overcolored] + dp_unplaced
    final_schedule, logs, unresolved = backtrack_unscheduled(
        partial_schedule=dp_schedule,
        unscheduled_classes=unresolved_classes,
        timeslots=timeslots,
        classes=classes,
        rooms=rooms,
        groups=groups,
    )
    print(f"  4. Backtracker       -> checked {len(unresolved_classes)} leftover classes, "
          f"still unresolved {len(unresolved)}")

    print("\nBacktracker notes:")
    for log in logs:
        print(f"  - {log}")

    final_waste = _total_waste(final_schedule, classes, rooms)
    print(f"\nFinal schedule summary: scheduled {len(final_schedule)}, "
          f"unscheduled {len(unresolved)}, waste {final_waste}\n")
    return final_schedule, unresolved, final_waste


def main() -> None:
    """Program entry point."""
    constraints_path = PROJECT_ROOT / "data" / "constraints.json"
    print(f"Loading constraints from {constraints_path}\n")

    timeslots, classes, rooms, groups = load_constraints(constraints_path)
    _print_input_summary(timeslots, classes, rooms, groups)

    _draw_conflict_graph(classes, groups, PROJECT_ROOT / "conflict_graph.png")
    print()

    final_schedule, unresolved, final_waste = run_pipeline(timeslots, classes, rooms, groups)

    violations = _validate_schedule(final_schedule, classes, rooms, groups)
    if violations:
        print("[Validation errors]")
        for violation in violations:
            print(f"  {violation}")
    else:
        print("[Validation] All hard constraints satisfied.")

    print("\n" + "-" * 70)
    for line in _build_report(final_schedule, unresolved):
        print(line)
    print("-" * 70)

    total_classes = len(classes)
    scheduled_count = len(final_schedule)
    unscheduled_count = len(unresolved)
    placement_rate = scheduled_count / total_classes if total_classes else 0

    print(f"\nTotal scheduled classes: {scheduled_count}")
    print(f"Total unscheduled classes: {unscheduled_count}")
    print(f"Total wasted capacity: {final_waste} seats")
    print(f"Placement success rate: {placement_rate:.1%}")


if __name__ == "__main__":
    main()
