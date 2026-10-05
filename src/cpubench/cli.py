from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Annotated

import typer
from pydantic import BaseModel
from rich.console import Console
from rich.table import Table

from . import __version__
from .analysis import analyze_campaign
from .campaign import (
    campaign_output_dir,
    execute_campaign,
    finalize_campaign,
    initialize_campaign,
    load_campaign_bundle,
    persist_runtime,
    preflight_summary,
    prepare_runtime,
)
from .evidence import CampaignStore, atomic_write_json
from .integrity import analyze_variant_set, run_integrity_demo
from .models import (
    AnalysisBundle,
    AttemptRecord,
    BuildReceipt,
    CampaignSpec,
    FamilySpec,
    FindingBundle,
    InstrumentRelease,
    MachineReceipt,
    PackRelease,
    PackSpec,
    ProfileSpec,
    ProviderDescriptor,
    RunEnvironmentReceipt,
    RunPlan,
    StudyBundle,
    StudySpec,
    VariantSetSpec,
    ValidationBundle,
    VerificationResult,
)
from .platform_probe import collect_machine_receipt
from .report import generate_report
from .specs import load_pack
from .study import compare_study, report_study
from .validation import validate_campaign

app = typer.Typer(
    name="cpubench",
    help="Evidence-producing CPU review campaigns.",
    no_args_is_help=True,
    add_completion=False,
)
campaign_app = typer.Typer(help="Create, run, validate, and report review campaigns.")
family_app = typer.Typer(help="Inspect and validate benchmark family definitions.")
integrity_app = typer.Typer(help="Exercise benchmark-integrity challenge logic.")
schema_app = typer.Typer(help="Export the versioned artifact schemas.")
study_app = typer.Typer(help="Compare finalized campaigns under one declared study policy.")
app.add_typer(campaign_app, name="campaign")
app.add_typer(family_app, name="family")
app.add_typer(integrity_app, name="integrity")
app.add_typer(schema_app, name="schema")
app.add_typer(study_app, name="study")
console = Console()


def _json(value: Any) -> None:
    console.print_json(json.dumps(value, default=str))


@app.command()
def version() -> None:
    """Print the installed CPUBench version."""
    console.print(__version__)


@app.command()
def doctor(
    output: Annotated[Path | None, typer.Option("--output", "-o", help="Write the machine receipt to this path.")] = None,
) -> None:
    """Inspect the machine and state exactly what CPUBench can prove."""
    receipt = collect_machine_receipt()
    if output:
        atomic_write_json(output, receipt.model_dump(mode="json", exclude_none=True))
        console.print(f"[bold green]Wrote machine receipt:[/] {output}")
    _json(receipt.model_dump(mode="json", exclude_none=True))


@campaign_app.command("init")
def campaign_init(
    path: Annotated[Path, typer.Argument(help="Campaign YAML path to create.")],
    campaign_id: Annotated[str, typer.Option("--campaign-id")] = "example-review",
) -> None:
    """Create a runnable campaign definition."""
    created = initialize_campaign(path, campaign_id=campaign_id)
    console.print(f"[bold green]Created:[/] {created}")


@campaign_app.command("preflight")
def campaign_preflight(
    path: Annotated[Path, typer.Argument(help="Campaign YAML path.")],
    profile: Annotated[str | None, typer.Option("--profile")] = None,
) -> None:
    """Validate campaign inputs and show the execution budget before any build or run."""
    summary = preflight_summary(path, profile)
    _json(summary)


@campaign_app.command("plan")
def campaign_plan(
    path: Annotated[Path, typer.Argument(help="Campaign YAML path.")],
    profile: Annotated[str | None, typer.Option("--profile")] = None,
) -> None:
    """Build providers and freeze the machine-specific run plan."""
    runtime = prepare_runtime(path, profile_override=profile, resume=True)
    persist_runtime(runtime)
    console.print(f"[bold green]Planned {len(runtime.plan.items)} attempts:[/] {runtime.store.root}")


