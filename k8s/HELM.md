# Helm Chart Documentation

## Task 1 — Helm Setup

### Installation & Version

```
$ helm version
version.BuildInfo{Version:"v4.1.3", GitCommit:"c94d381b03be117e7e57908edbf642104e00eb8f", GitTreeState:"clean", GoVersion:"go1.26.1", KubeClientVersion:"v1.35"}
```

### Repository Exploration

```bash
$ helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
"prometheus-community" has been added to your repositories

$ helm repo update
Hang tight while we grab the latest from your chart repositories...
...Successfully got an update from the "prometheus-community" chart repository
Update Complete. Happy Helming!

$ helm show chart prometheus-community/prometheus
annotations:
  artifacthub.io/license: Apache-2.0
  ...
apiVersion: v2
appVersion: v3.10.0
dependencies:
- condition: alertmanager.enabled
  name: alertmanager
  repository: https://prometheus-community.github.io/helm-charts
  version: 1.34.*
- condition: kube-state-metrics.enabled
  name: kube-state-metrics
  repository: https://prometheus-community.github.io/helm-charts
  version: 7.2.*
- condition: prometheus-node-exporter.enabled
  name: prometheus-node-exporter
  repository: https://prometheus-community.github.io/helm-charts
  version: 4.52.*
description: Prometheus is a monitoring system and time series database.
home: https://prometheus.io/
keywords:
- monitoring
- prometheus
kubeVersion: '>=1.19.0-0'
name: prometheus
type: application
version: 28.14.1
```

### Helm Value Proposition

Helm is the de-facto package manager for Kubernetes. It solves three key problems:

1. **Templating** — instead of copy-pasting YAML for dev/staging/prod, you write it once with Go template variables and override only what differs per environment
2. **Release lifecycle** — `helm install`, `upgrade`, `rollback`, `uninstall` give you versioned, atomic deployments with a full audit history
3. **Dependencies** — complex applications (e.g. Prometheus with Alertmanager, node-exporter, kube-state-metrics) are packaged as a single chart with declared sub-chart dependencies

Helm 4 (current) removes Tiller, adds full OCI registry support, and improves security over Helm 2.

---

## Chart Overview

### Structure

```
k8s/
├── devops-info-service/          # Main application chart
│   ├── Chart.yaml                # Chart metadata (name, version, appVersion)
│   ├── values.yaml               # Default configuration values
│   ├── values-dev.yaml           # Development environment overrides
│   ├── values-prod.yaml          # Production environment overrides
│   └── templates/
│       ├── _helpers.tpl          # Reusable named templates (fullname, labels, etc.)
│       ├── deployment.yaml       # Kubernetes Deployment resource
│       ├── service.yaml          # Kubernetes Service resource
│       ├── NOTES.txt             # Post-install instructions
│       └── hooks/
│           ├── pre-install-job.yaml   # Pre-install hook Job
│           └── post-install-job.yaml  # Post-install hook Job
├── common-lib/                   # Library chart (shared templates — bonus)
│   ├── Chart.yaml                # type: library
│   └── templates/
│       └── _common.tpl           # Shared helpers: fullname, labels, selectorLabels
└── app2/                         # Second app using common-lib (bonus)
    ├── Chart.yaml                # Declares common-lib as dependency
    ├── values.yaml
    ├── charts/                   # Packaged common-lib dependency
    └── templates/
        ├── deployment.yaml
        ├── service.yaml
        └── NOTES.txt
```

### Key Template Files

| File | Purpose |
|------|---------|
| `_helpers.tpl` | Defines reusable templates: `fullname`, `name`, `labels`, `selectorLabels`, `chart` |
| `deployment.yaml` | Deployment with templated replicas, image, resources, probes, env vars |
| `service.yaml` | Service with conditional `nodePort` field |
| `hooks/pre-install-job.yaml` | Job annotated `helm.sh/hook: pre-install`, weight `-5` |
| `hooks/post-install-job.yaml` | Job annotated `helm.sh/hook: post-install`, weight `5` |

### Values Organization

Values are organized into logical groups:

- `replicaCount` — number of pod replicas
- `image.*` — container image repository, tag, pull policy
- `env` — environment variables passed to the container
- `service.*` — type (NodePort/LoadBalancer/ClusterIP), ports
- `resources.*` — CPU/memory limits and requests
- `livenessProbe` / `readinessProbe` — health check configuration
- `strategy.*` — rolling update parameters

---

## Configuration Guide

### Important Values

