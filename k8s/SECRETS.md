# Lab 11 — Kubernetes Secrets & HashiCorp Vault

## Table of Contents

- [Kubernetes Secrets](#kubernetes-secrets)
- [Helm Secret Integration](#helm-secret-integration)
- [Resource Management](#resource-management)
- [Vault Integration](#vault-integration)
- [Security Analysis](#security-analysis)
- [Bonus: Vault Agent Templates](#bonus-vault-agent-templates)

---

## Kubernetes Secrets

### Creating a Secret

```bash
kubectl create secret generic app-credentials \
  --from-literal=username=admin \
  --from-literal=password=S3cur3P@ss
```

Output:

```
secret/app-credentials created
```

### Viewing the Secret

```bash
kubectl get secret app-credentials -o yaml
```

Output:

```yaml
apiVersion: v1
data:
  password: UzNjdXIzUEBzcw==
  username: YWRtaW4=
kind: Secret
metadata:
  creationTimestamp: "2026-04-06T21:24:14Z"
  name: app-credentials
  namespace: default
  resourceVersion: "217187"
  uid: 1b189145-4e87-434c-b102-c0d5da00babc
type: Opaque
```

### Decoding Base64 Values

```bash
echo "YWRtaW4=" | base64 -d
# admin

echo "UzNjdXIzUEBzcw==" | base64 -d
# S3cur3P@ss
```

### Base64 Encoding vs Encryption

| Aspect | Base64 Encoding | Encryption |
|--------|----------------|------------|
| Purpose | Data representation format | Data protection |
| Reversibility | Anyone can decode instantly | Requires a key to decrypt |
| Security | Provides zero security | Provides confidentiality |
| Use in K8s | Default for Secrets storage | Requires enabling etcd encryption |

Base64 is **not** a security mechanism — it is a binary-to-text encoding scheme. Kubernetes uses it only so that binary data can be stored in YAML/JSON. Anyone with `kubectl get secret` access can decode the values trivially.

### Are Kubernetes Secrets Encrypted at Rest?

**No**, Kubernetes Secrets are **not** encrypted at rest by default. They are stored as base64-encoded plaintext in etcd.

To enable encryption at rest:

1. Create an `EncryptionConfiguration` resource specifying a provider (e.g., `aescbc`, `secretbox`, or a KMS plugin)
2. Pass `--encryption-provider-config` flag to the kube-apiserver
3. Re-encrypt existing secrets with `kubectl get secrets --all-namespaces -o json | kubectl replace -f -`

You should enable etcd encryption when:

- Running in production environments
- Storing sensitive credentials (DB passwords, API keys, TLS certs)
- Compliance requirements mandate data-at-rest encryption (SOC2, HIPAA, PCI-DSS)

---

## Helm Secret Integration

### Chart Structure

```
devops-info-service/
├── Chart.yaml
├── values.yaml
├── templates/
│   ├── _helpers.tpl
│   ├── deployment.yaml
│   ├── secrets.yaml        ← new
│   ├── service.yaml
│   └── serviceaccount.yaml ← new
└── ...
```

### Secret Template (`templates/secrets.yaml`)

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: {{ include "devops-info-service.fullname" . }}-secret
  labels:
    {{- include "devops-info-service.labels" . | nindent 4 }}
type: Opaque
stringData:
  {{- range $key, $value := .Values.secrets }}
  {{ $key }}: {{ $value | quote }}
  {{- end }}
```

### Secret Values in `values.yaml`

```yaml
secrets:
  DATABASE_USERNAME: "admin"
  DATABASE_PASSWORD: "changeme"
```

These are placeholder values. Real credentials should be injected at deploy time:

```bash
helm install myapp ./devops-info-service \
  --set secrets.DATABASE_USERNAME=realuser \
  --set secrets.DATABASE_PASSWORD=realpassword
```

### How Secrets Are Consumed in Deployment

The deployment uses `envFrom` with `secretRef` to inject all secret keys as environment variables:

```yaml
envFrom:
  - secretRef:
      name: {{ include "devops-info-service.fullname" . }}-secret
```

### Verification

After deploying the chart:

```bash
$ helm install devops-info-service ./devops-info-service

$ kubectl get pods -l app.kubernetes.io/instance=devops-info-service
NAME                                                       READY   STATUS    RESTARTS   AGE
devops-info-service-devops-info-service-6f97c69c89-pkggk   1/1     Running   0          14s
devops-info-service-devops-info-service-6f97c69c89-tttsx   1/1     Running   0          14s
devops-info-service-devops-info-service-6f97c69c89-zjrxl   1/1     Running   0          14s

$ kubectl exec -it devops-info-service-devops-info-service-6f97c69c89-pkggk -- env | grep DATABASE
DATABASE_PASSWORD=changeme
DATABASE_USERNAME=admin
```

Secrets are **not** visible in `kubectl describe pod` output — environment variable values sourced from Secrets are hidden:

```bash
$ kubectl describe pod devops-info-service-devops-info-service-6f97c69c89-pkggk
```

```
    Environment Variables from:
      devops-info-service-devops-info-service-secret  Secret  Optional: false
    Environment:
      PORT:         5000
      APP_RELEASE:  v1
      APP_NAME:     devops-info-service-devops-info-service
      APP_ENV:      production
      LOG_LEVEL:    info
```

---

## Resource Management

### Resource Limits Configuration

Defined in `values.yaml`:

```yaml
resources:
  limits:
    cpu: 200m
    memory: 256Mi
  requests:
    cpu: 100m
    memory: 128Mi
```

### Requests vs Limits

| Aspect | Requests | Limits |
|--------|----------|--------|
| Purpose | Minimum guaranteed resources | Maximum allowed resources |
| Scheduling | Used by scheduler to find a suitable node | Not used for scheduling |
| Enforcement | Soft — pod gets at least this much | Hard — pod is killed/throttled if exceeded |
| CPU behavior | Guaranteed CPU time | Throttled if exceeded |
| Memory behavior | Guaranteed memory | OOMKilled if exceeded |

### How to Choose Appropriate Values

1. **Start with monitoring** — observe actual usage with `kubectl top pods` or Prometheus metrics
2. **Requests** — set to the P50 (median) usage of the application
3. **Limits** — set to 1.5-2x the requests to accommodate spikes
4. **CPU** — be generous with limits since CPU is compressible (throttled, not killed)
5. **Memory** — be more careful since exceeding memory limits causes OOMKill
6. **Use environment-specific values** — smaller for dev, larger for prod:

| Environment | CPU Request | CPU Limit | Memory Request | Memory Limit |
|-------------|-------------|-----------|----------------|--------------|
| Dev | 50m | 100m | 64Mi | 128Mi |
| Default | 100m | 200m | 128Mi | 256Mi |
| Prod | 200m | 500m | 256Mi | 512Mi |

---

## Vault Integration

### Installation

```bash
helm repo add hashicorp https://helm.releases.hashicorp.com
helm repo update
helm install vault hashicorp/vault \
  --set "server.dev.enabled=true" \
  --set "injector.enabled=true"
```

### Verification

```bash
$ kubectl get pods | grep vault
vault-0                                                    1/1     Running   0          59s
vault-agent-injector-848dd747d7-jptf9                      1/1     Running   0          59s
```

### KV Secrets Engine Configuration

```bash
$ kubectl exec vault-0 -- vault kv put secret/devops-info-service/config \
    username="db-admin" password="vault-managed-secret"
============= Secret Path =============
secret/data/devops-info-service/config

======= Metadata =======
Key                Value
---                -----
created_time       2026-04-06T21:29:28.203024055Z
custom_metadata    <nil>
deletion_time      n/a
destroyed          false
version            1
```

### Kubernetes Authentication

```bash
$ kubectl exec vault-0 -- vault auth enable kubernetes
Success! Enabled kubernetes auth method at: kubernetes/

$ kubectl exec vault-0 -- sh -c \
    'vault write auth/kubernetes/config kubernetes_host="https://$KUBERNETES_PORT_443_TCP_ADDR:443"'
Success! Data written to: auth/kubernetes/config
```

### Policy Configuration

```bash
$ kubectl exec -i vault-0 -- vault policy write devops-info-service - <<EOF
path "secret/data/devops-info-service/config" {
  capabilities = ["read"]
}
EOF
Success! Uploaded policy: devops-info-service
```

### Role Configuration

```bash
$ kubectl exec vault-0 -- vault write auth/kubernetes/role/devops-info-service \
    bound_service_account_names=devops-info-service-devops-info-service \
    bound_service_account_namespaces=default \
    policies=devops-info-service \
    ttl=24h
```

The role binds:

- **Service Account**: `devops-info-service-devops-info-service` (created by our Helm chart)
- **Namespace**: `default`
- **Policy**: `devops-info-service` (read access to our secret path)
- **TTL**: 24 hours

### Vault Agent Injection

Enable vault injection by setting `vault.enabled=true`:

```bash
helm upgrade devops-info-service ./devops-info-service --set vault.enabled=true
```

This adds the following annotations to the pod template:

```yaml
vault.hashicorp.com/agent-inject: "true"
vault.hashicorp.com/role: "devops-info-service"
vault.hashicorp.com/agent-inject-secret-config: "secret/data/devops-info-service/config"
```

### Pods with Vault Sidecar

After enabling Vault injection, pods run with 2 containers (app + vault-agent):

```bash
$ kubectl get pods -l app.kubernetes.io/instance=devops-info-service
NAME                                                       READY   STATUS    RESTARTS   AGE
devops-info-service-devops-info-service-5c74d45d5d-6ck9f   2/2     Running   0          43s
devops-info-service-devops-info-service-5c74d45d5d-wkmgk   2/2     Running   0          35s
devops-info-service-devops-info-service-5c74d45d5d-xlfgd   2/2     Running   0          27s
```

### Proof of Secret Injection

```bash
$ kubectl exec devops-info-service-devops-info-service-5c74d45d5d-6ck9f \
    -c devops-info-service -- cat /vault/secrets/config
DATABASE_USERNAME=db-admin
DATABASE_PASSWORD=vault-managed-secret
```

### Sidecar Injection Pattern

The Vault Agent Injector uses a **sidecar pattern**:

1. **Mutating Webhook** — the injector watches for pods with `vault.hashicorp.com/agent-inject: "true"` annotation
2. **Init Container** — added automatically; authenticates with Vault and fetches initial secrets before the main container starts
3. **Sidecar Container** — runs alongside the application; continuously watches for secret changes and refreshes the files
4. **Shared Volume** — secrets are written to `/vault/secrets/` on a shared in-memory volume (`emptyDir`) accessible to the main container

This approach keeps Vault credentials out of the application code entirely. The app simply reads files from a known path.

---

## Security Analysis

### Comparison: Kubernetes Secrets vs Vault

| Feature | K8s Secrets | HashiCorp Vault |
|---------|-------------|-----------------|
| Encryption at rest | Not by default (base64 only) | Encrypted with seal/unseal mechanism |
| Access control | RBAC-based | Fine-grained policies + RBAC |
| Audit logging | Via K8s audit logs | Built-in detailed audit log |
| Secret rotation | Manual | Automatic with dynamic secrets |
| Dynamic secrets | No | Yes (DB creds, AWS IAM, etc.) |
| Lease/TTL | No | Yes, secrets can expire |
| Versioning | No | Yes (KV v2) |
| UI | Limited (dashboard) | Full web UI |
| Complexity | Low | High |
| Dependencies | None (built-in) | Requires Vault deployment |

### When to Use Each Approach

**Use Kubernetes Secrets when:**

- Non-sensitive configuration that just needs to be separate from code
- Development/testing environments
- Simple deployments with few secrets
- etcd encryption at rest is enabled
- Team is small and trusted with cluster access

**Use HashiCorp Vault when:**

- Production environments with strict compliance requirements
- Dynamic secrets are needed (e.g., short-lived database credentials)
- Multiple teams/applications share secrets
- Audit trail is required for secret access
- Secret rotation must be automated
- Cross-cluster or multi-cloud secret management is needed

### Production Recommendations

1. **Never** store secrets in Git — use placeholder values and inject at deploy time
2. **Enable etcd encryption** at rest if using K8s Secrets
3. **Use RBAC** to restrict who can read secrets (`kubectl get secret`)
4. **Deploy Vault** for production workloads with sensitive credentials
5. **Enable audit logging** in both Kubernetes and Vault
6. **Rotate secrets regularly** — Vault's dynamic secrets automate this
7. **Use namespaces** to isolate secrets between teams/environments
8. **Consider External Secrets Operator** as a middle ground — syncs secrets from Vault/AWS/GCP into K8s Secrets

---

## Bonus: Vault Agent Templates

### Template Annotation Configuration

The Vault Agent template annotation allows rendering secrets in custom formats. Our implementation uses `.env` format:

```yaml
vault.hashicorp.com/agent-inject-template-config: |
  {{- with secret "secret/data/devops-info-service/config" -}}
  DATABASE_USERNAME={{ .Data.data.username }}
  DATABASE_PASSWORD={{ .Data.data.password }}
  {{- end -}}
```

This renders secrets as a `.env`-style file at `/vault/secrets/config`, which can be sourced directly by the application.

### Rendered Secret File Content

```
DATABASE_USERNAME=db-admin
DATABASE_PASSWORD=vault-managed-secret
```

### Dynamic Secret Rotation

Vault Agent handles secret updates automatically:

1. **Polling** — the sidecar agent periodically checks Vault for secret changes
2. **Automatic Re-rendering** — when secrets change, the agent re-renders the template files
3. **Command Execution** — `vault.hashicorp.com/agent-inject-command` annotation can trigger a command after secret update (e.g., send SIGHUP to reload the app):

```yaml
vault.hashicorp.com/agent-inject-command-config: "/bin/sh -c 'kill -HUP $(pidof python)'"
```

This enables zero-downtime secret rotation without pod restarts.

### Named Template Implementation

In `_helpers.tpl`:

```yaml
{{- define "devops-info-service.envVars" -}}
- name: APP_NAME
  value: {{ include "devops-info-service.fullname" . }}
- name: APP_ENV
  value: {{ .Values.environment | default "production" }}
- name: LOG_LEVEL
  value: {{ .Values.logLevel | default "info" }}
{{- end -}}
```

Used in `deployment.yaml`:

```yaml
env:
  {{- toYaml .Values.env | nindent 12 }}
  {{- include "devops-info-service.envVars" . | nindent 12 }}
```

### Benefits of Templating Approach

1. **DRY Principle** — common environment variables defined once, reused across multiple deployments
2. **Consistency** — all deployments using the named template get the same base variables
3. **Maintainability** — changes to common vars happen in one place (`_helpers.tpl`)
4. **Custom Formats** — Vault template annotations allow rendering secrets in any format (`.env`, JSON, YAML, TOML) matching what the application expects
5. **Separation of Concerns** — secrets management is decoupled from application configuration