@campaign_app.command("run")
def campaign_run(
    path: Annotated[Path, typer.Argument(help="Campaign YAML path.")],
    profile: Annotated[str | None, typer.Option("--profile")] = None,
) -> None:
    """Execute or resume a frozen campaign plan."""
    runtime = prepare_runtime(path, profile_override=profile, resume=True)
    persist_runtime(runtime)
    counts = execute_campaign(runtime, resume=True)
    console.print(f"[bold green]Execution complete:[/] {runtime.store.root}")
    _json(counts)


@campaign_app.command("status")
def campaign_status(
    campaign_dir: Annotated[Path, typer.Argument(help="Campaign evidence directory.")],
) -> None:
    """Summarize plan, terminal attempts, derived artifacts, and finalization state."""
    root = campaign_dir.resolve()
    plan_path = root / "run-plan.json"
    if not plan_path.exists():
        raise typer.BadParameter(f"run-plan.json not found: {root}")
    plan = RunPlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
    counts: dict[str, int] = {}
    for attempt_path in (root / "attempts").glob("*/attempt.json"):
        attempt = AttemptRecord.model_validate_json(attempt_path.read_text(encoding="utf-8"))
        counts[attempt.state.value] = counts.get(attempt.state.value, 0) + 1
    payload = {
        "campaign_id": plan.campaign_id,
        "run_plan_id": plan.semantic_id,
        "instrument_release_id": plan.instrument_release_id,
        "planning_environment_receipt_id": plan.run_environment_receipt_id,
        "execution_environment_receipts": len(list((root / "run-environments").glob("*.json"))),
        "pack_release_ids": plan.pack_release_ids,
        "planned_attempts": len(plan.items),
        "terminal_attempts": sum(counts.values()),
        "attempt_states": counts,
        "validation": (root / "validation" / "validation-bundle.json").exists(),
        "analysis": (root / "analysis" / "analysis-bundle.json").exists(),
        "report": (root / "report" / "index.html").exists(),
        "finalized": (root / "manifest.json").exists(),
        "verification": (root / "verification.json").exists(),
    }
    _json(payload)


@campaign_app.command("validate")
def campaign_validate(
    campaign_dir: Annotated[Path, typer.Argument(help="Campaign evidence directory.")],
    validity_view: Annotated[str, typer.Option("--view")] = "portable_elapsed",
) -> None:
    """Interpret retained evidence under a named validity view."""
    bundle = validate_campaign(campaign_dir, validity_view=validity_view)
    console.print(f"[bold green]Validation bundle:[/] {bundle.semantic_id}")
    _json(bundle.coverage)


@campaign_app.command("analyze")
def campaign_analyze(
    campaign_dir: Annotated[Path, typer.Argument(help="Campaign evidence directory.")],
) -> None:
    """Compute family-level estimates from validated attempts."""
    bundle = analyze_campaign(campaign_dir)
    console.print(f"[bold green]Analysis bundle:[/] {bundle.semantic_id}")
    console.print(f"Comparable points: {len(bundle.points)}")


@campaign_app.command("report")
def campaign_report(
    campaign_dir: Annotated[Path, typer.Argument(help="Campaign evidence directory.")],
) -> None:
    """Render static HTML, Markdown, and JSON reports from retained evidence."""
    report = generate_report(campaign_dir)
    console.print(f"[bold green]Report:[/] {report}")


@campaign_app.command("finalize")
def campaign_finalize(
    campaign_dir: Annotated[Path, typer.Argument(help="Campaign evidence directory.")],
) -> None:
    """Hash the complete campaign bundle and make it immutable to CPUBench."""
    manifest = finalize_campaign(campaign_dir)
    console.print(f"[bold green]Finalized {len(manifest['files'])} files:[/] {campaign_dir}")


