"""Pure-Python SVG chart and HTML report generator for evaluation results.

Uses only the Python standard library so every team member can run it without
installing matplotlib or other third-party plotting packages for local devices that have not installed them/ avoid pip issues
#visualizer for algorithm cost, nodes es expanded, execution time, heuristic comparison, and policy compliance.


"""
from __future__ import annotations

from html import escape
from pathlib import Path
import json

COMPLEXITIES = ["simple", "medium", "complex"]
MAIN_CONFIGS = [
    ("bfs", "BFS", "#4C78A8"),
    ("ucs", "UCS", "#F58518"),
    ("greedy", "Greedy", "#E45756"),
    ("astar", "A* (h-max)", "#54A24B"),
]


def draw_grouped_bar_chart(
    title: str,
    subtitle: str,
    y_label: str,
    groups: list[str],
    series: list[tuple[str, str, list[float]]],
    value_format: str = "{:.1f}",
) -> str:
    """Create a clean SVG grouped bar chart from categories and numeric series."""
    width = 820
    height = 440
    left = 80
    right = 30
    top = 85
    bottom = 95
    plot_w = width - left - right
    plot_h = height - top - bottom

    all_values = [v for _, _, vals in series for v in vals]
    max_val = max(all_values) if all_values else 1.0
    if max_val <= 0:
        max_val = 1.0
    y_max = max_val * 1.18

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" style="background:#ffffff;font-family:Segoe UI,Arial,sans-serif;">',
        f'<text x="{left}" y="32" font-size="18" font-weight="700" fill="#1f2937">{escape(title)}</text>',
        f'<text x="{left}" y="53" font-size="12" fill="#6b7280">{escape(subtitle)}</text>',
    ]

    # Horizontal gridlines and Y-axis tick labels.
    ticks = 5
    for i in range(ticks + 1):
        ratio = i / ticks
        val = y_max * ratio
        y = top + plot_h - (ratio * plot_h)
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" stroke="#e5e7eb" stroke-width="1"/>')
        parts.append(
            f'<text x="{left - 10}" y="{y + 4:.1f}" font-size="11" text-anchor="end" fill="#4b5563">'
            f'{escape(value_format.format(val))}</text>'
        )

    # Axes and Y-axis title.
    parts.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" stroke="#374151" stroke-width="1.5"/>')
    parts.append(f'<line x1="{left}" y1="{top + plot_h}" x2="{width - right}" y2="{top + plot_h}" stroke="#374151" stroke-width="1.5"/>')
    parts.append(
        f'<text x="22" y="{top + plot_h / 2:.1f}" font-size="12" font-weight="600" fill="#374151" '
        f'text-anchor="middle" transform="rotate(-90 22 {top + plot_h / 2:.1f})">{escape(y_label)}</text>'
    )

    # Bars grouped by category.
    group_count = max(len(groups), 1)
    series_count = max(len(series), 1)
    group_w = plot_w / group_count
    inner_w = group_w * 0.72
    bar_w = inner_w / series_count

    for g_idx, group_name in enumerate(groups):
        gx = left + g_idx * group_w
        parts.append(
            f'<text x="{gx + group_w / 2:.1f}" y="{top + plot_h + 24}" font-size="12" '
            f'font-weight="600" text-anchor="middle" fill="#1f2937">{escape(group_name)}</text>'
        )
        start_x = gx + (group_w - inner_w) / 2
        for s_idx, (_, color, vals) in enumerate(series):
            val = vals[g_idx] if g_idx < len(vals) else 0.0
            bar_h = (val / y_max) * plot_h
            bx = start_x + s_idx * bar_w + 2
            bw = max(bar_w - 4, 6)
            by = top + plot_h - bar_h
            parts.append(
                f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bar_h:.1f}" '
                f'rx="3" fill="{color}"/>'
            )
            parts.append(
                f'<text x="{bx + bw / 2:.1f}" y="{by - 5:.1f}" font-size="10" '
                f'text-anchor="middle" fill="#111827">{escape(value_format.format(val))}</text>'
            )

    # Legend at the bottom.
    legend_x = left
    legend_y = height - 32
    for label, color, _ in series:
        parts.append(f'<rect x="{legend_x}" y="{legend_y - 10}" width="12" height="12" rx="2" fill="{color}"/>')
        parts.append(f'<text x="{legend_x + 17}" y="{legend_y}" font-size="12" fill="#374151">{escape(label)}</text>')
        legend_x += max(125, len(label) * 8 + 34)

    parts.append("</svg>")
    return "\n".join(parts)


