---
name: helm-add-gwapi-route
description: Add or modernize Gateway API *Route templates (HTTPRoute/GRPCRoute/TLSRoute/TCPRoute/UDPRoute) in a Helm chart. Auto-detects add-mode (chart has no *Route yet) vs update-mode (existing templates need modernization — outdated apiVersion, unnamed rules, CORS via annotations, HTTPS backend without BackendTLSPolicy). Pure file edits — no git, no PR. TRIGGER proactively when cwd is a Helm chart with templates/ingress.yaml but no *route.yaml, or when existing *Route templates use outdated apiVersion or lack named rules (best practice since v1.4, Nov 2025), or when the user mentions migrating from Ingress to Gateway API. Do not trigger for charts that already have current-spec routes or non-Helm projects.
argument-hint: "[chart-path] [--type=httproute|grpcroute|tlsroute|tcproute|udproute|auto] [--mode=add|update|auto] [--with-backend-tls]"
---

# helm-add-gwapi-route

Add or modernize Gateway API *Route resources inside a Helm chart. The skill only edits files — git operations (branch, commit, push, PR) are left to the caller.

## Arguments

Parse `$ARGUMENTS`:

- First positional = `chart-path`. Default: `cwd`.
- `--type=<list>` — comma-separated subset of `httproute,grpcroute,tlsroute,tcproute,udproute`, or `auto` (default). Controls which route kinds to add (add-mode) or update (update-mode).
- `--mode=add|update|auto` — default `auto`. See Phase 3.
- `--with-backend-tls` — also generate `BackendTLSPolicy` for the chart's Service (useful when the backend Service terminates TLS itself).

## Phase 1 — Locate and validate the chart

1. Resolve `chart-path`. If not provided, walk upward from cwd looking for a directory that contains `Chart.yaml`. If multiple `Chart.yaml` files exist under `charts/*` (umbrella chart), ask the user via AskUserQuestion which chart to operate on; multi-select is allowed — process each selected chart independently.
2. Read `Chart.yaml`. Require `apiVersion: v2`. Capture chart `name` and `version`.
3. Inventory `templates/`:
   - note which of these exist: `ingress.yaml`, `service.yaml`, `deployment.yaml`, `statefulset.yaml`, `_helpers.tpl`
   - note which route templates already exist: `httproute.yaml`, `grpcroute.yaml`, `tlsroute.yaml`, `tcproute.yaml`, `udproute.yaml`, `backendtlspolicy.yaml`
4. Note whether `tests/` exists (used in Phase 8 to decide whether to add helm-unittest tests).
5. Parse `values.yaml`:
   - extract the `ingress:` block — record its indent style (2 vs 4 spaces), field naming (`host` vs `hostname`, `path` vs `paths`, `className` style), whether helm-docs `# -- description` comments are used, and the values of any CORS/auth/rate-limit annotations (these are migration targets in update-mode)
   - extract the `service:` block — port number, port name, `protocol`, `appProtocol`, type
   - detect any existing `gateway:`, `httpRoute:`, `grpcRoute:`, `tlsRoute:`, `tcpRoute:`, `udpRoute:` blocks
6. Read `_helpers.tpl`. Extract the exact helper template names the chart defines — typically `<chart>.fullname`, `<chart>.labels`, `<chart>.selectorLabels`, `<chart>.serviceAccountName`. Use the actual names in generated templates; do not assume the prefix matches the directory name.

## Phase 2 — Verify current Gateway API spec

Training data may be outdated. Before generating any template, fetch current maturity info via WebFetch from:

- https://gateway-api.sigs.k8s.io/concepts/versioning/
- https://kubernetes.io/blog/ (search for the latest Gateway API release post)

Build a fresh status table. Typical expectations as of April 2026 (verify each time):

| Resource | apiVersion | Status |
|---|---|---|
| HTTPRoute | gateway.networking.k8s.io/v1 | Standard (GA since v1.0) |
| GRPCRoute | gateway.networking.k8s.io/v1 | Standard (GA since v1.4, Nov 2025) |
| TLSRoute | gateway.networking.k8s.io/v1 | Standard (GA since v1.5, Mar 2026) |
| TCPRoute | gateway.networking.k8s.io/v1alpha2 | Experimental |
| UDPRoute | gateway.networking.k8s.io/v1alpha2 | Experimental |
| BackendTLSPolicy | gateway.networking.k8s.io/v1 | Standard (GA since v1.4) |
| ReferenceGrant | gateway.networking.k8s.io/v1beta1 | Standard (frozen in beta) |

