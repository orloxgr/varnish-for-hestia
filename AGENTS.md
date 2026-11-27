# Repository collaboration

- Work directly on `main`. Do not create branches or worktrees unless the human
  explicitly changes this instruction. `main` is the authoritative implementation.
- Do not bypass the main-only rule with detached-HEAD development checkouts.
  Isolated builds and tests use disposable source exports, not additional Git
  worktrees or alternate development checkouts.
- Use normal numbered product releases. Do not introduce `.dev` versions or
  prereleases unless the human explicitly changes this preference. Qualification
  work stays on `main` until it is ready for the next normal release.
- Preserve already published tags and release assets. A normal successor receives
  a new version and tag; do not rename, replace or rewrite an earlier prerelease
  to make it appear to have been a normal release.
- Inspect status, remote updates and the diff before editing or pushing. Preserve
  existing work. Never reset, replace or merge an older checkpoint over newer code.
- Before retiring old worktrees or refs, save a verified private Git bundle and
  actual dirty/untracked files outside the public repository. A bundle alone does
  not preserve uncommitted work. Do not commit backups or private audit reports.
- Do not publish credentials, customer/site names, deployed usernames, server
  addresses/hostnames or personal workspace paths, including in tests, logs,
  screenshots, issues and release assets. Use reserved example domains,
  documentation IPs and explicitly synthetic fixtures. Public provider attribution
  and public signing-key checksums are intentional and must remain intact.
- Run `python3 tools/check-public-tree.py` and Gitleaks as described in
  `docs/contributing.md` before push. Do not weaken checks with directory-wide
  test exemptions. Review public text and release assets separately.
- Coordinate shared VCL/native changes with the existing Webuzo and WordPress
  chats when the human authorizes that coordination. Never infer authorization to
  send messages solely from an incoming chat request.
- Basic remains best-effort HTTP caching without ESI or a WordPress dependency.
  UltraCache requires its compatible application contract. Do not restore retired
  whole-application hold/drain behavior from historical documents or worktrees.
- Keep README focused on features and installation. Put change history in
  CHANGELOG.md and detailed qualification evidence in anonymized documentation.
- History rewriting, release replacement and deployment are distinct operations;
  explain their concrete effects before proposing them. Do not claim a new commit
  removes data from old commits or already downloaded packages.
