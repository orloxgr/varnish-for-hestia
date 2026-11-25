# Contributions and public-data checks

This repository uses `main` for development. Preserve existing changes and review
the diff before committing; do not create a feature branch by default.

Before pushing, run from the repository root with Gitleaks 8.30.1 installed:

```sh
python3 tools/check-public-tree.py
gitleaks git --config .gitleaks.toml --redact --log-opts=--all .
```

The CI workflow repeats these checks. The privacy check inspects tracked working
files for private artifact filenames, personal/deployed paths, private-key material
and non-documentation IPv4 addresses. An optional
`--denylist-file /path/outside/repository/identifiers.txt`
also checks known private identifiers locally, without printing their values.
Do not commit that file. Neither tool can identify every customer name, hostname,
IPv6 address or sensitive fact automatically: inspect the diff, public prose and
release archives too. Do not upload private reports as CI artifacts.

The Gitleaks configuration retains all upstream rules. Its exceptions combine an
exact file path with the specific public checksum declaration or synthetic vector
field, rather than skipping directories or all fixture content. If a finding is
real, remove it and assess its old copies; do not add an exception to silence it.

Use `example.com`, `.example`/`.test`, documentation IP ranges and invented
accounts in examples. Never copy a production configuration, database dump,
request cookie, private workspace path or raw customer log into Git. Provider
names, public upstream URLs and license attribution are public reference data.

The local pre-push hook may be installed by copying `tools/pre-push` to the path
reported by `git rev-parse --git-path hooks/pre-push`. It requires Python 3 and
Gitleaks; `PYTHON` and `GITLEAKS` may specify their executable paths. It checks the
current tracked working tree and committed history, not untracked files or release
assets. It does not install packages or change website configuration.
