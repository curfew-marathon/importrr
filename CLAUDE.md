# CLAUDE.md

importrr automates importing image/movie files into a photo library, wrapping
Phil Harvey's ExifTool. See [README.md](README.md) for the full workflow and
config.

CI (Python 3.11): `ruff check .`, `ruff format --check .`, `mypy .`,
`pytest --cov` (with `PYTHONPATH=.:src`).

## Canonical run scripts

`start.sh` and `stop.sh` are shared across the curfew-marathon deploy repos
(hivemind, importrr, uploadrr, prometheus, grafana) and are kept **byte-identical
outside the fences**. Only the `# >>> project-specific` ... `# <<< project-specific`
blocks, the header comment, the `--help` line range, and the `.env` bootstrap
messages may differ between repos. **hivemind is the reference.**

Interface: `./start.sh` builds from source; `./start.sh --pull` runs the published
image; `./start.sh --no-build` runs whatever image is already local. `./stop.sh`
takes it down (`--volumes` also drops the local NFS mount handles; `--images`
also removes the first-party image). `wait_for_health` polls the compose
healthcheck.

To change anything outside the fences: edit it in **hivemind** first, run
`scripts/canonical-hash.sh` to get the new hash, set `EXPECTED=` in that script,
then copy `start.sh` + `stop.sh` + `scripts/canonical-hash.sh` here. The
`canonical-scripts` CI job fails if this repo's shared block drifts.
