from __future__ import annotations

import html
import json
import math
from collections import defaultdict
from pathlib import Path

from .evidence import atomic_write_json, atomic_write_text
from .models import AnalysisBundle, CampaignSpec, MachineReceipt, PointEstimate, ValidationBundle


LIGHT = "#f5f1e8"
PAPER = "#fafaf7"
INK = "#1a1816"
TEAL = "#156b76"
GOLD = "#e1a82c"
AMBER = "#d97706"
RUST = "#b5651d"


def _human_bytes(value: int | float | None) -> str:
    if value is None:
        return "—"
    size = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(size) < 1024 or unit == "TiB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TiB"




def _human_ns(value: int | float | None) -> str:
    if value is None:
        return "—"
    nanoseconds = float(value)
    if nanoseconds < 1_000:
        return f"{nanoseconds:.2f} ns"
    if nanoseconds < 1_000_000:
        return f"{nanoseconds / 1_000:.2f} µs"
    if nanoseconds < 1_000_000_000:
        return f"{nanoseconds / 1_000_000:.2f} ms"
    return f"{nanoseconds / 1_000_000_000:.2f} s"

def _point_sort_key(point: PointEstimate) -> tuple[float, str]:
    parameters = point.parameters
    if "working_set_bytes" in parameters and point.family_id.endswith("dependent_load_latency"):
        return float(parameters["working_set_bytes"]), point.point_id
    if "chains" in parameters:
        return float(parameters["chains"]), point.point_id
    return 0.0, point.point_id


def _safe_name(value: str) -> str:
    return "".join(character if character.isalnum() or character in {"-", "_"} else "-" for character in value)


def _chart_svg(points: list[PointEstimate], family_id: str) -> str:
    if not points:
        return ""
    width, height = 760, 280
    left, right, top, bottom = 70, 24, 28, 48
    plot_w, plot_h = width - left - right, height - top - bottom

    def x_value(point: PointEstimate) -> float:
        params = point.parameters
        if "working_set_bytes" in params and family_id.endswith("dependent_load_latency"):
            return math.log2(max(1, float(params["working_set_bytes"])))
        if "chains" in params:
            return math.log2(max(1, float(params["chains"])))
        return float(points.index(point))

    xs = [x_value(point) for point in points]
    ys = [point.median_ns_per_unit for point in points]
    interval_values = [value for point in points for value in (point.ci95_low_ns_per_unit, point.ci95_high_ns_per_unit)]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(interval_values), max(interval_values)
    if min_x == max_x:
        min_x -= 1
        max_x += 1
    if min_y == max_y:
        min_y *= 0.9
        max_y *= 1.1
        if min_y == max_y:
            max_y += 1

    def sx(value: float) -> float:
        return left + (value - min_x) / (max_x - min_x) * plot_w

    def sy(value: float) -> float:
        return top + plot_h - (value - min_y) / (max_y - min_y) * plot_h

    path = " ".join(("M" if index == 0 else "L") + f" {sx(x):.1f} {sy(y):.1f}" for index, (x, y) in enumerate(zip(xs, ys)))
    circles = "".join(
        f'<circle cx="{sx(x):.1f}" cy="{sy(y):.1f}" r="4.5"><title>{html.escape(point.point_id)}: {y:.3f} ns/unit</title></circle>'
        for x, y, point in zip(xs, ys, points)
    )
    intervals = "".join(
        f'<line class="interval" x1="{sx(x):.1f}" y1="{sy(point.ci95_low_ns_per_unit):.1f}" '
        f'x2="{sx(x):.1f}" y2="{sy(point.ci95_high_ns_per_unit):.1f}"><title>'
        f'{point.ci95_low_ns_per_unit:.3f}–{point.ci95_high_ns_per_unit:.3f} ns/unit</title></line>'
        for x, point in zip(xs, points)
    )
    labels = "".join(
        f'<text x="{sx(x):.1f}" y="{height - 18}" text-anchor="middle">{html.escape(point.point_id)}</text>'
        for x, point in zip(xs, points)
    )
    return f"""
<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(family_id)} curve">
  <line class="axis" x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}"/>
  <line class="axis" x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}"/>
  <text x="18" y="{top + plot_h / 2}" transform="rotate(-90 18 {top + plot_h / 2})" text-anchor="middle">ns / unit</text>
  <path class="series" d="{path}"/>
  <g class="intervals">{intervals}</g>
  <g class="points">{circles}</g>
  <g class="xlabels">{labels}</g>
</svg>
"""


