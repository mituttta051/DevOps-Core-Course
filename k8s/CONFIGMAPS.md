# ConfigMaps & Persistent Volumes

## Application Changes

### Visits Counter Implementation

The application was extended with a persistent visit counter:

- Each request to `GET /` increments a counter stored in `/data/visits`
- A new `GET /visits` endpoint returns the current count
- The counter is read from file on each request (defaults to 0 if file doesn't exist)
- Thread safety is ensured via `threading.Lock`
- The visits file path is configurable via `VISITS_FILE` environment variable

### New Endpoint

**`GET /visits`** - Returns the current visit count:

```json
{
  "visits": 42
}
```

### Local Testing with Docker

Docker Compose configuration (`app_python/docker-compose.yml`) mounts a volume for persistence:

```yaml
services:
  app-python:
    build: .
    ports:
      - "5000:5000"
    volumes:
      - ./data:/data
    environment:
      - PORT=5000
      - VISITS_FILE=/data/visits
```

**Test evidence:**

```
# First run - 3 requests to /
$ curl -s http://localhost:5001/visits
{"visits": 3}

# After container restart
$ docker restart test-visits
$ curl -s http://localhost:5001/visits
{"visits": 3}

# File on host
$ cat ./data/visits
3
```

The counter persists across container restarts via the mounted volume.

## ConfigMap Implementation

### ConfigMap Template Structure

Two ConfigMaps are defined in `templates/configmap.yaml`:

1. **File-based ConfigMap** (`-config`) — loads `files/config.json` as a file
2. **Environment ConfigMap** (`-env`) — provides key-value pairs as environment variables

### config.json Content

```json
{
  "app_name": "devops-info-service",
  "environment": "production",
  "version": "1.0.0",
  "features": {
    "visits_counter": true,
    "prometheus_metrics": true
  },
  "settings": {
    "log_format": "json",
    "timezone": "UTC"
  }
}
```

### ConfigMap Mounted as File

The file-based ConfigMap is mounted as a volume at `/config`:

```yaml
volumeMounts:
  - name: config-volume
    mountPath: /config
volumes:
  - name: config-volume
    configMap:
      name: {{ include "devops-info-service.fullname" . }}-config
```

**Verification:**

```bash
$ kubectl exec myrelease-devops-info-service-5bcd8ff7f-q9dxm -- cat /config/config.json
{
  "app_name": "devops-info-service",
  "environment": "production",
  "version": "1.0.0",
  "features": {
    "visits_counter": true,
    "prometheus_metrics": true
  },
  "settings": {
    "log_format": "json",
    "timezone": "UTC"
  }
}
```

### ConfigMap as Environment Variables

The env ConfigMap is injected via `envFrom`:

```yaml
envFrom:
  - configMapRef:
      name: {{ include "devops-info-service.fullname" . }}-env
```

This injects `APP_ENV`, `LOG_LEVEL`, and `APP_NAME` as environment variables.

**Verification:**

```bash
$ kubectl exec myrelease-devops-info-service-5bcd8ff7f-q9dxm -- printenv | grep -E "APP_|LOG_"
APP_NAME=myrelease-devops-info-service
LOG_LEVEL=info
APP_ENV=production
APP_RELEASE=v1
```

### Rendered ConfigMap Output

```bash
$ kubectl get configmap,pvc
NAME                                             DATA   AGE
configmap/kube-root-ca.crt                       1      20d
configmap/myrelease-devops-info-service-config   1      22m
configmap/myrelease-devops-info-service-env      3      22m

NAME                                                       STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS   AGE
persistentvolumeclaim/myrelease-devops-info-service-data   Bound    pvc-41f7c17c-58c2-4d3c-a598-37f3eaeaadd0   100Mi      RWO            standard       22m
```

## Persistent Volume

### PVC Configuration

The PVC is defined in `templates/pvc.yaml`:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: {{ include "devops-info-service.fullname" . }}-data
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: {{ .Values.persistence.size }}
```

**Values (`values.yaml`):**

```yaml
persistence:
  enabled: true
  size: 100Mi
  storageClass: ""
```

### Access Modes and Storage Class

- **ReadWriteOnce (RWO):** The volume can be mounted as read-write by a single node. This is sufficient for our single-replica deployment with a visit counter.
- **Storage Class:** Left empty to use the cluster default. On Minikube, this provisions a `hostPath` volume automatically. In production, this would be set to a cloud provider's storage class (e.g., `gp3` on AWS, `standard` on GKE).

### Volume Mount Configuration

The PVC is mounted at `/data` in the deployment:

```yaml
volumeMounts:
  - name: data-volume
    mountPath: /data
volumes:
  - name: data-volume
    persistentVolumeClaim:
      claimName: {{ include "devops-info-service.fullname" . }}-data
```

### Persistence Test Evidence

```bash
# Access root endpoint 3 times via in-cluster curl
$ kubectl run curl-test --image=curlimages/curl --rm -it --restart=Never -- sh -c \
  "curl -s http://10.102.225.4/ > /dev/null && \
   curl -s http://10.102.225.4/ > /dev/null && \
   curl -s http://10.102.225.4/ > /dev/null && \
   curl -s http://10.102.225.4/visits"
{"visits":3}

# Check visits file in pod
$ kubectl exec myrelease-devops-info-service-5bcd8ff7f-q9dxm -- cat /data/visits
3

# Delete the pod
$ kubectl delete pod myrelease-devops-info-service-5bcd8ff7f-q9dxm
pod "myrelease-devops-info-service-5bcd8ff7f-q9dxm" deleted

# New pod starts automatically
$ kubectl get pods -l app.kubernetes.io/instance=myrelease
NAME                                            READY   STATUS    RESTARTS   AGE
myrelease-devops-info-service-5bcd8ff7f-jk2zv   1/1     Running   0          8s
myrelease-devops-info-service-5bcd8ff7f-t8rrp   1/1     Running   0          51m
myrelease-devops-info-service-5bcd8ff7f-zksr4   1/1     Running   0          51m

# Verify counter is preserved after pod restart
$ kubectl run curl-test2 --image=curlimages/curl --rm -it --restart=Never -- \
  curl -s http://10.102.225.4/visits
{"visits":3}
```

The data survives pod deletion because the PVC retains data independently of pod lifecycle.

## ConfigMap vs Secret

| Aspect | ConfigMap | Secret |
|--------|-----------|--------|
| **Purpose** | Non-sensitive configuration data | Sensitive data (passwords, tokens, keys) |
| **Storage** | Stored as plain text in etcd | Base64-encoded in etcd (encrypted at rest if configured) |
| **Size limit** | 1 MiB | 1 MiB |
| **Use cases** | App config files, environment settings, feature flags | Database credentials, API keys, TLS certificates |
| **Access control** | Standard RBAC | Stricter RBAC recommended |
| **Mounting** | Volume or env vars | Volume or env vars |

**When to use ConfigMap:**
- Application configuration files (JSON, YAML, properties)
- Environment-specific settings (log level, feature flags)
- Non-sensitive key-value pairs

**When to use Secret:**
- Database credentials
- API keys and tokens
- TLS certificates and private keys
- Any data that should not appear in logs or be visible in plain text

## Bonus: ConfigMap Hot Reload

### Default Update Behavior

When a ConfigMap is updated (e.g., via `kubectl edit configmap`), Kubernetes propagates the change to mounted volumes. The kubelet syncs ConfigMap changes periodically (default sync period: 60 seconds + cache TTL). The total delay can be up to a few minutes.

### subPath Limitation

When using `subPath` to mount a single file from a ConfigMap (e.g., `mountPath: /config/config.json`, `subPath: config.json`), the mounted file is a **copy**, not a symlink. Therefore, it does **not** receive automatic updates when the ConfigMap changes.

**When to use `subPath`:** When you need to mount a single file into an existing directory without overwriting other files.

**When to avoid `subPath`:** When you need automatic ConfigMap updates. Use full directory mounts instead.

### Checksum Annotation Pattern (Implemented)

The deployment uses a checksum annotation to trigger pod restarts when ConfigMap content changes:

```yaml
spec:
  template:
    metadata:
      annotations:
        checksum/config: {{ include (print $.Template.BasePath "/configmap.yaml") . | sha256sum }}
```

When `helm upgrade` is run and the ConfigMap content has changed, the checksum annotation value changes, causing Kubernetes to perform a rolling update of the pods.

**How it works:**
1. Helm renders the ConfigMap template and computes its SHA-256 hash
2. The hash is stored as a pod annotation
3. On `helm upgrade`, if the ConfigMap content changes, the hash changes
4. Changed pod template triggers a rolling deployment
5. New pods pick up the updated ConfigMap

This approach ensures configuration changes are always applied without manual intervention.