@campaign_app.command("verify")
def campaign_verify(
    campaign_dir: Annotated[Path, typer.Argument(help="Finalized campaign evidence directory.")],
) -> None:
    """Verify a finalized campaign bundle offline."""
    result = CampaignStore(campaign_dir).verify()
    _json(result.model_dump(mode="json"))
    if not result.valid:
        raise typer.Exit(1)


@campaign_app.command("all")
def campaign_all(
    path: Annotated[Path, typer.Argument(help="Campaign YAML path.")],
    profile: Annotated[str | None, typer.Option("--profile")] = None,
    validity_view: Annotated[str, typer.Option("--view")] = "portable_elapsed",
    fresh: Annotated[bool, typer.Option("--fresh", help="Delete an existing unfinished campaign directory first.")] = False,
) -> None:
    """Run the complete evidence chain from doctor through offline-verifiable report."""
    loaded = load_campaign_bundle(path, profile)
    output_dir = campaign_output_dir(loaded)
    if fresh and output_dir.exists():
        shutil.rmtree(output_dir)
    runtime = prepare_runtime(path, profile_override=profile, resume=True)
    persist_runtime(runtime)
    counts = execute_campaign(runtime, resume=True)
    validation = validate_campaign(runtime.store.root, validity_view=validity_view)
    analysis = analyze_campaign(runtime.store.root)
    report = generate_report(runtime.store.root)
    manifest = finalize_campaign(runtime.store.root)
    verification = runtime.store.verify()

    table = Table(title="CPUBench campaign complete")
    table.add_column("Stage")
    table.add_column("Receipt")
    table.add_row("Attempts", json.dumps(counts, sort_keys=True))
    table.add_row("Validation", validation.semantic_id or "")
    table.add_row("Analysis", analysis.semantic_id or "")
    table.add_row("Report", str(report))
    table.add_row("Manifest files", str(len(manifest["files"])))
    table.add_row("Verification", "pass" if verification.valid else "fail")
    console.print(table)
    if not verification.valid:
        raise typer.Exit(1)


