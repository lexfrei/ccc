---
name: helm-add-gwapi-route
description: Add or modernize Gateway API *Route templates (HTTPRoute/GRPCRoute/TLSRoute/TCPRoute/UDPRoute) in a Helm chart. Auto-detects add vs update mode, mirrors the chart's ingress/values conventions, applies current best practices (named rules, typed filters, optional BackendTLSPolicy). Pure file edits — no git, no PR. Trigger proactively on Helm charts with ingress but no routes, or outdated routes needing modernization. See "When to invoke" below for full triggers.
argument-hint: "[chart-path] [--type=httproute|grpcroute|tlsroute|tcproute|udproute|auto] [--mode=add|update|auto] [--with-backend-tls]"
---

# helm-add-gwapi-route

Add or modernize Gateway API *Route resources inside a Helm chart. The skill only edits files — git operations (branch, commit, push, PR) are left to the caller.

## When to invoke

Invoke proactively (without an explicit user command) when any of these hold:

- cwd is a Helm chart (Chart.yaml with `apiVersion: v2`) that has `templates/ingress.yaml` but no `templates/*route.yaml` — candidate for add-mode.
- cwd has `templates/httproute.yaml` / `grpcroute.yaml` / `tlsroute.yaml` declaring `gateway.networking.k8s.io/v1beta1` or `v1alpha2` for resources that are now GA at `v1` — candidate for update-mode.
- cwd has `*Route` templates whose rules lack the `name` field (named rules are best practice since Gateway API v1.4).
- The user mentions migrating a chart from Ingress to Gateway API, adding HTTPRoute/GRPCRoute/TLSRoute support, "gwapi", or modernizing existing routes.

Do not invoke when:

- The chart already has current-spec routes with nothing to modernize.
- cwd is not a Helm chart (no `Chart.yaml` with `apiVersion: v2`).
- The scope is a standalone Kubernetes manifest, not a Helm chart.
- The user is working on an unrelated task — do not interrupt.

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

Training data is frequently outdated on API maturity. Before generating any template, fetch fresh data via WebFetch — do not rely on memory or prior conversation.

Fetch:

- <https://gateway-api.sigs.k8s.io/concepts/versioning/> — canonical maturity table.
- <https://kubernetes.io/blog/> — search for the latest Gateway API release post.

Build a fresh status table covering every resource this skill generates: HTTPRoute, GRPCRoute, TLSRoute, TCPRoute, UDPRoute, BackendTLSPolicy, ReferenceGrant. Record the current apiVersion and channel (Standard / Experimental) for each.

Carry that table into Phase 10 (Report). Every run must include a line like:

```text
Verified via WebFetch at <ISO8601 timestamp>: HTTPRoute=v1 (Standard), GRPCRoute=v1 (Standard), ...
```

This forces the model to actually perform the fetch rather than reuse cached claims.

**Minimum cluster Gateway API version required per route kind** — this is a separate question from current apiVersion and changes much less often. As a reference (still verify via the versioning page in case of controller-specific caveats; dates are omitted because they date-drift and the version number alone is enough to gate on):

| Route kind / feature | Min Gateway API version |
| --- | --- |
| HTTPRoute | v1.0 |
| GRPCRoute | v1.1 |
| HTTPRoute timeouts | v1.2 |
| BackendTLSPolicy | v1.4 |
| Named rules on HTTPRoute/GRPCRoute | v1.4 |
| CORS filter in Standard channel | v1.5 |
| TLSRoute | v1.5 |
| TCPRoute / UDPRoute | Experimental (no GA yet) |

Surface the relevant minimum version(s) in Phase 10's PR body so users can gate on controller support.

## Phase 3 — Determine mode (add vs update)

If `--mode` is given, use it and apply it to every selected route kind uniformly.

Otherwise, `--mode=auto` is resolved **per route kind**, not per chart:

- For each route kind selected in Phase 4, check whether the corresponding `templates/<kind>.yaml` exists.
- If it does not exist → that kind is in **add-mode**.
- If it exists → that kind is in **update-mode**.

This handles the common mixed case where a chart already has `httproute.yaml` and the user wants to add a brand-new `grpcroute.yaml` at the same time: HTTPRoute gets update-mode review, GRPCRoute gets add-mode generation.

In the rest of this document, references to "add-mode" and "update-mode" are per-kind decisions.

