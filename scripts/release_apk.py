import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


def run(*args, **kwargs):
    return subprocess.check_output(args, text=True, **kwargs).strip()


def is_current():
    head = run("git", "ls-remote", "origin", "refs/heads/apk-builds").split()[0]
    return head == os.environ["GITHUB_SHA"]


if not is_current():
    print("A newer APK is queued; skipping this superseded publication.")
    raise SystemExit(0)

manifest = json.loads(Path("incoming/release.json").read_text())
version = manifest["version"]
if not re.fullmatch(r"[0-9A-Za-z][0-9A-Za-z.+-]{0,63}", version):
    raise ValueError("Invalid app version")
run_id = int(manifest["run_id"])
attempt = int(manifest["run_attempt"])
version_code = int(manifest["version_code"])
apk = Path("incoming/app-release.apk")
digest = hashlib.file_digest(apk.open("rb"), "sha256").hexdigest()
if digest != manifest["sha256"]:
    raise ValueError("APK checksum does not match the verified build")

checksum = Path(os.environ["RUNNER_TEMP"]) / "SHA256SUMS.txt"
checksum.write_text(f"{digest}  app-release.apk\n")
notes = Path(os.environ["RUNNER_TEMP"]) / "release-notes.md"
notes.write_text(
    f"## Noctyra {version}\n\n"
    "APK oficial publicado automaticamente após testes, build e verificação da assinatura.\n\n"
    "Baixe **app-release.apk** abaixo. Requer Android 8.0 ou superior.\n\n"
    f"Versão: **{version}** · Código: **{version_code}** · Build: **{run_id}.{attempt}**.\n\n"
    "O arquivo é o APK original da build, sem recompilação.\n\n"
    f"### SHA-256\n\n```text\n{digest}\n```\n\n"
    "Esta página distribui somente o aplicativo compilado. O código do app permanece privado.\n"
)
repo = os.environ["GITHUB_REPOSITORY"]
tag = f"android-v{version}-build.{run_id}.{attempt}"
exists = subprocess.run(
    ["gh", "release", "view", tag, "--repo", repo],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
).returncode == 0
if not exists:
    subprocess.run([
        "gh", "release", "create", tag, "--repo", repo,
        "--target", os.environ["GITHUB_SHA"], "--draft",
        "--title", f"Noctyra {version} — build {run_id}.{attempt}",
        "--notes-file", str(notes),
    ], check=True)
subprocess.run([
    "gh", "release", "upload", tag, str(apk), str(checksum),
    "--repo", repo, "--clobber",
], check=True)
if not is_current():
    print("A newer APK arrived; leaving this build unpublished.")
    raise SystemExit(0)
subprocess.run([
    "gh", "release", "edit", tag, "--repo", repo,
    "--draft=false", "--latest", "--notes-file", str(notes),
], check=True)
print(f"Published: https://github.com/{repo}/releases/tag/{tag}")