def generate_report(campaign_dir: Path) -> Path:
    campaign_dir = campaign_dir.resolve()
    campaign = CampaignSpec.model_validate_json((campaign_dir / "campaign-spec.json").read_text(encoding="utf-8"))
    machine = MachineReceipt.model_validate_json((campaign_dir / "machine-receipt.json").read_text(encoding="utf-8"))
    validation = ValidationBundle.model_validate_json(
        (campaign_dir / "validation" / "validation-bundle.json").read_text(encoding="utf-8")
    )
    analysis = AnalysisBundle.model_validate_json(
        (campaign_dir / "analysis" / "analysis-bundle.json").read_text(encoding="utf-8")
    )

    grouped: dict[str, list[PointEstimate]] = defaultdict(list)
    for point in analysis.points:
        grouped[point.family_id].append(point)
    for points in grouped.values():
        points.sort(key=_point_sort_key)

    table_rows: list[str] = []
    for point in analysis.points:
        parameters = ", ".join(f"{key}={value}" for key, value in sorted(point.parameters.items()))
        table_rows.append(
            "<tr>"
            f"<td><code>{html.escape(point.family_id)}</code></td>"
            f"<td>{html.escape(point.point_id)}</td>"
            f"<td>{html.escape(parameters)}</td>"
            f"<td>{point.eligible_attempts}</td>"
            f"<td>{point.median_ns_per_unit:.4f}</td>"
            f"<td>{point.ci95_low_ns_per_unit:.4f}–{point.ci95_high_ns_per_unit:.4f}</td>"
            f"<td>{point.mad_ns_per_unit:.4f}</td>"
            f"<td>{point.median_units_per_second:,.2f}</td>"
            "</tr>"
        )

    chart_sections = "".join(
        f"<section><h2>{html.escape(family_id)}</h2>{_chart_svg(points, family_id)}</section>"
        for family_id, points in grouped.items()
    )

    timer_qualification_rows = "".join(
        "<tr>"
        f"<td><code>{html.escape(timer)}</code></td>"
        f"<td>{html.escape(qualification.state.value)}</td>"
        f"<td>{_human_ns(qualification.read_overhead_ns)}</td>"
        f"<td>{_human_ns(qualification.effective_resolution_ns)}</td>"
        f"<td>{_human_ns(qualification.minimum_sample_duration_ns)}</td>"
        f"<td>{qualification.observations:,}</td>"
        f"<td>{qualification.non_monotonic_observations:,}</td>"
        f"<td>{html.escape(qualification.reason_code)}</td>"
        "</tr>"
        for timer, qualification in sorted(validation.timer_qualifications.items())
    )

    capability_rows = "".join(
        "<tr>"
        f"<td><code>{html.escape(name)}</code></td>"
        f"<td>{html.escape(value.state.value)}</td>"
        f"<td>{html.escape(value.authority)}</td>"
        f"<td>{html.escape(value.detail or '')}</td>"
        "</tr>"
        for name, value in sorted(machine.capabilities.items())
    )

    html_text = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(campaign.title)} · CPUBench</title>