@study_app.command("init")
def study_init(
    path: Annotated[Path, typer.Argument(help="Study YAML path to create.")],
    baseline: Annotated[Path, typer.Option("--baseline", help="Finalized baseline campaign directory.")],
    campaign: Annotated[list[Path] | None, typer.Option("--campaign", help="Additional finalized campaign directory.")] = None,
    study_id: Annotated[str, typer.Option("--study-id")] = "comparison",
) -> None:
    """Create a study definition over finalized campaign bundles."""
    if path.exists():
        raise typer.BadParameter(f"path already exists: {path}")
    refs = [baseline.resolve(), *((item.resolve()) for item in (campaign or []))]
    baseline_spec_path = refs[0] / "campaign-spec.json"
    if not baseline_spec_path.exists():
        raise typer.BadParameter(f"baseline does not contain campaign-spec.json: {refs[0]}")
    baseline_spec = CampaignSpec.model_validate_json(baseline_spec_path.read_text(encoding="utf-8"))
    baseline_validation_path = refs[0] / "validation" / "validation-bundle.json"
    baseline_analysis_path = refs[0] / "analysis" / "analysis-bundle.json"
    if not baseline_validation_path.exists() or not baseline_analysis_path.exists():
        raise typer.BadParameter("baseline must contain validation and analysis bundles")
    baseline_validation = ValidationBundle.model_validate_json(baseline_validation_path.read_text(encoding="utf-8"))
    baseline_analysis = AnalysisBundle.model_validate_json(baseline_analysis_path.read_text(encoding="utf-8"))
    payload = {
        "schema_version": 1,
        "artifact_kind": "study_spec",
        "study_id": study_id,
        "title": f"{study_id} comparison",
        "description": "Direct comparison of finalized CPUBench campaigns.",
        "campaigns": [{"path": str(item)} for item in refs],
        "baseline_campaign_id": baseline_spec.campaign_id,
        "validity_view": baseline_validation.validity_view,
        "analysis_policy": baseline_analysis.analysis_policy,
        "missingness_policy": "omit_unmatched",
        "output_root": ".cpubench/studies",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    import yaml

    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    console.print(f"[bold green]Created:[/] {path}")


@study_app.command("compare")
def study_compare(
    path: Annotated[Path, typer.Argument(help="Study YAML path.")],
) -> None:
    """Compare only directly compatible points from finalized campaigns."""
    bundle, output_dir = compare_study(path)
    console.print(f"[bold green]Study bundle:[/] {output_dir / 'study-bundle.json'}")
    console.print(f"Comparable points: {len(bundle.points)}; omissions: {len(bundle.omissions)}")


@study_app.command("report")
def study_report(
    path: Annotated[Path, typer.Argument(help="Study YAML path.")],
) -> None:
    """Render a static multi-campaign comparison report."""
    report = report_study(path)
    console.print(f"[bold green]Study report:[/] {report}")


@family_app.command("lint")
def family_lint(
    pack: Annotated[str, typer.Argument(help="Pack YAML path or bundled resource path.")],
) -> None:
    """Validate a pack and every family it contains."""
    pack_spec, families = load_pack(pack, base_dir=Path.cwd())
    table = Table(title=f"{pack_spec.pack_id} {pack_spec.pack_version}")
    table.add_column("Family")
    table.add_column("Version")
    table.add_column("Points", justify="right")
    table.add_column("Provider")
    for family in families:
        table.add_row(family.family_id, family.family_version, str(len(family.points)), family.provider_id)
    console.print(table)


@integrity_app.command("demo")
def integrity_demo(
    output_dir: Annotated[Path, typer.Option("--output", "-o")] = Path(".cpubench/integrity-demo"),
    threshold: Annotated[float, typer.Option("--threshold")] = 1.25,
) -> None:
    """Prove that the integrity analyzer separates known-honest and known-gamed providers."""
    payload = run_integrity_demo(output_dir, threshold=threshold)
    _json(payload)


@integrity_app.command("analyze")
def integrity_analyze(
    campaign_dir: Annotated[Path, typer.Argument(help="Campaign directory containing analysis evidence.")],
    variant_set: Annotated[Path, typer.Argument(help="VariantSetSpec YAML or JSON path.")],
    output_dir: Annotated[Path, typer.Option("--output", "-o")] = Path(".cpubench/findings"),
) -> None:
    """Analyze matched campaign points under an authored integrity variant relation."""
    bundle = analyze_variant_set(campaign_dir, variant_set, output_dir)
    _json(bundle.model_dump(mode="json", exclude_none=True))


@schema_app.command("export")
def schema_export(
    output_dir: Annotated[Path, typer.Argument(help="Directory for JSON Schemas.")] = Path("contracts/schemas"),
) -> None:
    """Export the exact schemas used by the installed control plane."""
    models: list[tuple[str, type[BaseModel]]] = [
        ("campaign-spec", CampaignSpec),
        ("pack-spec", PackSpec),
        ("family-spec", FamilySpec),
        ("profile-spec", ProfileSpec),
        ("instrument-release", InstrumentRelease),
        ("pack-release", PackRelease),
        ("variant-set-spec", VariantSetSpec),
        ("machine-receipt", MachineReceipt),
        ("run-environment-receipt", RunEnvironmentReceipt),
        ("provider-descriptor", ProviderDescriptor),
        ("build-receipt", BuildReceipt),
        ("run-plan", RunPlan),
        ("study-spec", StudySpec),
        ("study-bundle", StudyBundle),
        ("attempt-record", AttemptRecord),
        ("validation-bundle", ValidationBundle),
        ("analysis-bundle", AnalysisBundle),
        ("finding-bundle", FindingBundle),
        ("verification-result", VerificationResult),
    ]
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, model in models:
        target = output_dir / f"{name}.schema.json"
        atomic_write_json(target, model.model_json_schema())
    console.print(f"[bold green]Exported {len(models)} schemas:[/] {output_dir}")


def main() -> None:
    app()
