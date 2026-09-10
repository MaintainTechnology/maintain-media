"""Escrow newly generated engine keys and install them at two fixed targets.

Default invocation is review-only. --apply may resume its own DPAPI escrow;
it never reads an existing .env, AWS credential store or remote runtime.env.
Only the dedicated website assertion key is installed into Vercel. The live
connection mode/origin are intentionally left for a later verified deployment.
"""
from __future__ import annotations

import base64
import ctypes
import hashlib
import json
import os
import secrets
import stat
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

from provision_runtime import validate_material

PROJECT = "prj_0jiFRBJLqKpgwyClzI4bl1qn1a12"
SCOPE = "maintain-technology"
HOST = "ubuntu@3.104.119.142"
NODE = Path("C:/nvm4w/nodejs/node.exe")
NODE_TARGET = Path("C:/Users/dalig/AppData/Local/nvm/v22.22.2/node.exe")
VERCEL = Path("C:/Users/dalig/AppData/Roaming/npm/node_modules/vercel/dist/index.js")
REMOTE = ("sudo env PYTHONPATH=/opt/abn-leadgen/src /opt/abn-leadgen/.venv/bin/python "
          "/home/ubuntu/abn-host-bootstrap-20260910/provision_runtime.py --apply")
ENTROPY = b"MaintainMedia/ABN/new-runtime-keys/20260910/v1"
STAGES = {"prepared", "remote_pending", "remote_ready", "vercel_pending", "complete"}


class ProvisionFailure(RuntimeError):
    """Messages are fixed codes only; never wrap provider exception text."""


def run_process(command, *, data=None, timeout=60, environment=None):
    try:
        result = subprocess.run(command, input=data, capture_output=True, timeout=timeout,
                                check=False, shell=False, env=environment,
                                creationflags=0x08000000 if os.name == "nt" else 0)
    except (OSError, subprocess.SubprocessError):
        raise ProvisionFailure("COMMAND_RESULT_UNCONFIRMED") from None
    if len(result.stdout) > 65_536 or len(result.stderr) > 65_536:
        raise ProvisionFailure("COMMAND_RESULT_UNCONFIRMED")
    return result


def ordinary(path):
    """Reject symbolic links and Windows reparse points, including parent hops."""
    if not path.is_absolute():
        raise ProvisionFailure("ABSOLUTE_PATH_REQUIRED")
    for entry in (path, *path.parents):
        if entry.exists() or entry.is_symlink():
            info = entry.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise ProvisionFailure("REPARSE_PATH_REFUSED")


def powershell(script, *, path=None):
    executable = Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    environment = dict(os.environ)
    # Do not inherit PowerShell 7/user module resolution into Windows PowerShell.
    environment["PSModulePath"] = str(executable.parent / "Modules")
    if path is not None:
        environment["ABR_NEW_ESCROW_PATH"] = str(path)
    result = run_process([str(executable), "-NoProfile", "-NonInteractive", "-Command", script],
                         environment=environment)
    if result.returncode != 0:
        raise ProvisionFailure("ESCROW_ACL_UNAVAILABLE")
    return result.stdout.decode("utf-8-sig").strip()


def secure_directory(path):
    ordinary(path)
    if not path.exists():
        path.mkdir(parents=True)
        ordinary(path)
        # Establish the protected, current-user-only DACL before any key exists.
        powershell("""$ErrorActionPreference='Stop'
$sid=[System.Security.Principal.WindowsIdentity]::GetCurrent().User
$acl=New-Object System.Security.AccessControl.DirectorySecurity
$acl.SetAccessRuleProtection($true,$false)
$acl.SetOwner($sid)
$rule=New-Object System.Security.AccessControl.FileSystemAccessRule($sid,'FullControl','ContainerInherit,ObjectInherit','None','Allow')
$acl.AddAccessRule($rule)
Set-Acl -LiteralPath $env:ABR_NEW_ESCROW_PATH -AclObject $acl
""", path=path)
    verify_acl(path, directory=True)


def verify_acl(path, *, directory=False):
    ordinary(path)
    result = powershell("""$ErrorActionPreference='Stop'
$sid=[System.Security.Principal.WindowsIdentity]::GetCurrent().User
$acl=Get-Acl -LiteralPath $env:ABR_NEW_ESCROW_PATH
$rules=@($acl.GetAccessRules($true,$true,[System.Security.Principal.SecurityIdentifier]))
$valid=$acl.GetOwner([System.Security.Principal.SecurityIdentifier]).Value -eq $sid.Value
if ($env:ABR_NEW_ESCROW_IS_DIRECTORY -eq 'yes') {$valid=$valid -and $acl.AreAccessRulesProtected}
$valid=$valid -and $rules.Count -gt 0
foreach ($rule in $rules) {$valid=$valid -and $rule.IdentityReference.Value -eq $sid.Value -and $rule.AccessControlType -eq 'Allow' -and $rule.FileSystemRights -eq 'FullControl'}
if (-not $valid) {exit 2}
Write-Output 'current_user_only'
""".replace("$env:ABR_NEW_ESCROW_IS_DIRECTORY -eq 'yes'", "$true" if directory else "$false"), path=path)
    if result != "current_user_only":
        raise ProvisionFailure("ESCROW_ACL_UNAVAILABLE")


