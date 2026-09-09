"""Start/stop isolated PostgreSQL16 on Windows without installing a system service.

Download the Windows16 archive from the official EDB binary page to .runtime/postgresql.zip.
Only that task-local runtime is extracted. This script never changes any existing database.
"""
import argparse
import os
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["start", "stop", "status"])
    args = parser.parse_args()
    binary = RUNTIME / "pgsql/bin"
    data = RUNTIME / "data"
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

    def run(name, *arguments, check=True):
        return subprocess.run([str(binary / (name + ".exe")), *map(str, arguments)],
                              check=check, creationflags=flags, capture_output=True, text=True)

    if args.action == "start":
        if not (binary / "pg_ctl.exe").exists():
            with zipfile.ZipFile(RUNTIME / "postgresql.zip") as archive:
                for item in archive.infolist():
                    target = (RUNTIME / item.filename).resolve()
                    if not target.is_relative_to(RUNTIME.resolve()):
                        raise ValueError("Unsafe archive path")
                    # Database binaries and PostgreSQL own library/share files only; omit pgAdmin.
                    if item.filename.startswith(("pgsql/bin/", "pgsql/lib/", "pgsql/share/")):
                        archive.extract(item, RUNTIME)
        if not (data / "PG_VERSION").exists():
            password = RUNTIME / "fixture-password"
            password.write_text("abr_fixture\n")
            try:
                result = run("initdb", "-D", data, "-U", "abr_fixture", "--pwfile", password,
                             "--auth=scram-sha-256", "--encoding=UTF8", "--locale=C")
                print(result.stdout)
            finally:
                password.unlink(missing_ok=True)
            with (data / "postgresql.conf").open("a") as stream:
                stream.write("\nlisten_addresses='127.0.0.1'\nport=55432\nmax_connections=30\nshared_buffers='64MB'\n")
        if run("pg_ctl", "-D", data, "status", check=False).returncode != 0:
            # Do not give the background server inherited PIPE handles: on Windows they can
            # keep subprocess.communicate waiting after pg_ctl itself has exited.
            subprocess.run([str(binary / "pg_ctl.exe"), "-D", str(data), "-l",
                            str(RUNTIME / "postgres.log"), "-w", "start"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           creationflags=flags, check=True, timeout=45)
        os.environ["PGPASSWORD"] = "abr_fixture"
        result = run("psql", "-h", "127.0.0.1", "-p", "55432", "-U", "abr_fixture", "-d", "postgres",
                     "-tAc", "SELECT 1 FROM pg_database WHERE datname='abr_fixture'")
        if result.stdout.strip() != "1":
            run("createdb", "-h", "127.0.0.1", "-p", "55432", "-U", "abr_fixture", "abr_fixture")
        print(run("postgres", "--version").stdout.strip())
    else:
        print(run("pg_ctl", "-D", data, args.action, check=False).stdout)


if __name__ == "__main__":
    main()
