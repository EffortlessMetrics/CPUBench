from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .models import AttemptRecord, AttemptState, ProviderDescriptor, RunPlanItem, SampleRecord, utc_now


@dataclass(frozen=True)
class ProviderCommand:
    provider_id: str
    argv: list[str]
    cwd: Path | None = None
    env: dict[str, str] | None = None


class ProviderError(RuntimeError):
    pass


class SubprocessProvider:
    """One-shot language-neutral benchmark provider."""

    def __init__(self, command: ProviderCommand) -> None:
        self.command = command

    def _run(self, args: list[str], *, timeout: float = 30.0) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        if self.command.env:
            env.update(self.command.env)
        return subprocess.run(
            [*self.command.argv, *args],
            cwd=self.command.cwd,
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )

    def describe(self) -> ProviderDescriptor:
        try:
            result = self._run(["describe"])
        except OSError as exc:
            raise ProviderError(f"provider describe could not start: {exc}") from exc
        if result.returncode != 0:
            raise ProviderError(f"provider describe failed: {result.stderr.strip()}")
        try:
            return ProviderDescriptor.model_validate_json(result.stdout)
        except (ValidationError, ValueError) as exc:
            raise ProviderError(f"invalid provider descriptor: {exc}") from exc

    def self_test(self) -> dict[str, Any]:
        try:
            result = self._run(["self-test"], timeout=60.0)
        except OSError as exc:
            raise ProviderError(f"provider self-test could not start: {exc}") from exc
        if result.returncode != 0:
            raise ProviderError(f"provider self-test failed: {result.stderr.strip()}")
        try:
            value = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise ProviderError(f"provider self-test returned invalid JSON: {exc}") from exc
        if not isinstance(value, dict):
            raise ProviderError("provider self-test must return a JSON object")
        return value

    def _terminal(
        self,
        item: RunPlanItem,
        state: AttemptState,
        started: datetime,
        *,
        reason_code: str,
        detail: str,
        stdout: str = "",
        stderr: str = "",
        samples: list[SampleRecord] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AttemptRecord:
        return AttemptRecord(
            attempt_id=item.attempt_id,
            state=state,
            family_id=item.family_id,
            point_id=item.point_id,
            provider_id=item.provider_id,
            started_at=started,
            finished_at=utc_now(),
            requested_parameters=item.parameters,
            effective_parameters=metadata or {},
            samples=samples or [],
            warnings=[stderr.strip()] if stderr.strip() else [],
            provider_stdout=stdout,
            provider_stderr=stderr,
            reason_code=reason_code,
            detail=detail,
        ).with_semantic_id()

    def run_attempt(self, item: RunPlanItem) -> AttemptRecord:
        started = utc_now()
        args = [
            "run",
            "--family",
            item.family_id,
            "--samples",
            str(item.samples_per_attempt),
            "--warmup-samples",
            str(item.warmup_samples),
        ]
        for key, value in sorted(item.parameters.items()):
            flag = "--" + key.replace("_", "-")
            if isinstance(value, bool):
                if value:
                    args.append(flag)
            else:
                args.extend([flag, str(value)])

        try:
            result = self._run(args, timeout=item.timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout if isinstance(exc.stdout, str) else ""
            stderr = exc.stderr if isinstance(exc.stderr, str) else ""
            return self._terminal(
                item,
                AttemptState.TIMED_OUT,
                started,
                reason_code="provider_timeout",
                detail=str(exc),
                stdout=stdout,
                stderr=stderr,
            )
        except OSError as exc:
            return self._terminal(
                item,
                AttemptState.EXECUTION_FAILED,
                started,
                reason_code="provider_start_failed",
                detail=str(exc),
            )

        if result.returncode == 64:
            return self._terminal(
                item,
                AttemptState.UNSUPPORTED,
                started,
                reason_code="provider_unsupported",
                detail=result.stderr.strip() or result.stdout.strip(),
                stdout=result.stdout,
                stderr=result.stderr,
            )

        if result.returncode != 0:
            return self._terminal(
                item,
                AttemptState.EXECUTION_FAILED,
                started,
                reason_code="provider_nonzero_exit",
                detail=result.stderr.strip() or f"exit code {result.returncode}",
                stdout=result.stdout,
                stderr=result.stderr,
            )

        samples: list[SampleRecord] = []
        metadata: dict[str, Any] = {}
        for line_number, raw_line in enumerate(result.stdout.splitlines(), start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
                if not isinstance(payload, dict):
                    raise ValueError("provider record must be a JSON object")
                record_type = payload.get("record_type")
                if record_type == "metadata":
                    metadata.update(payload)
                    continue
                if record_type != "sample":
                    raise ValueError(f"unknown record_type: {record_type!r}")
                samples.append(
                    SampleRecord(
                        sample_index=int(payload["sample_index"]),
                        elapsed_ns=int(payload["elapsed_ns"]),
                        completed_units=int(payload["completed_units"]),
                        checksum=str(payload["checksum"]),
                        timer=str(payload.get("timer", "unknown")),
                        metrics={
                            key: value
                            for key, value in payload.items()
                            if key
                            not in {
                                "record_type",
                                "sample_index",
                                "elapsed_ns",
                                "completed_units",
                                "checksum",
                                "timer",
                            }
                        },
                    )
                )
            except (json.JSONDecodeError, KeyError, TypeError, ValueError, ValidationError) as exc:
                return self._terminal(
                    item,
                    AttemptState.EXECUTION_FAILED,
                    started,
                    reason_code="provider_invalid_record",
                    detail=f"line {line_number}: {exc}; record={line[:240]}",
                    stdout=result.stdout,
                    stderr=result.stderr,
                    samples=samples,
                    metadata=metadata,
                )

        sample_indices = [sample.sample_index for sample in samples]
        expected_indices = list(range(item.samples_per_attempt))
        if sample_indices != expected_indices:
            return self._terminal(
                item,
                AttemptState.EXECUTION_FAILED,
                started,
                reason_code="provider_sample_sequence_mismatch",
                detail=f"expected indices {expected_indices}, received {sample_indices}",
                stdout=result.stdout,
                stderr=result.stderr,
                samples=samples,
                metadata=metadata,
            )

        return AttemptRecord(
            attempt_id=item.attempt_id,
            state=AttemptState.COMPLETED,
            family_id=item.family_id,
            point_id=item.point_id,
            provider_id=item.provider_id,
            started_at=started,
            finished_at=utc_now(),
            requested_parameters=item.parameters,
            effective_parameters=metadata,
            samples=samples,
            work_output={
                "sample_checksums": [sample.checksum for sample in samples],
                "completed_units": sum(sample.completed_units for sample in samples),
            },
            warnings=[result.stderr.strip()] if result.stderr.strip() else [],
            provider_stdout=result.stdout,
            provider_stderr=result.stderr,
        ).with_semantic_id()


def python_provider(module: str, provider_id: str) -> SubprocessProvider:
    return SubprocessProvider(ProviderCommand(provider_id=provider_id, argv=[sys.executable, "-m", module]))