def dpapi(data: bytes, *, decrypt=False) -> bytes:
    if os.name != "nt":
        raise ProvisionFailure("WINDOWS_USER_DPAPI_REQUIRED")

    class Blob(ctypes.Structure):
        _fields_ = [("size", ctypes.c_ulong), ("data", ctypes.POINTER(ctypes.c_ubyte))]

    def blob(value):
        backing = ctypes.create_string_buffer(value)
        return Blob(len(value), ctypes.cast(backing, ctypes.POINTER(ctypes.c_ubyte))), backing

    source, source_buffer = blob(data)
    entropy, entropy_buffer = blob(ENTROPY)
    output = Blob()
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    method = crypt32.CryptUnprotectData if decrypt else crypt32.CryptProtectData
    method.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.POINTER(Blob), ctypes.c_void_p,
                       ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(Blob)]
    method.restype = ctypes.c_int
    # CRYPTPROTECT_UI_FORBIDDEN only. Never use CRYPTPROTECT_LOCAL_MACHINE.
    if not method(ctypes.byref(source), None, ctypes.byref(entropy), None, None, 1, ctypes.byref(output)):
        raise ProvisionFailure("USER_DPAPI_UNAVAILABLE")
    try:
        return ctypes.string_at(output.data, output.size)
    finally:
        kernel32.LocalFree(output.data)
        # Keep both input backing allocations alive until the native call ends.
        del source_buffer, entropy_buffer


def canonical(material):
    return json.dumps(material, sort_keys=True, separators=(",", ":")).encode()


def fresh_state():
    from cryptography.fernet import Fernet

    material = {"encryption_key": Fernet.generate_key().decode(),
                "lookup_key": base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
                "signing_key": secrets.token_urlsafe(48), "wrapping_key": Fernet.generate_key().decode(),
                "website_assertion_key": secrets.token_urlsafe(48)}
    validate_material(material)
    return {"version": 1, "project": PROJECT, "scope": SCOPE, "host": HOST, "mode": "pilot",
            "stage": "prepared", "material_sha256": hashlib.sha256(canonical(material)).hexdigest(),
            "material": material}


def validate_state(state):
    if (not isinstance(state, dict) or set(state) != {"version", "project", "scope", "host", "mode",
                                                    "stage", "material_sha256", "material"}
            or state["version"] != 1 or state["project"] != PROJECT or state["scope"] != SCOPE
            or state["host"] != HOST or state["mode"] != "pilot" or state["stage"] not in STAGES):
        raise ProvisionFailure("ESCROW_TARGET_MISMATCH")
    validate_material(state["material"])
    if state["material_sha256"] != hashlib.sha256(canonical(state["material"])).hexdigest():
        raise ProvisionFailure("ESCROW_MATERIAL_MISMATCH")
    return state


class Escrow:
    def __init__(self, path):
        self.path = path

    def load(self):
        verify_acl(self.path)
        if self.path.stat().st_size > 32_768:
            raise ProvisionFailure("ESCROW_SIZE_INVALID")
        return validate_state(json.loads(dpapi(self.path.read_bytes(), decrypt=True)))

    def recover(self):
        temporary = self.path.with_name(self.path.name + ".next")
        ordinary(temporary)
        if not temporary.exists():
            return
        staged = Escrow(temporary).load()
        if self.path.exists():
            current = self.load()
            if staged["material_sha256"] != current["material_sha256"]:
                raise ProvisionFailure("ESCROW_MATERIAL_MISMATCH")
            # The older durable state can replay either fixed target safely.
            temporary.unlink()
        else:
            # A crash after the first encrypted write must never create new keys.
            os.replace(temporary, self.path)
            verify_acl(self.path)

    def save(self, state):
        validate_state(state)
        verify_acl(self.path.parent, directory=True)
        ordinary(self.path)
        if self.path.exists():
            verify_acl(self.path)
        temporary = self.path.with_name(self.path.name + ".next")
        ordinary(temporary)
        encrypted = dpapi(canonical(state))
        descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                verify_acl(temporary)
                stream.write(encrypted)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            verify_acl(self.path)
        finally:
            if temporary.exists():
                temporary.unlink()