In **update-mode**, for each existing `*route.yaml`:

1. Render it with `helm template <chart-path>` using default values (and, if the route is gated by `enabled`, with `--set <route>.enabled=true` plus minimal required fields) to get the effective YAML.
2. Compare against the current-spec checklist:
   - apiVersion — per-kind judgement, not a blanket rule:
     - HTTPRoute `v1beta1` still coexists with `v1` in the Standard channel (v1beta1 was not removed at v1 GA). Bumping it silently breaks compatibility with controllers that only serve v1beta1. **Do not auto-bump HTTPRoute v1beta1 → v1; ask the user.**
     - GRPCRoute `v1alpha2` / `v1beta1` → `v1` is a safe bump where v1 is available (graduated v1.1). Treat as safe.
     - TLSRoute `v1alpha2` → `v1` is a safe bump where v1 is available (graduated v1.5). Treat as safe.
     - TCPRoute / UDPRoute — still `v1alpha2`; no bump to propose.
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
| --- | --- |
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
  # REQUIRED when enabled: the Gateway(s) this route attaches to. Empty list = no attachment = no traffic.
  parentRefs: []
  #   - name: my-gateway
  #     namespace: gateway-system
  #     sectionName: https   # optional, binds to a specific listener on the Gateway
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
  # REQUIRED when any nested route is enabled: the Gateway(s) the routes attach to.
  parentRefs: []
  #   - name: my-gateway
  #     namespace: gateway-system
  #     sectionName: https
  httpRoute:
    enabled: false
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
    rules:
      - name: default
```

`parentRefs` always defaults to `[]` — the cluster operator owns the Gateway resource; the chart should not assume its name. A route with empty `parentRefs` never attaches to a Gateway and receives no traffic; flag this explicitly in both the values.yaml comment above the field and in NOTES.txt (Phase 7) so users know to fill it in before enabling the route.

**TLSRoute / TCPRoute / UDPRoute parentRefs need `sectionName`.** These route kinds bind to a specific listener on the Gateway (by port and protocol), not to the Gateway as a whole. When generating a values example for any of these, include `sectionName` in the commented parentRefs example so users understand:

```yaml
  # parentRefs:
  #   - name: my-gateway
  #     namespace: gateway-system
  #     sectionName: tls-passthrough   # must match a listener defined on the Gateway
```

## Phase 6 — Generate or patch template file(s)

### add-mode — create a new template per selected route type

All placeholders `<chart>` must be replaced with the real helper name captured in Phase 1.

Use the apiVersion table built in Phase 2 — do not hardcode versions from this document.

**Backend port resolution.** The default `backendRefs` entry points to the chart's own Service. Two common conventions in `values.yaml`:

- Scalar: `.Values.service.port` — single main port.
- List: `.Values.service.ports` — list of `{name, port, protocol}` objects (common in charts with multiple Service ports).

In Phase 1 you captured which convention the chart uses. Emit the correct reference in the template:

- For scalar: `port: {{ $.Values.service.port }}`
- For list: `port: {{ (index $.Values.service.ports 0).port }}` (or a specific named port if the chart has multiple and only one matches the route's protocol — e.g. the port with `name: http` for HTTPRoute)

If the chart uses a non-standard structure (e.g. `.Values.server.port`, `.Values.http.port`), substitute it into the template rather than forcing `.Values.service.port`.

#### templates/httproute.yaml

```yaml
{{- if .Values.httpRoute.enabled -}}
{{- if not .Values.httpRoute.parentRefs -}}
{{- fail "httpRoute.enabled=true but httpRoute.parentRefs is empty. A route without parentRefs cannot attach to a Gateway. Set httpRoute.parentRefs to the Gateway(s) managed by your cluster operator." -}}
{{- end -}}
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
      {{- with .matches }}
      matches:
        {{- toYaml . | nindent 8 }}
      {{- end }}
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

Matches is wrapped in `{{- with .matches }}` because HTTPRoute (and GRPCRoute) treat a missing `matches` field as "match all" — valid and sometimes intended. Rendering `matches: null` from `toYaml nil` would be rejected by CRD validators. The same `{{- with }}` guard applies to the GRPCRoute template.