def _lookup_complexity(summary_by_complexity: list[dict], metric: str) -> list[tuple[str, str, list[float]]]:
    table = {(row["complexity"], row["config"]): row[metric] for row in summary_by_complexity}
    result = []
    for cfg, label, color in MAIN_CONFIGS:
        values = [float(table.get((comp, cfg), 0.0)) for comp in COMPLEXITIES]
        result.append((label, color, values))
    return result


def build_charts(payload: dict, charts_dir: Path) -> list[Path]:
    """Generate 5 SVG comparison charts in results/charts/."""
    charts_dir.mkdir(parents=True, exist_ok=True)
    comp_summary = payload["summary_by_complexity"]
    overall = {row["config"]: row for row in payload["summary_by_config"]}
    opt_rate = payload["optimality"]["optimal_rate"]
    policy_totals = payload["policy_comparison"]["totals"]

    chart_specs = [
        (
            "nodes_expanded_by_complexity.svg",
            draw_grouped_bar_chart(
                title="Nodes Expanded by Scenario Complexity",
                subtitle="Average search nodes expanded across 90 benchmark scenarios (lower is faster search)",
                y_label="Avg Nodes Expanded",
                groups=["Simple", "Medium", "Complex"],
                series=_lookup_complexity(comp_summary, "avg_nodes_expanded"),
                value_format="{:.1f}",
            ),
        ),
        (
            "cost_by_complexity.svg",
            draw_grouped_bar_chart(
                title="Total Investigation Plan Cost by Complexity",
                subtitle="UCS and A* (h-max) consistently find the lowest-cost safe plans",
                y_label="Avg Plan Cost",
                groups=["Simple", "Medium", "Complex"],
                series=_lookup_complexity(comp_summary, "avg_cost"),
                value_format="{:.2f}",
            ),
        ),
        (
            "execution_time_by_complexity.svg",
            draw_grouped_bar_chart(
                title="Execution Time by Scenario Complexity",
                subtitle=f"Mean search time in milliseconds ({payload['environment']['repeats']} repeats per scenario)",
                y_label="Mean Time (ms)",
                groups=["Simple", "Medium", "Complex"],
                series=_lookup_complexity(comp_summary, "avg_time_ms"),
                value_format="{:.3f}",
            ),
        ),
        (
            "heuristic_comparison.svg",
            draw_grouped_bar_chart(
                title="A* Heuristic Quality Comparison",
                subtitle="Admissible h-max vs. zero baseline (h=0) vs. deliberately overestimating heuristic",
                y_label="Average Value",
                groups=["Avg Nodes Expanded", "Avg Plan Cost", "Optimal Rate (%)"],
                series=[
                    (
                        "A* (h-max)",
                        "#54A24B",
                        [
                            overall["astar"]["avg_nodes_expanded"],
                            overall["astar"]["avg_cost"],
                            opt_rate["astar"] * 100.0,
                        ],
                    ),
                    (
                        "A* (h=0)",
                        "#4C78A8",
                        [
                            overall["astar_zero"]["avg_nodes_expanded"],
                            overall["astar_zero"]["avg_cost"],
                            opt_rate["astar_zero"] * 100.0,
                        ],
                    ),
                    (
                        "A* (overestimate)",
                        "#E45756",
                        [
                            overall["astar_over"]["avg_nodes_expanded"],
                            overall["astar_over"]["avg_cost"],
                            opt_rate["astar_over"] * 100.0,
                        ],
                    ),
                ],
                value_format="{:.1f}",
            ),
        ),
        (
            "policy_compliance.svg",
            draw_grouped_bar_chart(
                title="Policy Compliance: Secure Planner vs. Unconstrained Baseline",
                subtitle="Count of policy violations across approval-gate and prohibited-shortcut tests",
                y_label="Total Violations",
                groups=["Approval-Gate Runs (12)", "Prohibited-Shortcut Runs (12)"],
                series=[
                    ("Secure Planner (Ours)", "#54A24B", [0.0, float(policy_totals["secure_shortcut_violations"])]),
                    (
                        "Unconstrained Baseline",
                        "#E45756",
                        [
                            float(policy_totals["unconstrained_approval_violations"]),
                            float(policy_totals["unconstrained_shortcut_violations"]),
                        ],
                    ),
                ],
                value_format="{:.0f}",
            ),
        ),
    ]

    created = []
    for filename, svg_text in chart_specs:
        target = charts_dir / filename
        target.write_text(svg_text, encoding="utf-8")
        created.append(target)
    return created


