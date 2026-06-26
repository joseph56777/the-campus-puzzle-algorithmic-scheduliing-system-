# University Timetable Scheduling System

This project implements an advanced algorithm solution for university timetable scheduling. It assigns classes to available rooms and timeslots while respecting professor availability, student group clashes, room capacity, and room double-booking rules.

The program is designed as a clear academic project: the data is stored in JSON, the algorithm logic is separated into different Python modules, and the final output explains the scheduled classes, unscheduled classes, total wasted capacity, and validation status.

## Project Goal

The main goal is to create a feasible timetable with minimum room-capacity waste. A good schedule should:

- place as many classes as possible,
- avoid professor clashes,
- avoid student group clashes,
- avoid assigning two classes to the same room at the same time,
- assign each class to a room with enough seats,
- reduce empty seats as much as possible.

## Input Data

The input file is:

```text
data/constraints.json
```

It contains four main sections:

```json
{
  "timeslots": [],
  "rooms": [],
  "classes": [],
  "student_groups": []
}
```

### Data Summary

The project data contains:

- 11 timeslots
- 16 rooms
- 38 classes
- 19 professors
- 12 student groups

## Project Structure

```text
josp 603/
├── README.md
├── conflict_graph.png
├── data/
│   └── constraints.json
└── src/
    ├── models.py
    ├── utils.py
    ├── greedy_solver.py
    ├── graph_engine.py
    ├── optimizer.py
    ├── backtracker.py
    └── main.py
```

## File Explanation

| File | Purpose |
|---|---|
| `models.py` | Defines the main data objects: class, room, student group, schedule entry, and graph statistics. |
| `utils.py` | Loads JSON data, validates input, checks hard constraints, calculates waste, and prepares readable summaries. |
| `greedy_solver.py` | Builds a fast baseline timetable using a scored greedy placement method. |
| `graph_engine.py` | Creates the conflict graph and assigns timeslots using DSATUR graph colouring. |
| `optimizer.py` | Assigns rooms using dynamic programming when possible and greedy assignment when the room set is large. |
| `backtracker.py` | Uses recursive search to place remaining unresolved classes. |
| `main.py` | Runs the full pipeline and prints the final timetable report. |

## Algorithms Used

### 1. Greedy Scheduling

The greedy solver gives a fast initial timetable. It sorts classes by difficulty, checks all valid room-timeslot combinations, and selects the placement with a good balance between low wasted capacity and fair timeslot usage.

This stage is useful because it quickly shows how many classes can be placed before the more advanced stages run.

### 2. Conflict Graph

The graph engine represents every class as a node. An edge is added between two nodes if the two classes cannot happen at the same time. A conflict can happen because:

- both classes have the same professor, or
- both classes are attended by the same student group.

This makes the scheduling problem easier to understand visually and mathematically.

### 3. DSATUR Graph Colouring

DSATUR assigns colours to graph nodes. In this project, colours are converted into timeslots. The algorithm always tries to choose a colour that is not used by neighbouring conflict nodes.

The main idea is:

1. Choose the most constrained class first.
2. Assign the earliest possible safe timeslot.
3. Repeat until all possible classes receive a timeslot.

This helps prevent professor and student group clashes.

### 4. Dynamic Programming Room Optimizer

After timeslots are selected, each class still needs a room. The dynamic programming optimizer finds room assignments with minimum wasted capacity for each timeslot.

For example, if a class has 43 students, a 45-seat room is better than an 80-seat room because it wastes fewer seats.

The optimizer uses exact dynamic programming for suitable room counts and uses a faster greedy fallback when the instance becomes too large.

### 5. Backtracking

Some classes may remain unresolved after graph colouring and room optimization. The backtracker tries to place those classes using recursive search.

It improves efficiency by:

- choosing the hardest class first,
- skipping rooms that are too small,
- rejecting invalid placements early,
- trying low-waste room choices first.

## Hard Constraints

The final timetable is valid only if all these constraints are satisfied:

1. A professor cannot teach two classes at the same time.
2. A student group cannot attend two classes at the same time.
3. A room cannot contain two classes at the same time.
4. A room must have enough capacity for the class.

The validation step at the end of the program checks these rules again before printing the final result.

## How to Run

### Run in PyCharm

1. Open the `josp 603` folder in PyCharm.
2. Open `src/main.py`.
3. Right-click inside the file.
4. Click **Run 'main'**.

### Run in Terminal

From the project folder, run:

```bash
python src/main.py
```

If your system uses Python 3 as `python3`, run:

```bash
python3 src/main.py
```

## Expected Output

The program prints:

- input summary,
- algorithm stage results,
- validation status,
- scheduled classes,
- total scheduled classes,
- total unscheduled classes,
- total wasted capacity,
- placement success rate.

Example summary:

```text
Total scheduled classes: 38
Total unscheduled classes: 0
Total wasted capacity: 116 seats
Placement success rate: 100.0%
[Validation] All hard constraints satisfied.
```

## Conflict Graph Image

The file `conflict_graph.png` shows the class conflict graph. In the graph, each node is a class and each edge means the connected classes cannot be scheduled at the same time.

If `matplotlib` or `networkx` is not installed, the program still runs. Only the image export step is skipped.

## Why This Solution Is Suitable

This project uses more than one algorithm because timetable scheduling has different sub-problems:

- greedy method for a quick baseline,
- graph colouring for conflict-free timeslots,
- dynamic programming for room optimization,
- backtracking for unresolved classes.

This combination gives a practical, explainable, and academically strong solution for an advanced algorithms project.