If a newer release promoted more resources, use the up-to-date apiVersion. Report the detected API status to the user in Phase 10.

## Phase 3 — Determine mode (add vs update)

If `--mode` is given, use it. Otherwise decide by template presence from Phase 1:

- **add** — no existing `templates/*route.yaml` files.
- **update** — at least one exists.

In **update-mode**, for each existing `*route.yaml`:

1. Render it with `helm template <chart-path>` using default values (and, if the route is gated by `enabled`, with `--set <route>.enabled=true` plus minimal required fields) to get the effective YAML.
2. Compare against the current-spec checklist:
   - apiVersion — is it still GA? E.g. GRPCRoute v1beta1 → should be v1.
   - does each `rules[]` entry have a `name` field? (v1.4+ best practice)
   - are CORS/auth/rate-limit headers implemented via ingress-style annotations rather than typed `filters`?
   - is there an HTTPS backend port (443, `appProtocol: https`, `name: https`) but no `BackendTLSPolicy`?
3. Build a list of discrepancies.

Show the discrepancy list to the user via AskUserQuestion (multiSelect, all pre-selected) and apply the selected ones.

Classify discrepancies into **safe** (applied silently in proactive runs) and **unsafe** (require interactive confirmation):

- safe: bump apiVersion for GA resources; add `name: default` to unnamed rules; add obvious helm-docs comment fixes.
- unsafe: migrate CORS from annotations to filters (changes the chart's public surface); add a new `BackendTLSPolicy` template (introduces a new resource with external dependencies like CA ConfigMaps); remove deprecated fields.

If the skill was invoked proactively (Claude's own decision, not the user's explicit command), only apply safe discrepancies. For unsafe ones, stop and report: "found unsafe migrations — run this skill interactively to review them".

In **add-mode**, skip the discrepancy analysis.

## Phase 4 — Determine route type(s) (add-mode only)

If `--type` is explicit, use it. Otherwise infer from Service ports captured in Phase 1:

| Service port signal | Suggested route type |
|---|---|
| `name: grpc`, `appProtocol: grpc`, `appProtocol: h2c` | GRPCRoute |
| `name: http` / `web` / `api`, protocol TCP, `appProtocol: http` | HTTPRoute |
| `name: https`, `appProtocol: tls` (SNI passthrough) | TLSRoute |
| `protocol: UDP` | UDPRoute |
| `protocol: TCP` without HTTP semantics (game server, TCP-only db) | TCPRoute |
| multiple mismatched ports | ask via AskUserQuestion (multiSelect) |

If TCPRoute or UDPRoute is selected, warn the user: those resources are still experimental (v1alpha2) and may see breaking changes in future Gateway API releases.

## Phase 5 — Choose values.yaml style (add-mode only)

Two valid styles:

**Flat** — use when adding exactly one route type and the chart has no existing `gateway:` block. Matches the jellyfin/longhorn PR style:

```yaml
httpRoute:
  enabled: false
  annotations: {}
  parentRefs: []
  hostnames: []
  rules:
    - name: default
      matches:
        - path:
            type: PathPrefix
            value: /
      # filters: []
      # timeouts: {}
      # backendRefs: []
```

**Nested** — use when adding multiple route types or the chart already has a `gateway:` block:

```yaml
gateway:
  enabled: false
  parentRefs: []
  httpRoute:
    enabled: true
    annotations: {}
    hostnames: []
    rules:
      - name: default
        matches:
          - path:
              type: PathPrefix
              value: /
  grpcRoute:
    enabled: false
    hostnames: []
    rules: []
```

`parentRefs` always defaults to `[]` — the cluster operator owns the Gateway resource; the chart should not assume its name.

## Phase 6 — Generate or patch template file(s)

### add-mode — create a new template per selected route type

All placeholders `<chart>` must be replaced with the real helper name captured in Phase 1.

Use the apiVersion table from Phase 2.

#### templates/httproute.yaml

```yaml
{{- if .Values.httpRoute.enabled -}}
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: {{ include "<chart>.fullname" . }}
  namespace: {{ .Release.Namespace }}
  labels:
    {{- include "<chart>.labels" . | nindent 4 }}
  {{- with .Values.httpRoute.annotations }}
  annotations:
    {{- toYaml . | nindent 4 }}
  {{- end }}
spec:
  parentRefs:
    {{- toYaml .Values.httpRoute.parentRefs | nindent 4 }}
  {{- with .Values.httpRoute.hostnames }}
  hostnames:
    {{- toYaml . | nindent 4 }}
  {{- end }}
  rules:
    {{- range .Values.httpRoute.rules }}
    -
      {{- with .name }}
      name: {{ . | quote }}
      {{- end }}
      matches:
        {{- toYaml .matches | nindent 8 }}
      {{- with .filters }}
      filters:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .timeouts }}
      timeouts:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      backendRefs:
        {{- if .backendRefs }}
        {{- toYaml .backendRefs | nindent 8 }}
        {{- else }}
        - name: {{ include "<chart>.fullname" $ }}
          port: {{ $.Values.service.port }}
        {{- end }}
    {{- end }}
{{- end }}
```

#### templates/grpcroute.yaml

Structurally identical to HTTPRoute. Differences: `kind: GRPCRoute`, default `matches` is `[{ method: { type: Exact, service: "", method: "" } }]` with empty values for the user to fill in. `filters` are still supported (v1 GA).

#### templates/tlsroute.yaml

No `filters`. `hostnames` are SNI names. Rules contain only `backendRefs`:

```yaml
{{- if .Values.tlsRoute.enabled -}}
apiVersion: gateway.networking.k8s.io/v1
kind: TLSRoute
metadata:
  name: {{ include "<chart>.fullname" . }}
  namespace: {{ .Release.Namespace }}
  labels:
    {{- include "<chart>.labels" . | nindent 4 }}
spec:
  parentRefs:
    {{- toYaml .Values.tlsRoute.parentRefs | nindent 4 }}
  {{- with .Values.tlsRoute.hostnames }}
  hostnames:
    {{- toYaml . | nindent 4 }}
  {{- end }}
  rules:
    {{- range .Values.tlsRoute.rules }}
    -
      {{- with .name }}
      name: {{ . | quote }}
      {{- end }}
      backendRefs:
        {{- if .backendRefs }}
        {{- toYaml .backendRefs | nindent 8 }}
        {{- else }}
        - name: {{ include "<chart>.fullname" $ }}
          port: {{ $.Values.service.port }}
        {{- end }}
    {{- end }}
{{- end }}
```

#### templates/tcproute.yaml and templates/udproute.yaml

Both use `apiVersion: gateway.networking.k8s.io/v1alpha2` (experimental — warn user). No `hostnames`, no `filters`. `parentRefs` should include `sectionName` to bind to a specific listener port on the Gateway. Structure mirrors TLSRoute minus hostnames.

#### templates/backendtlspolicy.yaml (optional)

Generate only when `--with-backend-tls` is set or a HTTPS-looking backend port is detected:

```yaml
{{- if .Values.backendTLSPolicy.enabled -}}
apiVersion: gateway.networking.k8s.io/v1
kind: BackendTLSPolicy
metadata:
  name: {{ include "<chart>.fullname" . }}
  namespace: {{ .Release.Namespace }}
spec:
  targetRefs:
    - group: ""
      kind: Service
      name: {{ include "<chart>.fullname" . }}
  validation:
    hostname: {{ .Values.backendTLSPolicy.hostname | quote }}
    {{- with .Values.backendTLSPolicy.caCertificateRefs }}
    caCertificateRefs:
      {{- toYaml . | nindent 6 }}
    {{- end }}
    {{- if .Values.backendTLSPolicy.wellKnownCACertificates }}
    wellKnownCACertificates: {{ .Values.backendTLSPolicy.wellKnownCACertificates | quote }}
    {{- end }}
{{- end }}
```

### update-mode — patch existing templates

Minimize the diff. Edit only the lines that correspond to discrepancies selected in Phase 3. Preserve the chart's original indentation, blank lines, and comments elsewhere. Use the `Edit` tool (not `Write`) to avoid reformatting the file.

## Phase 7 — Patch values.yaml

**add-mode:** insert the new values block (style chosen in Phase 5) after the `ingress:` block if it exists, otherwise after the `service:` block. Match the file's existing indent and comment style. If the file uses helm-docs `# --` annotations, add them to every new field.

Include commented-out examples for common patterns so users can uncomment rather than look them up:

```yaml
  # rules:
  #   - name: api
  #     matches:
  #       - path:
  #           type: PathPrefix
  #           value: /api
  #     filters:
  #       - type: CORS
  #         cors:
  #           allowOrigins: ["https://app.example.com"]
  #           allowMethods: [GET, POST]
  #     timeouts:
  #       request: 30s
  #       backendRequest: 10s
```

**update-mode:** insert new fields (e.g. `filters: []` when CORS migration is selected, `name: default` on existing unnamed rules) with minimum surrounding changes.

## Phase 8 — Optional helm-unittest test

Only if `tests/` exists in the chart (see Phase 1). Add or update `tests/<lowercase-kind>_test.yaml` following the jellyfin-helm#86 structure:

- Suite name: `<kind> template`
- Test cases:
  - `should not render when disabled` — assert `hitCount: 0`
  - `should render with minimal config` — set `enabled=true` plus `hostnames=[example.com]` and `parentRefs=[{name: gw}]`; assert kind, apiVersion, hostnames[0], parentRefs[0].name, and **rules[0].name** (named rule)
  - `should propagate annotations` (HTTPRoute/GRPCRoute only)
  - `should support multiple parentRefs with namespace+sectionName`
  - `should default backendRef to service.fullname:service.port`
  - `should support filters` (HTTPRoute only — e.g. CORS)
  - `should support timeouts` (HTTPRoute only)

In update-mode, update assertions to match the new structure (e.g. add `rules[0].name` assertion if named rules were introduced).

## Phase 9 — Verify rendering

Run locally from the chart's directory:

```bash
helm lint <chart-path>
helm template <chart-path>
```

The default render should NOT include any *Route resource (all `enabled: false`).

Then render with a route enabled:

```bash
helm template <chart-path> --set httpRoute.enabled=true \
  --set 'httpRoute.parentRefs[0].name=test' \
  --set 'httpRoute.hostnames[0]=test.example.com'
```

For nested style:

```bash
helm template <chart-path> --set gateway.enabled=true \
  --set gateway.httpRoute.enabled=true \
  --set 'gateway.parentRefs[0].name=test' \
  --set 'gateway.httpRoute.hostnames[0]=test.example.com'
```

If helm-unittest is installed and tests were added or updated:

```bash
helm unittest <chart-path>
```

Finally, show `git --no-pager diff -- <chart-path>` read-only for the user to inspect.

## Phase 10 — Report

Produce a summary:

1. **Mode** — add or update.
2. **Detected API status** — the apiVersion table from Phase 2, highlighting any change vs training-data expectations.
3. **Files created / modified** — absolute paths.
4. **Applied changes** — list of what was added/patched (e.g. "added name: default to rules[0]", "migrated CORS annotation to filter").
5. **Suggested commit message** (English, semantic commit):
   - add-mode: `feat(<chart>): add HTTPRoute template for Gateway API support`
   - update-mode: `chore(<chart>): modernize HTTPRoute template to Gateway API v1.5 spec`
6. **Suggested PR title and draft body** (English). The body should state: mode (add/update), affected route types, API channel (Standard GA vs Experimental), and Gateway API minimum version required (≥ v1.4 for named rules, ≥ v1.5 for CORS filter GA).
7. **Reminder** — git operations (branch, commit, push, PR) are the caller's responsibility. The skill did not run any.

## Guardrails

- **No git operations.** The skill never runs `git checkout`, `git commit`, `git push`, `gh pr create`, or any write-changing git command. Read-only `git diff` is allowed to show the user what changed.
- **No Gateway resource inside the chart.** Only *Route and optional BackendTLSPolicy. The cluster operator owns the Gateway — an embedded Gateway makes the chart non-portable.
- **All routes default to `enabled: false`** in add-mode so upgrading an existing release does not silently create new traffic. In update-mode, preserve the existing `enabled` value.
- **Match the chart's existing style.** Indent, naming conventions, helm-docs `# --` annotations — mirror the `ingress:` block. Never impose a foreign style.
- **Minimize diff in update-mode.** Use `Edit` tool with narrow replacements; preserve blank lines, comments, and field ordering outside the touched region.
- **Use the chart's real `_helpers.tpl` names.** Do not assume `<chart>.fullname`; read the file and substitute the actual helper name.
- **Long flags only** in any helm/git/gh command shown to the user — `--values`, `--set`, `--namespace`, `--filename`. Never `-f`, `-n`, `-v`.
- **Verify API versions via WebFetch every run** (Phase 2). Do not rely on baked-in assumptions — the spec moves quickly.
- **Public-facing text in English.** Suggested commit messages, PR titles, and PR bodies never use Russian.
- **Bail cleanly** if add-mode would overwrite an existing `templates/<kind>.yaml`. Switch to update-mode automatically, or if nothing to modernize, report "nothing to do".
- **Warn about Experimental resources** (TCPRoute, UDPRoute). The user must acknowledge before generating them.
- **Proactive runs apply safe changes only.** If the skill was invoked by Claude's own decision (not an explicit user request), only perform safe updates; for unsafe ones, stop and ask the user to run interactively.
