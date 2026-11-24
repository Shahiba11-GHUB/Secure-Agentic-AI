"""Deterministic graph search, independent of security scenario details."""
from __future__ import annotations

import heapq
import math
from collections import deque
from dataclasses import dataclass
from itertools import count
from time import perf_counter
from typing import Callable, Hashable, Iterable, Protocol


class SearchProblem(Protocol):
    initial_state: Hashable

    def is_goal(self, state: Hashable) -> bool: ...
    def successors(self, state: Hashable) -> Iterable[tuple[str, Hashable, float]]: ...
    def heuristic(self, state: Hashable) -> float: ...


@dataclass(frozen=True)
class SearchResult:
    algorithm: str
    goal_reached: bool
    actions: tuple[str, ...]
    states: tuple[Hashable, ...]
    total_cost: float | None
    nodes_expanded: int
    nodes_generated: int
    frontier_peak: int
    elapsed_seconds: float


@dataclass(frozen=True)
class _Node:
    state: Hashable
    cost: float = 0.0
    parent: _Node | None = None
    action: str | None = None


def search(
    problem: SearchProblem,
    algorithm: str = "astar",
    *,
    heuristic: Callable[[Hashable], float] | None = None,
    on_expand: Callable[[Hashable], None] | None = None,
) -> SearchResult:
    """Run BFS, UCS, Greedy, or A* with stable insertion-order tie breaking.

    BFS/Greedy keep the first discovery of each state. UCS/A* retain cheaper
    paths, skip stale queue entries, and reopen states on an improvement. A*
    needs an admissible nonnegative heuristic (zero at goals) for optimality.
    The default is the problem's heuristic; pass lambda state: 0 for a baseline.

    Expanded counts non-goal states whose successors are examined. Generated
    counts successors yielded before duplicate filtering, excluding the root.
    Frontier peak counts queue entries, including stale entries in cost search.
    """
    if algorithm not in {"bfs", "ucs", "greedy", "astar"}:
        raise ValueError(f"Unknown algorithm: {algorithm}")
    started = perf_counter()
    estimate = heuristic if heuristic is not None else problem.heuristic
    serial = count()
    root = _Node(problem.initial_state)
    fifo = deque()
    heap = []
    visited = {root.state}
    best_cost = {root.state: 0.0}
    expanded = generated = 0
    peak = 1

    def push(node: _Node) -> None:
        if algorithm == "bfs":
            fifo.append(node)
            return
        h = estimate(node.state) if algorithm in {"greedy", "astar"} else 0.0
        if math.isnan(h) or h < 0:
            raise ValueError("Heuristic values must be nonnegative and not NaN")
        priority = h if algorithm == "greedy" else node.cost + h
        heapq.heappush(heap, (priority, next(serial), node))

    def finish(node: _Node | None) -> SearchResult:
        actions, states = [], []
        cursor = node
        while cursor is not None:
            states.append(cursor.state)
            if cursor.action is not None:
                actions.append(cursor.action)
            cursor = cursor.parent
        return SearchResult(
            algorithm, node is not None, tuple(reversed(actions)), tuple(reversed(states)),
            node.cost if node is not None else None, expanded, generated, peak,
            perf_counter() - started,
        )

    push(root)
    while fifo or heap:
        node = fifo.popleft() if algorithm == "bfs" else heapq.heappop(heap)[2]
        if algorithm in {"ucs", "astar"} and node.cost > best_cost[node.state]:
            continue
        if problem.is_goal(node.state):
            return finish(node)
        expanded += 1
        if on_expand is not None:
            on_expand(node.state)
        for action, next_state, step_cost in problem.successors(node.state):
            generated += 1
            if not math.isfinite(step_cost) or step_cost < 0:
                raise ValueError("Search requires finite nonnegative action costs")
            cost = node.cost + step_cost
            if not math.isfinite(cost):
                raise ValueError("Accumulated path cost overflowed")
            if algorithm in {"ucs", "astar"}:
                if cost >= best_cost.get(next_state, math.inf):
                    continue
                best_cost[next_state] = cost
            else:
                if next_state in visited:
                    continue
                visited.add(next_state)
            push(_Node(next_state, cost, node, action))
            peak = max(peak, len(fifo) + len(heap))
    return finish(None)


def bfs(problem: SearchProblem, **kwargs) -> SearchResult:
    return search(problem, "bfs", **kwargs)


def ucs(problem: SearchProblem, **kwargs) -> SearchResult:
    return search(problem, "ucs", **kwargs)


def greedy_best_first(problem: SearchProblem, **kwargs) -> SearchResult:
    return search(problem, "greedy", **kwargs)


def astar(problem: SearchProblem, **kwargs) -> SearchResult:
    return search(problem, "astar", **kwargs)
