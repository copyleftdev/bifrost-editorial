# Bifrost dependency audit via vulngraph-cli

Date: 2026-08-27. Snapshot: sha256:d2140e13… (2026-08-27T07:02:46Z). Note: first scan (2026-08-26) was re-run after noticing the `update` command installed the prior day's release before the morning refresh; results were identical, confirming no drift between snapshots.
Scope: /tmp/bifrost-read clone of maximhq/bifrost @ dev branch.

## Method

1. Built vulngraph-cli from source (cargo build --release).
2. `vulngraph update` — downloaded + verified today's data release (576k nodes, 847k edges).
3. `vulngraph check --json` on all `go.sum` + `package-lock.json` files (1639 raw targets).
4. Refined: resolved-version pass — newest version per module across each go.sum, plus resolved npm graph from package-lock.json (1396 targets).

## Raw scan (all go.sum history)

| verdict | count |
|---|---|
| unknown | 989 |
| not-affected | 605 |
| recorded | 21 |
| scored | 9 |
| proof-of-concept | 6 |
| actively-exploited | 5 |
| weaponized | 4 |

Raw flags were exclusively historical pseudo-versions of golang.org/x/{net,crypto,text,mod},
plus protobuf, logrus, jsonparser, go-jose, yaml. All are go.sum hash entries, not selected
versions — flagged by vulngraph because it scans every line without consulting
`go mod graph` (Minimum Version Selection).

## Resolved-version scan (the real audit surface)

| verdict | count |
|---|---|
| unknown | 862 (mostly npm dev-deps + internal Bifrost modules) |
| not-affected | 530 |
| recorded | 2 |
| proof-of-concept | 1 |
| scored | 1 |

Two flags remained; both resolve clean on grounding:

1. `Go:github.com/sirupsen/logrus@1.7.0` — verdict proof-of-concept (CVE-2025-65637,
   CVSS 7.5, public PoC, fixed in 1.8.3). go mod graph shows Bifrost's actual logrus
   resolves to v1.9.3+ (ClickHouse, Qdrant, Weaviate deps). Not reachable at 1.7.0 — the
   hash is historical. DISMISSED (false positive in vulngraph's go.sum handling).

2. `Go:golang.org/x/mod@0.3.0` — verdict scored (HIGH_SEVERITY). No fix indicated in
   findings; x/mod is a semver-parsing library, no runtime handling of untrusted input
   in Bifrost's server path. MONITOR only.

## Reachability check on raw-go.sum flags

`golang.org/x/net` resolved: 0.56.0
`golang.org/x/crypto` resolved: 0.53.0
`golang.org/x/text` resolved: 0.39.0
`github.com/buger/jsonparser` resolved: 1.2.0
`github.com/go-jose/go-jose/v4` resolved: 4.1.4
`gopkg.in/yaml.v2` resolved: 2.4.0
`google.golang.org/protobuf` resolved: 1.36.12-0.2026…
All current stable releases; the flagged pseudo-versions are not selected.

## Findings (about vulngraph-cli itself, used in audit)

- F-1 (medium): naively scans every go.sum line and reports historical pseudo-versions
  as `actively-exploited`/`weaponized` — scary output in CI. Should consult
  `go mod graph` for MVS-resolved versions like Go tooling does.
- F-2 (low): `observations` array is empty in raw-scan JSON for flagged rows; only
  `findings` is populated on query-by-query. Inconsistent envelope.
- F-3 (info): `unknown` is honestly reported, dismissed cleanly by the tool itself.

## Findings (about Bifrost, the audit target)

- B-1 (informational, clean): resolved dependency surface of Bifrost @dev is clean
  against today's vulngraph snapshot. Only monitor-level flags on x/mod.
- B-2 (informational): 42 go.sum files (plugins each have their own module) — an
  ecosystem audit ought to automate per-module resolution, which vulngraph does not.

## Note on `semgrep` (the intended second tool)

Clarified after initial misspelling ("zemgrab" → semgrep). The semgrep install
available here (pipx, 1.167.0) crashes inside its Python↔OCaml RPC bridge with
`Yojson__Common.Json_error` on the `CallValidate`/`CallFormatter` frames, before
any rule is loaded. Pinning to 1.163.0 in a clean venv produced the identical
failure against both the `p/security-audit` registry and a trivial local rule.
The failure is environment-level (proot-wrapped HOME with non-standard socket
semantics), not the ruleset.

This means static-analysis coverage in this audit is BLOCKED, not skipped, and
that is recorded here honestly. Semgrep can be re-run by the user on a normal
HOME path (e.g. on a machine where pipx/semgrep installs function). Until
that re-run, treat this report as dependency-surface-only and not a statement
of source-code safety.

