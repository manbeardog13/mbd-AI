"""Core-owned verification profiles and the fail-closed production backend.

This module intentionally contains no process-launching implementation.  M2
establishes the authority, evidence, and policy boundary first; an isolated
executor can only be added as a separately reviewed backend.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping, Protocol

from .contracts import (
    VerificationBackendCapabilities,
    VerificationProfile,
    VerificationStatus,
)


EMPTY_SHA256 = sha256(b"").hexdigest()
MAX_OUTPUT_EXCERPT = 4096
MAX_DETAIL = 1000
_SHA256 = re.compile(r"[0-9a-f]{64}")


class VerificationPolicyError(RuntimeError):
    """Raised when a profile or backend cannot satisfy Core policy."""


def canonical_json(value: Mapping[str, Any] | list[Any]) -> str:
    """Return the one JSON representation used by manifests and receipts."""
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def canonical_digest(value: Mapping[str, Any] | list[Any]) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class VerificationExecutionResult:
    """Bounded facts returned by a backend; Core decides their authority."""

    status: VerificationStatus
    exit_code: int | None = None
    duration_ms: int = 0
    stdout_sha256: str = EMPTY_SHA256
    stderr_sha256: str = EMPTY_SHA256
    stdout_excerpt: str = ""
    stderr_excerpt: str = ""
    output_truncated: bool = False
    error_code: str | None = None
    detail: str = ""

    def as_evidence(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data


def bounded_execution_result(
    result: VerificationExecutionResult,
) -> VerificationExecutionResult:
    """Validate hashes and bound untrusted backend-provided display text."""

    if (
        type(result) is not VerificationExecutionResult
        or type(result.status) is not VerificationStatus
        or (
            result.exit_code is not None
            and (type(result.exit_code) is not int or abs(result.exit_code) > 2**31)
        )
        or (
            result.status is VerificationStatus.PASSED
            and (type(result.exit_code) is not int or result.exit_code != 0)
        )
        or type(result.duration_ms) is not int
        or result.duration_ms < 0
        or type(result.stdout_sha256) is not str
        or type(result.stderr_sha256) is not str
        or not _SHA256.fullmatch(result.stdout_sha256)
        or not _SHA256.fullmatch(result.stderr_sha256)
        or type(result.stdout_excerpt) is not str
        or type(result.stderr_excerpt) is not str
        or type(result.output_truncated) is not bool
        or (result.error_code is not None and type(result.error_code) is not str)
        or (
            isinstance(result.error_code, str)
            and any(ord(character) < 32 for character in result.error_code)
        )
        or type(result.detail) is not str
    ):
        return VerificationExecutionResult(
            status=VerificationStatus.ERROR,
            error_code="VERIFICATION_RESULT_INVALID",
            detail="The verification backend returned an invalid evidence contract.",
        )

    def clean(value: str, limit: int) -> tuple[str, bool]:
        text = "".join(
            character
            for character in value
            if character in "\n\r\t" or ord(character) >= 32
        )
        encoded = text.encode("utf-8", errors="replace")
        if len(encoded) <= limit:
            return text, False
        clipped = encoded[:limit].decode("utf-8", errors="ignore")
        return clipped, True

    stdout, stdout_cut = clean(result.stdout_excerpt, MAX_OUTPUT_EXCERPT)
    stderr, stderr_cut = clean(result.stderr_excerpt, MAX_OUTPUT_EXCERPT)
    detail, detail_cut = clean(result.detail, MAX_DETAIL)
    return VerificationExecutionResult(
        status=result.status,
        exit_code=result.exit_code,
        duration_ms=result.duration_ms,
        stdout_sha256=result.stdout_sha256,
        stderr_sha256=result.stderr_sha256,
        stdout_excerpt=stdout,
        stderr_excerpt=stderr,
        output_truncated=result.output_truncated or stdout_cut or stderr_cut or detail_cut,
        error_code=(result.error_code[:200] if result.error_code else None),
        detail=detail,
    )


_CAPABILITY_BOOLEAN_FIELDS = (
    "execution_available",
    "network_disabled",
    "rootfs_readonly",
    "snapshot_readonly",
    "runs_as_nonroot",
    "host_credentials_unavailable",
    "host_devices_unavailable",
    "docker_socket_unavailable",
    "child_process_limit",
    "memory_limit_supported",
    "cpu_limit_supported",
    "timeout_supported",
    "output_limit_supported",
    "no_new_privileges",
    "capabilities_dropped",
    "test_only",
)


def validate_backend_capabilities(
    capabilities: VerificationBackendCapabilities,
) -> VerificationBackendCapabilities:
    """Reject truthy impostors and subclasses at the authority boundary."""

    if type(capabilities) is not VerificationBackendCapabilities:
        raise VerificationPolicyError("verification backend capability type is invalid")
    for name in ("backend_id", "backend_version", "isolation_level", "os_family"):
        value = getattr(capabilities, name)
        if (
            type(value) is not str
            or not value.strip()
            or len(value) > 200
            or any(ord(character) < 32 for character in value)
        ):
            raise VerificationPolicyError(
                f"verification backend capability field is invalid: {name}"
            )
    for name in _CAPABILITY_BOOLEAN_FIELDS:
        if type(getattr(capabilities, name)) is not bool:
            raise VerificationPolicyError(
                f"verification backend capability field is not boolean: {name}"
            )
    return capabilities


class VerificationRunner(Protocol):
    """Dependency-injection seam for reviewed isolation backends."""

    @property
    def capabilities(self) -> VerificationBackendCapabilities: ...

    def run(
        self,
        profile: VerificationProfile,
        *,
        run_id: str,
        task_id: str,
        worktree: str,
    ) -> VerificationExecutionResult: ...


class DisabledRunner:
    """The only production backend in M2; it never launches a process."""

    @property
    def capabilities(self) -> VerificationBackendCapabilities:
        return VerificationBackendCapabilities(
            backend_id="nero.disabled.v1",
            backend_version="1",
            execution_available=False,
            isolation_level="disabled",
            os_family="none",
            network_disabled=False,
            rootfs_readonly=False,
            snapshot_readonly=False,
            runs_as_nonroot=False,
            host_credentials_unavailable=False,
            host_devices_unavailable=False,
            docker_socket_unavailable=False,
            child_process_limit=False,
            memory_limit_supported=False,
            cpu_limit_supported=False,
            timeout_supported=False,
            output_limit_supported=False,
            no_new_privileges=False,
            capabilities_dropped=False,
            test_only=False,
        )

    def run(
        self,
        profile: VerificationProfile,
        *,
        run_id: str,
        task_id: str,
        worktree: str,
    ) -> VerificationExecutionResult:
        del profile, run_id, task_id, worktree
        return VerificationExecutionResult(
            status=VerificationStatus.BACKEND_UNAVAILABLE,
            error_code="VERIFICATION_BACKEND_DISABLED",
            detail=(
                "No approved isolated verification backend is enabled. "
                "Core did not start a process."
            ),
        )


class VerificationProfileRegistry:
    """Build the code-owned, content-addressed profile catalog.

    The harness is resolved from the installed Core source rather than from a
    task-supplied path. Its hash participates in the manifest digest, so an
    already-pinned task fails closed if the reviewed harness changes.
    """

    PROFILE_ID = "mission-control.offline.v1"

    def __init__(self, source_root: str | Path | None = None) -> None:
        self.source_root = (
            Path(source_root).resolve()
            if source_root is not None
            else Path(__file__).resolve().parents[2]
        )

    def profiles(self) -> tuple[VerificationProfile, ...]:
        return (self._mission_control_profile(),)

    def get(self, profile_id: str) -> VerificationProfile:
        normalized = str(profile_id).strip()
        for profile in self.profiles():
            if profile.profile_id == normalized:
                return profile
        raise VerificationPolicyError(f"unknown verification profile: {normalized}")

    def resolve(
        self,
        profile_id: str,
        *,
        version: int | None = None,
        digest: str | None = None,
    ) -> VerificationProfile:
        profile = self.get(profile_id)
        if version is not None and profile.version != int(version):
            raise VerificationPolicyError("verification profile version drift")
        if digest is not None and profile.manifest_digest != str(digest):
            raise VerificationPolicyError("verification profile digest drift")
        return profile

    def catalog_digest(self) -> str:
        return canonical_digest(
            [
                {
                    "profile_id": item.profile_id,
                    "version": item.version,
                    "manifest_digest": item.manifest_digest,
                }
                for item in self.profiles()
            ]
        )

    @staticmethod
    def backend_satisfies(
        profile: VerificationProfile,
        capabilities: VerificationBackendCapabilities,
        *,
        authorized_backend_ids: frozenset[str],
        allow_test_authority: bool = False,
    ) -> tuple[bool, tuple[str, ...]]:
        try:
            validate_backend_capabilities(capabilities)
        except VerificationPolicyError:
            return False, ("capability_contract",)
        missing: list[str] = []
        if not capabilities.execution_available:
            missing.append("execution_available")
        if capabilities.backend_id not in authorized_backend_ids:
            missing.append("backend_authorization")
        if (
            profile.required_os_family != "any"
            and capabilities.os_family != profile.required_os_family
        ):
            missing.append("os_family")
        if capabilities.test_only and not allow_test_authority:
            missing.append("test_only_backend")
        for name in profile.required_capabilities:
            if not bool(getattr(capabilities, name, False)):
                missing.append(name)
        return not missing, tuple(sorted(set(missing)))

    def _mission_control_profile(self) -> VerificationProfile:
        relative = Path("verify") / "verify_mission_control.py"
        harness_paths = (
            relative,
            Path("tests/test_nero_core.py"),
            Path("tests/test_repository_leases.py"),
            Path("tests/test_mission_control_git.py"),
            Path("tests/test_mission_control_service.py"),
            Path("tests/test_mission_control_api.py"),
            Path("tests/test_mission_control_m2_api.py"),
            Path("tests/test_mission_control_static.py"),
            Path("tests/test_mission_control_verification.py"),
            Path("tests/test_mission_control_migrations.py"),
        )
        harness_files: list[dict[str, str]] = []
        try:
            for path in harness_paths:
                harness_files.append(
                    {
                        "path": path.as_posix(),
                        "sha256": sha256((self.source_root / path).read_bytes()).hexdigest(),
                    }
                )
        except OSError as exc:
            raise VerificationPolicyError(
                f"trusted verification harness unavailable: {path.as_posix()}"
            ) from exc
        harness_hash = harness_files[0]["sha256"]
        manifest: dict[str, Any] = {
            "profile_id": self.PROFILE_ID,
            "version": 1,
            "display_name": "Mission Control offline suite",
            "description": (
                "Reviewed deterministic Core, API, migration, and interface checks."
            ),
            "command_label": "Mission Control offline verification suite",
            "harness_relative_path": relative.as_posix(),
            "harness_sha256": harness_hash,
            "harness_files": harness_files,
            "required_os_family": "windows",
            "required_capabilities": [
                "network_disabled",
                "rootfs_readonly",
                "snapshot_readonly",
                "runs_as_nonroot",
                "host_credentials_unavailable",
                "host_devices_unavailable",
                "docker_socket_unavailable",
                "child_process_limit",
                "memory_limit_supported",
                "cpu_limit_supported",
                "timeout_supported",
                "output_limit_supported",
                "no_new_privileges",
                "capabilities_dropped",
            ],
            "timeout_seconds": 600,
        }
        return VerificationProfile(
            profile_id=str(manifest["profile_id"]),
            version=int(manifest["version"]),
            display_name=str(manifest["display_name"]),
            description=str(manifest["description"]),
            command_label=str(manifest["command_label"]),
            harness_relative_path=str(manifest["harness_relative_path"]),
            harness_sha256=str(manifest["harness_sha256"]),
            harness_files=tuple(dict(item) for item in manifest["harness_files"]),
            required_os_family=str(manifest["required_os_family"]),
            required_capabilities=tuple(manifest["required_capabilities"]),
            timeout_seconds=int(manifest["timeout_seconds"]),
            manifest_digest=canonical_digest(manifest),
        )


__all__ = [
    "DisabledRunner",
    "VerificationExecutionResult",
    "VerificationPolicyError",
    "VerificationProfileRegistry",
    "VerificationRunner",
    "bounded_execution_result",
    "canonical_digest",
    "canonical_json",
    "validate_backend_capabilities",
]