def commands(base):
    ssh = Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32/OpenSSH/ssh.exe"
    identity = base / "keys/abn-leadgen-sydney-20260910"
    known_hosts = base / "known_hosts"
    if NODE.resolve(strict=True) != NODE_TARGET.resolve(strict=True):
        raise ProvisionFailure("APPROVED_NODE_TARGET_CHANGED")
    for path in (ssh, identity, known_hosts, NODE_TARGET, VERCEL):
        ordinary(path)
        if not path.is_file():
            raise ProvisionFailure("REQUIRED_EXECUTABLE_OR_PIN_MISSING")
    return ([str(ssh), "-F", "NUL", "-i", str(identity), "-o", "UserKnownHostsFile=" + str(known_hosts),
             "-o", "GlobalKnownHostsFile=NUL", "-o", "ClearAllForwardings=yes", "-o", "RequestTTY=no",
             "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes", "-o", "ForwardAgent=no",
             "-o", "KexAlgorithms=curve25519-sha256", "-o", "HostKeyAlgorithms=ssh-ed25519",
             "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=15", HOST, REMOTE],
            [str(NODE), str(VERCEL), "env", "add", "ABN_ENGINE_ASSERTION_KEY", "production",
             "--project", PROJECT, "--scope", SCOPE, "--yes", "--force", "--sensitive"])


def coordinate(escrow, ssh_command, vercel_command, *, runner=run_process):
    escrow.recover()
    state = escrow.load() if escrow.path.exists() else fresh_state()
    if not escrow.path.exists():
        escrow.save(state)  # Durable encrypted recovery exists before either external mutation.
    if state["stage"] in {"prepared", "remote_pending"}:
        state["stage"] = "remote_pending"
        escrow.save(state)
        response = runner(ssh_command, data=canonical(state["material"]), timeout=180)
        try:
            receipt = json.loads(response.stdout)
        except (ValueError, TypeError):
            raise ProvisionFailure("REMOTE_INSTALLATION_UNCONFIRMED") from None
        if (response.returncode != 0 or not isinstance(receipt, dict)
                or receipt.get("status") != "private_runtime_configured"
                or receipt.get("mode") != "pilot" or receipt.get("fixture_keys_used") is not False
                or receipt.get("initial_capabilities_enabled") != [] or receipt.get("release_approvals_created") is not False
                or receipt.get("material_sha256") != state["material_sha256"]):
            raise ProvisionFailure("REMOTE_INSTALLATION_UNCONFIRMED")
        state["stage"] = "remote_ready"
        escrow.save(state)
    if state["stage"] in {"remote_ready", "vercel_pending"}:
        state["stage"] = "vercel_pending"
        escrow.save(state)
        response = runner(vercel_command, data=state["material"]["website_assertion_key"].encode(), timeout=180)
        if response.returncode != 0:
            raise ProvisionFailure("VERCEL_INSTALLATION_UNCONFIRMED")
        state["stage"] = "complete"
        escrow.save(state)
    return {"status": "runtime_keys_installed", "stage": state["stage"], "mode": "pilot",
            "escrow": "current_user_dpapi", "website_connection_enabled": False,
            "capabilities_enabled": [], "deployment_performed": False}


@contextmanager
def coordinator_lock(path):
    """An OS-held lock releases on crash/reboot; an old lock file is harmless."""
    import msvcrt

    ordinary(path)
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    acquired = False
    try:
        verify_acl(path)
        if os.fstat(descriptor).st_size == 0:
            os.write(descriptor, b"0")
            os.fsync(descriptor)
        os.lseek(descriptor, 0, os.SEEK_SET)
        try:
            msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            acquired = True
        except OSError:
            raise ProvisionFailure("COORDINATOR_ALREADY_ACTIVE") from None
        yield
    finally:
        if acquired:
            os.lseek(descriptor, 0, os.SEEK_SET)
            msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
        os.close(descriptor)


def apply():
    if os.name != "nt":
        raise ProvisionFailure("WINDOWS_USER_DPAPI_REQUIRED")
    local = os.environ.get("LOCALAPPDATA", "")
    if not local or Path(local).resolve() != Path("C:/Users/dalig/AppData/Local").resolve():
        raise ProvisionFailure("LOCAL_USER_DIRECTORY_REQUIRED")
    base = Path(local) / "MaintainMedia/aws"
    ssh_command, vercel_command = commands(base)
    directory = base / "runtime-key-escrow"
    secure_directory(directory)
    escrow = Escrow(directory / "abn-leadgen-sydney-20260910.dpapi")
    lock_path = directory / "coordinator.lock"
    with coordinator_lock(lock_path):
        return coordinate(escrow, ssh_command, vercel_command)


def main():
    if sys.argv[1:] != ["--apply"]:
        print(json.dumps({"status": "review_only", "target": HOST, "project": PROJECT,
                          "scope": SCOPE, "mode": "pilot", "external_mutations": False}))
        return 0
    try:
        print(json.dumps(apply()))
        return 0
    except Exception:  # noqa: BLE001 - secret-bearing coordinator boundary must never echo exceptions/output
        print(json.dumps({"status": "blocked", "code": "RUNTIME_COORDINATOR_UNCONFIRMED",
                          "resume": "Retain the encrypted escrow and retry the same command; do not generate replacement keys."}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