| Value | Default | Description |
|-------|---------|-------------|
| `replicaCount` | `3` | Number of pod replicas |
| `image.repository` | `mituta/devops-info-service` | Container image repository |
| `image.tag` | `lab02` | Image tag |
| `image.pullPolicy` | `IfNotPresent` | Image pull policy |
| `service.type` | `NodePort` | Service type |
| `service.port` | `80` | Service port |
| `service.targetPort` | `5000` | Container port |
| `service.nodePort` | `30080` | NodePort (only for NodePort type) |
| `resources.limits.cpu` | `200m` | CPU limit |
| `resources.limits.memory` | `256Mi` | Memory limit |
| `livenessProbe.initialDelaySeconds` | `15` | Liveness probe delay |
| `readinessProbe.initialDelaySeconds` | `5` | Readiness probe delay |

### Environment-Specific Configurations

**Development (`values-dev.yaml`):**
- 1 replica (single pod, fast startup)
- NodePort service on port 30080 (direct external access)
- Reduced resources (50m/64Mi requests)
- Short probe delays (initialDelaySeconds: 5)
- `APP_RELEASE: dev`

**Production (`values-prod.yaml`):**
- 3 replicas (HA)
- LoadBalancer service type
- Full resources (200m/256Mi requests, 500m/512Mi limits)
- Conservative probe delays (initialDelaySeconds: 30 liveness, 10 readiness)
- `APP_RELEASE: v1`

### Example Installations

```bash
# Development
helm install myapp-dev k8s/devops-info-service -f k8s/devops-info-service/values-dev.yaml

# Production
helm install myapp-prod k8s/devops-info-service -f k8s/devops-info-service/values-prod.yaml

# Override a specific value
helm install myapp k8s/devops-info-service --set replicaCount=5

# Upgrade to prod
helm upgrade myapp-dev k8s/devops-info-service -f k8s/devops-info-service/values-prod.yaml
```

---

## Hook Implementation

### Hooks Overview

| Hook | Type | Weight | Deletion Policy | Purpose |
|------|------|--------|-----------------|---------|
| `pre-install-job` | `pre-install` | `-5` | `hook-succeeded` | Validates environment readiness before app installs |
| `post-install-job` | `post-install` | `5` | `hook-succeeded` | Smoke test after installation completes |

### Execution Order

1. **Pre-install hook** runs first (weight `-5` is lower → runs before other pre-install hooks at weight 0)
2. Main Kubernetes resources are created (Deployment, Service)
3. **Post-install hook** runs last (weight `5`)

### Deletion Policy

Both hooks use `hook-succeeded`: Kubernetes Jobs are automatically deleted after successful completion. This keeps the cluster clean and avoids stale job resources.

### Hook Annotations

```yaml
annotations:
  "helm.sh/hook": pre-install       # or post-install
  "helm.sh/hook-weight": "-5"       # execution priority
  "helm.sh/hook-delete-policy": hook-succeeded
```

---

## Installation Evidence

### `helm list` Output

```
NAME          NAMESPACE  REVISION  UPDATED                              STATUS    CHART                     APP VERSION
app2-release  default    1         2026-03-31 14:57:45 +0300            deployed  app2-0.1.0                lab02
myrelease-dev default    3         2026-03-31 15:18:09 +0300            deployed  devops-info-service-0.1.0 lab02
```

### `kubectl get all` — Both Releases Running

```
NAME                                                    READY   STATUS    RESTARTS   AGE
pod/app2-release-app2-5cc7bf6668-ldl7k                  1/1     Running   0          20m
pod/app2-release-app2-5cc7bf6668-ncx4d                  1/1     Running   0          20m
pod/myrelease-dev-devops-info-service-9c9cd9bd7-8djtn   1/1     Running   0          18m

NAME                                        TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)        AGE
service/app2-release-app2                   ClusterIP   10.104.237.160   <none>        80/TCP         20m
service/kubernetes                          ClusterIP   10.96.0.1        <none>        443/TCP        5d18h
service/myrelease-dev-devops-info-service   NodePort    10.110.101.232   <none>        80:30080/TCP   18m

NAME                                                READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/app2-release-app2                   2/2     2            2           20m
deployment.apps/myrelease-dev-devops-info-service   1/1     1            1           18m
```

### Hook Execution

Hooks ran during `helm install myrelease-dev` and were deleted automatically after success (`hook-delete-policy: hook-succeeded`). The release installed with STATUS: deployed, confirming both pre-install and post-install jobs completed.

```bash
kubectl get jobs
# No resources found in default namespace.
```

### Upgrade (Dev → Prod) and Rollback Evidence

```bash
$ helm upgrade myrelease-dev k8s/devops-info-service -f k8s/devops-info-service/values-prod.yaml
Release "myrelease-dev" has been upgraded. Happy Helming!
STATUS: deployed  REVISION: 2

$ helm rollback myrelease-dev 1
Rollback was a success! Happy Helming!

$ helm history myrelease-dev
REVISION  UPDATED                  STATUS      CHART                     APP VERSION  DESCRIPTION
1         Tue Mar 31 14:59:53 2026 superseded  devops-info-service-0.1.0 lab02        Install complete
2         Tue Mar 31 15:17:49 2026 superseded  devops-info-service-0.1.0 lab02        Upgrade complete
3         Tue Mar 31 15:18:09 2026 deployed    devops-info-service-0.1.0 lab02        Rollback to 1
```

