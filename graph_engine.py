"""Conflict graph construction and graph-colouring timeslot assignment.

DSATUR is a good fit for timetable problems because it always picks the class
that is currently most constrained by already-coloured neighbours.  The colour
assigned to each class is later mapped to a real timetable timeslot.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple

from models import ClassMap, GroupMap
from utils import class_conflicts, conflict_reason


Graph = Dict[str, Set[str]]


@dataclass(frozen=True)
class GraphStats:
    """Small summary that main.py can print for explanation."""

    nodes: int
    edges: int
    max_degree: int
    isolated_nodes: int


def build_conflict_graph(classes: ClassMap, groups: GroupMap) -> Graph:
    """Build an undirected graph where edges mean timetable conflicts."""
    graph: Graph = defaultdict(set)
    class_ids = sorted(classes.keys())

    for class_id in class_ids:
        graph.setdefault(class_id, set())

    for i, first_id in enumerate(class_ids):
        for second_id in class_ids[i + 1:]:
            if class_conflicts(classes[first_id], classes[second_id], groups):
                graph[first_id].add(second_id)
                graph[second_id].add(first_id)

    return dict(graph)


def graph_statistics(graph: Graph) -> GraphStats:
    """Return basic graph values for the console report."""
    degrees = [len(neighbours) for neighbours in graph.values()]
    edges = sum(degrees) // 2
    return GraphStats(
        nodes=len(graph),
        edges=edges,
        max_degree=max(degrees, default=0),
        isolated_nodes=sum(1 for degree in degrees if degree == 0),
    )


def conflict_edges_with_reasons(classes: ClassMap, groups: GroupMap) -> List[Tuple[str, str, str]]:
    """Return conflict edges with human-readable reasons for visualisation."""
    rows: List[Tuple[str, str, str]] = []
    class_ids = sorted(classes.keys())
    for i, first_id in enumerate(class_ids):
        for second_id in class_ids[i + 1:]:
            reason = conflict_reason(classes[first_id], classes[second_id], groups)
            if reason is not None:
                rows.append((first_id, second_id, reason))
    return rows


def _saturation_degree(node: str, graph: Graph, coloring: Dict[str, int]) -> int:
    """Number of different colours already used by coloured neighbours."""
    return len({coloring[nbr] for nbr in graph[node] if nbr in coloring})


def dsatur_coloring(graph: Graph) -> Dict[str, int]:
    """Colour the conflict graph using the DSATUR heuristic.

    Selection rule:
        Pick the uncoloured class with the highest saturation degree.  Ties
        are resolved by ordinary degree and then class id.  This usually uses
        fewer colours than a simple first-order greedy colouring.
    """
    uncolored = set(graph.keys())
    coloring: Dict[str, int] = {}

    while uncolored:
        node = max(
            uncolored,
            key=lambda candidate: (
                _saturation_degree(candidate, graph, coloring),
                len(graph[candidate]),
                candidate,
            ),
        )

        used_colours = {coloring[nbr] for nbr in graph[node] if nbr in coloring}
        colour = 0
        while colour in used_colours:
            colour += 1

        coloring[node] = colour
        uncolored.remove(node)

    return coloring


def welsh_powell(graph: Graph) -> Dict[str, int]:
    """Keep Welsh-Powell as a second algorithm for comparison/explanation."""
    sorted_nodes = sorted(graph.keys(), key=lambda node: (-len(graph[node]), node))
    coloring: Dict[str, int] = {}

    for node in sorted_nodes:
        used_colours = {coloring[nbr] for nbr in graph[node] if nbr in coloring}
        colour = 0
        while colour in used_colours:
            colour += 1
        coloring[node] = colour

    return coloring


def map_colors_to_timeslots(
    coloring: Dict[str, int],
    timeslots: List[str],
) -> Tuple[Dict[str, str], List[str]]:
    """Map colour numbers to real timeslot labels."""
    timeslot_map: Dict[str, str] = {}
    unplaced: List[str] = []

    for class_id, colour in sorted(coloring.items()):
        if colour < len(timeslots):
            timeslot_map[class_id] = timeslots[colour]
        else:
            unplaced.append(class_id)

    return timeslot_map, unplaced


def color_schedule(
    timeslots: List[str],
    classes: ClassMap,
    groups: GroupMap,
    algorithm: str = "dsatur",
) -> Tuple[Dict[str, str], List[str]]:
    """Build graph, colour it, and convert colours to timeslots."""
    graph = build_conflict_graph(classes, groups)
    if algorithm.lower() == "welsh-powell":
        coloring = welsh_powell(graph)
    else:
        coloring = dsatur_coloring(graph)
    return map_colors_to_timeslots(coloring, timeslots)
