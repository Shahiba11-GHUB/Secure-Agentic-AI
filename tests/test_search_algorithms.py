import math
import unittest

from search_algorithms import astar, bfs, greedy_best_first, search, ucs


class GraphProblem:
    def __init__(self, edges, goals=("G",), estimates=None, start="S"):
        self.edges = edges
        self.goals = set(goals)
        self.estimates = estimates or {}
        self.initial_state = start

    def is_goal(self, state):
        return state in self.goals

    def successors(self, state):
        return [(f"{state}->{target}", target, cost) for target, cost in self.edges.get(state, [])]

    def heuristic(self, state):
        return self.estimates.get(state, 0)


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.tradeoff = GraphProblem({"S": [("G", 9), ("A", 1)], "A": [("G", 1)]}, estimates={"S": 2, "A": 1})

    def test_bfs_minimizes_steps_not_cost(self):
        result = bfs(self.tradeoff)
        self.assertEqual(result.actions, ("S->G",))
        self.assertEqual(result.total_cost, 9)

    def test_ucs_and_astar_find_cheapest_path(self):
        for algorithm in (ucs, astar):
            with self.subTest(algorithm=algorithm.__name__):
                result = algorithm(self.tradeoff)
                self.assertEqual(result.actions, ("S->A", "A->G"))
                self.assertEqual(result.total_cost, 2)
                self.assertEqual(result.states, ("S", "A", "G"))

    def test_greedy_can_return_more_expensive_plan(self):
        self.assertEqual(greedy_best_first(self.tradeoff).total_cost, 9)

    def test_astar_reopens_with_admissible_inconsistent_heuristic(self):
        problem = GraphProblem(
            {"S": [("A", 3), ("B", 1)], "B": [("A", 1), ("G", 100)], "A": [("G", 2)]},
            estimates={"S": 4, "B": 3, "A": 0, "G": 0},
        )
        result = astar(problem)
        self.assertEqual(result.total_cost, 4)
        self.assertEqual(result.states, ("S", "B", "A", "G"))
        self.assertEqual(result.nodes_expanded, 4)  # S, A, B, A again

    def test_ucs_skips_stale_entries(self):
        problem = GraphProblem({"S": [("A", 8), ("B", 1)], "B": [("A", 1)]})
        result = ucs(problem)
        self.assertFalse(result.goal_reached)
        self.assertEqual(result.nodes_expanded, 3)

    def test_zero_cost_cycles_and_unreachable_goal_terminate(self):
        problem = GraphProblem({"S": [("A", 0)], "A": [("S", 0)]})
        for name in ("bfs", "ucs", "greedy", "astar"):
            with self.subTest(algorithm=name):
                result = search(problem, name)
                self.assertFalse(result.goal_reached)
                self.assertEqual(result.actions, ())
                self.assertIsNone(result.total_cost)
                self.assertEqual(result.nodes_expanded, 2)

    def test_initial_goal_needs_no_actions(self):
        for name in ("bfs", "ucs", "greedy", "astar"):
            result = search(GraphProblem({}, goals=("S",)), name)
            self.assertTrue(result.goal_reached)
            self.assertEqual(result.total_cost, 0)
            self.assertEqual(result.states, ("S",))
            self.assertEqual(result.nodes_expanded, 0)

    def test_ties_use_successor_order(self):
        problem = GraphProblem({"S": [("B", 1), ("A", 1)], "A": [("G", 1)], "B": [("G", 1)]})
        for name in ("bfs", "ucs", "greedy", "astar"):
            self.assertEqual(search(problem, name).actions, ("S->B", "B->G"))

    def test_zero_heuristic_matches_ucs(self):
        expected = ucs(self.tradeoff)
        actual = astar(self.tradeoff, heuristic=lambda state: 0)
        self.assertEqual(actual.actions, expected.actions)
        self.assertEqual(actual.nodes_expanded, expected.nodes_expanded)

    def test_metrics_have_defined_counts(self):
        result = bfs(GraphProblem({"S": [("A", 1)], "A": [("G", 1)]}))
        self.assertEqual((result.nodes_expanded, result.nodes_generated, result.frontier_peak), (2, 2, 1))
        self.assertGreaterEqual(result.elapsed_seconds, 0)

    def test_invalid_costs_rejected(self):
        for cost in (-1, math.inf, math.nan):
            with self.subTest(cost=cost), self.assertRaises(ValueError):
                ucs(GraphProblem({"S": [("G", cost)]}))

    def test_invalid_algorithm_and_heuristic_rejected(self):
        with self.assertRaises(ValueError):
            search(self.tradeoff, "unknown")
        for estimate in (-1, math.nan):
            with self.assertRaises(ValueError):
                astar(self.tradeoff, heuristic=lambda state: estimate)


if __name__ == "__main__":
    unittest.main()