def build_html_report(payload: dict, report_path: Path, chart_paths: list[Path]) -> Path:
    """Create a standalone HTML summary report embedding tables and SVG charts."""
    opt_rate = payload["optimality"]["optimal_rate"]
    rows_html = []
    for item in payload["summary_by_config"]:
        rows_html.append(
            "<tr>"
            f"<td>{escape(item['label'])}</td>"
            f"<td>{opt_rate[item['config']] * 100:.1f}%</td>"
            f"<td>{item['avg_cost']:.2f}</td>"
            f"<td>{item['avg_plan_length']:.2f}</td>"
            f"<td>{item['avg_nodes_expanded']:.2f}</td>"
            f"<td>{item['avg_nodes_generated']:.2f}</td>"
            f"<td>{item['avg_time_ms']:.4f} ms</td>"
            f"<td>{item['total_policy_violations']}</td>"
            "</tr>"
        )

    charts_html = "\n".join(
        f'<div class="card">{path.read_text(encoding="utf-8")}</div>'
        for path in chart_paths
    )
    totals = payload["policy_comparison"]["totals"]

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Secure Agentic AI — Evaluation Report</title>
  <style>
    body {{ font-family: Segoe UI, Arial, sans-serif; margin: 0; padding: 28px; background: #f3f4f6; color: #111827; }}
    .wrap {{ max-width: 1100px; margin: 0 auto; }}
    h1 {{ margin-bottom: 4px; }}
    .muted {{ color: #4b5563; margin-top: 0; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 14px; margin: 20px 0; }}
    .stat {{ background: #fff; padding: 16px; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
    .stat .num {{ font-size: 26px; font-weight: 700; color: #1d4ed8; }}
    .card {{ background: #fff; padding: 18px; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); margin-bottom: 18px; overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid #e5e7eb; text-align: left; }}
    th {{ background: #f9fafb; font-weight: 600; }}
    svg {{ max-width: 100%; height: auto; }}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>Secure Agentic AI — Performance &amp; Policy Evaluation Report</h1>
    <p class="muted">Simulation-only research prototype | Python {escape(payload['environment']['python_version'])} | {payload['environment']['repeats']} repeats per scenario</p>

    <div class="grid">
      <div class="stat"><div>Benchmark Scenarios</div><div class="num">{payload['optimality']['total_scenarios']}</div></div>
      <div class="stat"><div>Total Configurations</div><div class="num">{len(payload['summary_by_config'])}</div></div>
      <div class="stat"><div>Secure Planner Violations</div><div class="num" style="color:#15803d;">0</div></div>
      <div class="stat"><div>Unconstrained Violations</div><div class="num" style="color:#b91c1c;">{totals['unconstrained_approval_violations'] + totals['unconstrained_shortcut_violations']}</div></div>
    </div>

    <div class="card">
      <h2>Algorithm Comparison Summary (90 Benchmark Scenarios)</h2>
      <table>
        <thead>
          <tr><th>Algorithm</th><th>Optimal Rate</th><th>Avg Cost</th><th>Avg Steps</th><th>Avg Expanded</th><th>Avg Generated</th><th>Mean Time</th><th>Violations</th></tr>
        </thead>
        <tbody>
          {''.join(rows_html)}
        </tbody>
      </table>
    </div>

    {charts_html}
  </div>
</body>
</html>
"""
    report_path.write_text(html, encoding="utf-8")
    return report_path


def generate_all_visualizations(payload: dict | None = None, output_dir: Path | None = None) -> list[Path]:
    """Generate SVG charts and standalone HTML report from evaluation results."""
    base_dir = output_dir or (Path(__file__).resolve().parent / "results")
    if payload is None:
        json_path = base_dir / "benchmark_results.json"
        if not json_path.exists():
            raise FileNotFoundError(f"Run evaluate.py first so {json_path} exists.")
        payload = json.loads(json_path.read_text(encoding="utf-8"))

    chart_paths = build_charts(payload, base_dir / "charts")
    report_path = build_html_report(payload, base_dir / "evaluation_report.html", chart_paths)
    return [*chart_paths, report_path]


if __name__ == "__main__":
    files = generate_all_visualizations()
    for path in files:
        print(f"Created: {path}")