The same `{{- if not .Values.<route>.parentRefs -}}{{- fail ... -}}{{- end -}}` guard applies to every route template (GRPCRoute, TLSRoute, TCPRoute, UDPRoute): a route with empty parentRefs cannot attach to a Gateway and produces an invalid manifest rejected by kube-apiserver. Fail fast at template time so `helm install` never creates a broken route.

#### templates/grpcroute.yaml

Structurally identical to HTTPRoute. Differences:

- `kind: GRPCRoute`
- `filters` are still supported (v1 GA).
- **No default `matches`.** GRPCRoute treats a missing `matches` field as "match all", just like HTTPRoute. Do not emit a default matcher with empty strings (`service: "", method: ""`) — GRPCRoute's CRD schema requires non-empty values for `type: Exact` matchers, so the default would fail server-side validation. Let users omit `matches` for match-all, or populate real service/method strings when they need scoping.

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

Generate only when `--with-backend-tls` is set or a HTTPS-looking backend port is detected.

**Note:** `caCertificateRefs` and `wellKnownCACertificates` are mutually exclusive per the BackendTLSPolicy spec. Use `if/else if` so only one renders even if both are set in values — the `else if` branch is only selected when `caCertificateRefs` is empty.

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
    {{- if .Values.backendTLSPolicy.caCertificateRefs }}
    caCertificateRefs:
      {{- toYaml .Values.backendTLSPolicy.caCertificateRefs | nindent 6 }}
    {{- else if .Values.backendTLSPolicy.wellKnownCACertificates }}
    wellKnownCACertificates: {{ .Values.backendTLSPolicy.wellKnownCACertificates | quote }}
    {{- end }}
{{- end }}
```

### update-mode — patch existing templates

Minimize the diff. Edit only the lines that correspond to discrepancies selected in Phase 3. Preserve the chart's original indentation, blank lines, and comments elsewhere. Use the `Edit` tool (not `Write`) to avoid reformatting the file.

## Phase 7 — Patch values.yaml

**add-mode:** insert the new values block (style chosen in Phase 5) after the `ingress:` block if it exists, otherwise after the `service:` block. Match the file's existing indent and comment style. If the file uses helm-docs `# --` annotations, add them to every new field.

Include commented-out examples for common patterns so users can uncomment rather than look them up. Annotate features with their minimum Gateway API version so users can gate on controller support:

```yaml
  # rules:
  #   - name: api
  #     matches:
  #       - path:
  #           type: PathPrefix
  #           value: /api
  #     filters:
  #       # CORS filter is Standard-channel since Gateway API v1.5.
  #       # On older clusters it is Experimental and may not be supported.
  #       - type: CORS
  #         cors:
  #           allowOrigins: ["https://app.example.com"]
  #           allowMethods: [GET, POST]
  #       - type: RequestHeaderModifier
  #         requestHeaderModifier:
  #           set:
  #             - name: X-Forwarded-Prefix
  #               value: /api
  #     timeouts:
  #       # HTTPRoute timeouts are Standard-channel since Gateway API v1.2.
  #       request: 30s
  #       backendRequest: 10s
```

**update-mode:** insert new fields (e.g. `filters: []` when CORS migration is selected, `name: default` on existing unnamed rules) with minimum surrounding changes.

### BackendTLSPolicy values block

When `--with-backend-tls` is set (or an HTTPS backend port was detected and the user confirmed), also add the corresponding values block near the route block:

```yaml
backendTLSPolicy:
  enabled: false
  # Expected SNI hostname the backend Service presents on its TLS certificate.
  hostname: ""
  # Set ONE of the two fields below — the spec requires them to be mutually exclusive.
  # caCertificateRefs: References to ConfigMaps holding PEM CA bundles.
  caCertificateRefs: []
  #   - group: ""
  #     kind: ConfigMap
  #     name: backend-ca
  # wellKnownCACertificates: "System" to trust the controller's system CA roots.
  wellKnownCACertificates: ""
```

Place the `backendTLSPolicy:` block adjacent to the route block for discoverability.

### NOTES.txt

If the chart has `templates/NOTES.txt`, append a block describing how to inspect the newly added route(s) post-install. Example:

```text
{{- if .Values.httpRoute.enabled }}
HTTPRoute '{{ include "<chart>.fullname" . }}' was created.
{{- if not .Values.httpRoute.parentRefs }}

WARNING: httpRoute.parentRefs is empty. The route will not attach to any Gateway
and no traffic will reach the Service. Edit values.yaml to set parentRefs to the
Gateway managed by your cluster operator, then run `helm upgrade`.
{{- end }}
Verify it is accepted by the parent Gateway:
    kubectl --namespace {{ .Release.Namespace }} get httproute {{ include "<chart>.fullname" . }} --output yaml
    kubectl --namespace {{ .Release.Namespace }} describe httproute {{ include "<chart>.fullname" . }}

Check that the parentRefs resolve and the route is attached:
    kubectl --namespace {{ .Release.Namespace }} get httproute {{ include "<chart>.fullname" . }} --output jsonpath='{.status.parents[*].conditions[?(@.type=="Accepted")].status}'
{{- end }}
```

Adapt the kind name (HTTPRoute → GRPCRoute / TLSRoute / TCPRoute / UDPRoute) for each generated route type. Preserve the trailing newline of the existing NOTES.txt when appending. If NOTES.txt does not exist and the chart has no other notes, skip this step — do not create a new NOTES.txt just for the route.

## Phase 8 — Optional helm-unittest test

Only if `tests/` exists in the chart (see Phase 1). Add or update `tests/<lowercase-kind>_test.yaml` following the jellyfin-helm#86 structure:

- Suite name: `<kind> template`
- Test cases:
  - `should not render when disabled` — assert `hitCount: 0`
  - `should render with minimal config` — set `enabled=true` plus `hostnames=[example.com]` and `parentRefs=[{name: gw}]`; assert kind, apiVersion, hostnames[0], parentRefs[0].name, and **rules[0].name** (named rule)
  - `should propagate annotations` (HTTPRoute/GRPCRoute only)
  - `should support multiple parentRefs with namespace+sectionName`
  - `should default backendRef to service.fullname:service.port` (use the backend-port pattern chosen in Phase 6 — scalar or list index)
  - `should support filters` (HTTPRoute only — e.g. CORS)
  - `should support timeouts` (HTTPRoute only)

### update-mode adjustments

If `tests/<lowercase-kind>_test.yaml` already exists:

1. Parse the existing file. Keep its `suite` name, `templates:` list, and `values:` fixture paths as-is.
2. Preserve existing test case names and `set:` blocks. Only add new assertions (e.g. `rules[0].name` if named rules were added in Phase 6) — do not rewrite test bodies.
3. Add brand-new test cases only for new behavior (e.g. new CORS filter test). Do not duplicate existing ones.
4. If the existing file uses a values fixture (e.g. `set:` with a large object), do not inline it — keep the reference intact.
5. Run `helm unittest <chart-path>` at the end of Phase 8 to confirm the whole suite still passes.

## Phase 9 — Verify rendering

Run locally from the chart's directory:

```bash
helm lint --strict <chart-path>
helm template <chart-path>
```

Use `--strict` — it turns lint warnings (deprecation messages, missing `icon` in Chart.yaml, templating warnings) into failures so they don't get ignored. If the chart has a `values.schema.json`, schema validation against defaults happens regardless of `--strict`.

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

### Server-side validation (optional but recommended)

`helm template` + `helm lint` do not validate generated YAML against CRD schemas — they only catch Go template syntax errors. To catch schema violations (wrong field names, invalid enums, missing required fields) before the manifests are applied for real, run a server-side dry-run against a cluster that already has Gateway API CRDs installed:

```bash
helm template <chart-path> --set httpRoute.enabled=true \
    --set 'httpRoute.parentRefs[0].name=test' \
    --set 'httpRoute.hostnames[0]=test.example.com' \
  | kubectl --context <ctx> apply --filename - --dry-run=server
```

Skip this step if the user has no cluster access in the current session.

### helm-unittest

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
5. **Suggested commit message** (English, semantic commit). Include the full message body and the `Assisted-By` trailer required by repo/global CLAUDE.md:
   - add-mode subject: `feat(<chart>): add HTTPRoute template for Gateway API support`
   - update-mode subject: `chore(<chart>): modernize HTTPRoute template to current Gateway API spec`
   - body: one sentence per change (what and why), then a blank line, then:

     ```text
     Assisted-By: Claude <noreply@anthropic.com>
     ```

6. **Suggested PR title and draft body** (English). The body should state: mode (add/update), affected route types, API channel (Standard GA vs Experimental), and Gateway API minimum version required per kind (look up each touched kind in the Phase 2 min-version table — do not state a single universal floor).
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