### Application Health Check

```
$ kubectl run test-curl --image=curlimages/curl --rm -it --restart=Never \
    -- curl -s http://10.110.101.232/health

{"status":"healthy","timestamp":"2026-03-31T11:58:56.860828Z","uptime_seconds":90}
```

---

## Operations

### Installation

```bash
# Install with dev values
helm install myrelease-dev k8s/devops-info-service -f k8s/devops-info-service/values-dev.yaml

# Install with prod values
helm install myrelease-prod k8s/devops-info-service -f k8s/devops-info-service/values-prod.yaml

# Install app2 (with common-lib dependency — run dependency update first)
helm dependency update k8s/app2
helm install app2-release k8s/app2
```

### Upgrade

```bash
helm upgrade myrelease-dev k8s/devops-info-service -f k8s/devops-info-service/values-prod.yaml
```

### Rollback

```bash
# Roll back to specific revision
helm rollback myrelease-dev 1

# Roll back to previous revision
helm rollback myrelease-dev

# Check history
helm history myrelease-dev
# REVISION  STATUS      DESCRIPTION
# 1         superseded  Install complete
# 2         superseded  Upgrade complete
# 3         deployed    Rollback to 1
```

### Uninstall

```bash
helm uninstall myrelease-dev
helm uninstall app2-release
```

---

## Testing & Validation

### `helm lint` Output

```
==> Linting k8s/devops-info-service
[INFO] Chart.yaml: icon is recommended
1 chart(s) linted, 0 chart(s) failed

==> Linting k8s/app2
[INFO] Chart.yaml: icon is recommended
1 chart(s) linted, 0 chart(s) failed
```

### `helm template` Verification

```bash
helm template myrelease k8s/devops-info-service
helm template myrelease-dev k8s/devops-info-service -f k8s/devops-info-service/values-dev.yaml
```

Both produce valid Kubernetes manifests with correct labels, selectors, probes, and hook annotations.

### Dry-run Output (hooks visible)

```bash
helm install --dry-run --debug test-release k8s/devops-info-service | grep -A 5 "hook"
# Shows: pre-install-job with helm.sh/hook: pre-install, weight -5
#        post-install-job with helm.sh/hook: post-install, weight 5
```

### Application Accessibility

```bash
kubectl run test-curl --image=curlimages/curl --rm -it --restart=Never \
  -- curl -s http://$(kubectl get svc myrelease-dev-devops-info-service \
  -o jsonpath='{.spec.clusterIP}')/health
# {"status":"healthy","timestamp":"...","uptime_seconds":90}
```

---

## Bonus — Library Charts

### Why Library Charts

The `common-lib` library chart extracts shared helper templates (`fullname`, `labels`, `selectorLabels`, `chart`) used by both `devops-info-service` and `app2`. This follows the DRY principle — naming logic and label standards are defined once and reused.

**Benefits:**
- Single source of truth for label standards
- Consistent Kubernetes resource naming across apps
- Easier to update: change template in one place, all consumers pick it up
- Charts stay focused on their own application logic

### Library Chart Structure

```
common-lib/
├── Chart.yaml        # type: library (cannot be installed directly)
└── templates/
    └── _common.tpl   # Defines: common.name, common.fullname, common.chart,
                      #          common.labels, common.selectorLabels
```

### Using the Library

Both `devops-info-service` and `app2` declare `common-lib` as a dependency in their `Chart.yaml`:

```yaml
dependencies:
  - name: common-lib
    version: 0.1.0
    repository: "file://../common-lib"
```

Each chart has `charts/common-lib-0.1.0.tgz` and a `Chart.lock` after running `helm dependency update`.

**`devops-info-service/templates/_helpers.tpl`** delegates all template logic to the library:

```yaml
{{- define "devops-info-service.fullname" -}}
{{- include "common.fullname" . }}
{{- end }}

{{- define "devops-info-service.labels" -}}
{{- include "common.labels" . }}
{{- end }}
```

**`app2/templates/deployment.yaml`** calls library templates directly:

```yaml
name: {{ include "common.fullname" . }}
labels:
  {{- include "common.labels" . | nindent 4 }}
```

```bash
# Install dependencies and deploy both charts
helm dependency update k8s/devops-info-service
helm dependency update k8s/app2
helm install myrelease-dev k8s/devops-info-service -f k8s/devops-info-service/values-dev.yaml
helm install app2-release k8s/app2
```

Both apps deploy successfully with identical label structure generated from the shared `common-lib` library.