<style>
:root {{ --paper:{PAPER}; --warm:{LIGHT}; --ink:{INK}; --teal:{TEAL}; --gold:{GOLD}; --amber:{AMBER}; --rust:{RUST}; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--warm); color:var(--ink); font:16px/1.55 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif; }}
main {{ max-width:1120px; margin:0 auto; padding:32px 20px 72px; }}
header {{ border-left:6px solid var(--teal); padding:8px 0 8px 18px; margin-bottom:28px; }}
h1 {{ margin:0; font-size:clamp(2rem,5vw,3.5rem); line-height:1; }}
.deck {{ max-width:760px; font-size:1.1rem; }}
.meta {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); gap:12px; margin:22px 0; }}
.card, section {{ background:var(--paper); border:1px solid #d8d1c5; border-radius:12px; padding:18px; box-shadow:0 2px 0 rgba(26,24,22,.04); }}
.card strong {{ display:block; color:var(--teal); font-size:.8rem; letter-spacing:.08em; text-transform:uppercase; }}
section {{ margin:18px 0; overflow-x:auto; }}
h2 {{ margin-top:0; }}
table {{ width:100%; border-collapse:collapse; font-size:.92rem; }}
th,td {{ text-align:left; padding:9px 8px; border-bottom:1px solid #ddd5c8; vertical-align:top; }}
th {{ color:var(--teal); }}
code {{ font-family:ui-monospace,SFMono-Regular,Consolas,monospace; }}
.chart {{ width:100%; min-width:680px; background:#fff; border-radius:8px; }}
.chart .axis {{ stroke:#777; stroke-width:1; }}
.chart .series {{ fill:none; stroke:var(--teal); stroke-width:3; }}
.chart .interval {{ stroke:var(--rust); stroke-width:2; }}
.chart .points circle {{ fill:var(--gold); stroke:var(--ink); stroke-width:1; }}
.chart text {{ fill:var(--ink); font-size:11px; }}
.notice {{ border-left:5px solid var(--amber); }}
footer {{ margin-top:34px; color:#5f5953; font-size:.9rem; }}
</style>
</head>
<body><main>
<header>
  <h1>{html.escape(campaign.title)}</h1>
  <p class="deck">{html.escape(campaign.description)}</p>
</header>
<div class="meta">
  <div class="card"><strong>Campaign</strong>{html.escape(campaign.campaign_id)}</div>
  <div class="card"><strong>Operating mode</strong>{html.escape(campaign.operating_mode.value)}</div>
  <div class="card"><strong>Machine</strong>{html.escape(str(machine.cpu.get('linux_cpuinfo', {}).get('model name') or machine.cpu.get('processor') or machine.system.get('machine')))}</div>
  <div class="card"><strong>Memory</strong>{_human_bytes(machine.memory.get('total_bytes'))}</div>
  <div class="card"><strong>Validity view</strong>{html.escape(validation.validity_view)}</div>
  <div class="card"><strong>Comparable points</strong>{len(analysis.points)}</div>
</div>
<section class="notice">
<h2>Claim boundary</h2>
<p>This is an instrument-development campaign. It preserves raw evidence and bounded family results; it does not publish a universal CPU score.</p>
</section>
{chart_sections}
<section>
<h2>Point estimates</h2>
<table><thead><tr><th>Family</th><th>Point</th><th>Parameters</th><th>Attempts</th><th>Median ns/unit</th><th>95% interval</th><th>MAD</th><th>Units/s</th></tr></thead>
<tbody>{''.join(table_rows)}</tbody></table>
</section>
<section>
<h2>Timer qualification</h2>
<table><thead><tr><th>Timer</th><th>State</th><th>Read overhead</th><th>Effective resolution</th><th>Minimum sample</th><th>Observations</th><th>Non-monotonic</th><th>Reason</th></tr></thead><tbody>{timer_qualification_rows}</tbody></table>
</section>
<section>
<h2>Measurement authority</h2>
<table><thead><tr><th>Capability</th><th>State</th><th>Authority</th><th>Detail</th></tr></thead><tbody>{capability_rows}</tbody></table>
</section>
<section>
<h2>Coverage</h2>
<pre>{html.escape(json.dumps(validation.coverage, indent=2, sort_keys=True))}</pre>
</section>
<footer>Generated from retained CPUBench evidence. The report is a projection; campaign artifacts remain authoritative.</footer>
</main></body></html>
"""

    report_dir = campaign_dir / "report"
    report_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = report_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)
    for family_id, points in grouped.items():
        atomic_write_text(figures_dir / f"{_safe_name(family_id)}.svg", _chart_svg(points, family_id))
    atomic_write_text(report_dir / "index.html", html_text)

    markdown_lines = [
        f"# {campaign.title}",
        "",
        campaign.description,
        "",
        f"- Campaign: `{campaign.campaign_id}`",
        f"- Operating mode: `{campaign.operating_mode.value}`",
        f"- Validity view: `{validation.validity_view}`",
        f"- Comparable points: {len(analysis.points)}",
        "",
        "## Point estimates",
        "",
        "| Family | Point | Attempts | Median ns/unit | 95% interval | MAD | Units/s |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for point in analysis.points:
        markdown_lines.append(
            f"| `{point.family_id}` | `{point.point_id}` | {point.eligible_attempts} | "
            f"{point.median_ns_per_unit:.4f} | "
            f"{point.ci95_low_ns_per_unit:.4f}–{point.ci95_high_ns_per_unit:.4f} | "
            f"{point.mad_ns_per_unit:.4f} | "
            f"{point.median_units_per_second:.2f} |"
        )
    markdown_lines.extend(
        [
            "",
            "## Timer qualification",
            "",
            "| Timer | State | Read overhead | Effective resolution | Minimum sample | Observations | Non-monotonic |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for timer, qualification in sorted(validation.timer_qualifications.items()):
        markdown_lines.append(
            f"| `{timer}` | `{qualification.state.value}` | {_human_ns(qualification.read_overhead_ns)} | "
            f"{_human_ns(qualification.effective_resolution_ns)} | "
            f"{_human_ns(qualification.minimum_sample_duration_ns)} | "
            f"{qualification.observations} | {qualification.non_monotonic_observations} |"
        )
    markdown_lines.extend(
        [
            "",
            "## Claim boundary",
            "",
            "This campaign does not produce a universal CPU score. Family-level evidence remains canonical.",
        ]
    )
    atomic_write_text(report_dir / "summary.md", "\n".join(markdown_lines) + "\n")
    atomic_write_json(
        report_dir / "summary.json",
        {
            "campaign": campaign.model_dump(mode="json", exclude_none=True),
            "machine_receipt_id": machine.semantic_id,
            "validation_bundle_id": validation.semantic_id,
            "analysis_bundle_id": analysis.semantic_id,
            "timer_qualifications": {
                timer: qualification.model_dump(mode="json", exclude_none=True)
                for timer, qualification in sorted(validation.timer_qualifications.items())
            },
            "points": [point.model_dump(mode="json") for point in analysis.points],
        },
    )
    return report_dir / "index.html"
