# Lab 09 — Kubernetes Fundamentals

## 1) Architecture Overview

Implemented Kubernetes architecture (main task):

- `Deployment/devops-info-service` with 3 replicas (`Pod` replicas of FastAPI app).
- `Service/devops-info-service` of type `NodePort` for local access from host.
- Health model:
  - `readinessProbe` on `GET /health` for traffic gating.
  - `livenessProbe` on `GET /health` for self-healing restarts.
- Update model:
  - `RollingUpdate` (`maxSurge: 1`, `maxUnavailable: 0`) to keep service available during rollout.
- Resource policy:
  - Requests: `100m CPU`, `128Mi memory`.
  - Limits: `200m CPU`, `256Mi memory`.

Traffic flow:

`Client -> NodeIP:30080 -> Service (NodePort:80) -> Pods (containerPort:5000)`

Bonus architecture:

- `Deployment/devops-info-service-app2` + `Service/devops-info-service-app2` (`ClusterIP`).
- `Ingress/devops-info-ingress` with path routing:
  - `/app1` -> `devops-info-service`
  - `/app2` -> `devops-info-service-app2`
- TLS termination on host `local.example.com` via secret `local-example-com-tls`.

## 2) Manifest Files and Key Choices

### `k8s/deployment.yml`

- Main workload for app image from Lab 2: `mituta/devops-info-service:lab02`.
- `replicas: 3` satisfies lab minimum and gives basic HA.
- Probes use existing `/health` endpoint from app.
- Resource requests/limits set to avoid noisy-neighbor behavior and improve scheduler decisions.
- `APP_RELEASE=v1` was added to make controlled rollout demonstrations easy (change to `v2` -> rollout).

### `k8s/service.yml`

- `NodePort` service for local cluster access without cloud LB.
- Fixed `nodePort: 30080` for deterministic testing and documentation.
- Selects pods by `app: devops-info-service`.

### Bonus files

- `k8s/deployment-app2.yml`: second app workload (same image, separate deployment/labels).
- `k8s/service-app2.yml`: internal service for second app.
- `k8s/ingress.yml`: path-based routing + TLS host config.

## 3) Setup and Deployment Commands

### Tool verification

```bash
kubectl version --client
```

### Cluster start (choose one)

#### Option A: minikube

```bash
minikube start --driver=docker
kubectl cluster-info
kubectl get nodes -o wide
kubectl get namespaces
```

#### Option B: kind

```bash
kind create cluster --name devops-lab09
kubectl cluster-info
kubectl get nodes -o wide
kubectl get namespaces
```

### Deploy main app

```bash
kubectl apply -f k8s/deployment.yml
kubectl apply -f k8s/service.yml

kubectl get deployments
kubectl get pods -o wide
kubectl get svc
kubectl describe deployment devops-info-service
```

### Access checks

#### minikube

```bash
minikube service devops-info-service --url
curl "$(minikube service devops-info-service --url)/health"
curl "$(minikube service devops-info-service --url)/"
```

#### kind/other local cluster

```bash
kubectl port-forward service/devops-info-service 8080:80
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8080/
```

## 4) Scaling, Rolling Update, Rollback

### Scaling to 5 replicas

Declarative:

1. Set `spec.replicas: 5` in `k8s/deployment.yml`.
2. Apply:

```bash
kubectl apply -f k8s/deployment.yml
kubectl rollout status deployment/devops-info-service
kubectl get pods -l app=devops-info-service
```

Imperative check:

```bash
kubectl scale deployment/devops-info-service --replicas=5
kubectl get deployment devops-info-service
```

### Rolling update demonstration

Use config change (safe, does not require new Docker image):

```bash
kubectl set env deployment/devops-info-service APP_RELEASE=v2
kubectl rollout status deployment/devops-info-service
kubectl rollout history deployment/devops-info-service
```

Alternative: edit `k8s/deployment.yml` and change `APP_RELEASE` value, then `kubectl apply -f`.

### Rollback

```bash
kubectl rollout undo deployment/devops-info-service
kubectl rollout status deployment/devops-info-service
kubectl rollout history deployment/devops-info-service
```

Zero-downtime verification (during rollout):

```bash
while true; do curl -sf http://127.0.0.1:8080/health || echo "failed"; sleep 1; done
```

## 5) Bonus — Ingress + TLS

### Deploy second app + service

```bash
kubectl apply -f k8s/deployment-app2.yml
kubectl apply -f k8s/service-app2.yml
kubectl get deployments,svc
```

### Enable/Install ingress controller

#### minikube

```bash
minikube addons enable ingress
kubectl get pods -n ingress-nginx
```

#### kind

```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml
kubectl get pods -n ingress-nginx
```

### Create TLS secret and apply ingress

```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout tls.key \
  -out tls.crt \
  -subj "/CN=local.example.com/O=local.example.com"

kubectl create secret tls local-example-com-tls \
  --key tls.key \
  --cert tls.crt

kubectl apply -f k8s/ingress.yml
kubectl get ingress
```

Add hosts entry:

```bash
echo "$(minikube ip) local.example.com" | sudo tee -a /etc/hosts
```

Routing checks:

```bash
curl -k https://local.example.com/app1/health
curl -k https://local.example.com/app2/health
```

## 6) Production Considerations

- Probes:
  - `readinessProbe` protects users from requests to not-ready pods.
  - `livenessProbe` ensures failed pods are restarted.
- Resources:
  - Conservative defaults for small FastAPI app.
  - In production, tune by measuring real p95 CPU/RAM utilization.
- Security:
  - Image from Lab 2 already runs as non-root.
  - Next step: add Pod Security context and read-only root filesystem if app supports it.
- Reliability:
  - Add HPA (`cpu` and custom metrics).
  - Add `PodDisruptionBudget` and anti-affinity.
- Observability:
  - App already exposes `/metrics`; integrate ServiceMonitor (lab 16 stack), alerts, and dashboards.

## 7) Execution Evidence (Captured)

### Cluster and context

```bash
$ kubectl config current-context
minikube

$ kubectl get nodes -o wide
NAME       STATUS   ROLES           AGE     VERSION   INTERNAL-IP    OS-IMAGE                         CONTAINER-RUNTIME
minikube   Ready    control-plane   2m59s   v1.35.1   192.168.49.2   Debian GNU/Linux 12 (bookworm)   docker://29.2.1
```

### Main deployment and service

```bash
$ kubectl apply -f k8s/deployment.yml
deployment.apps/devops-info-service created

$ kubectl apply -f k8s/service.yml
service/devops-info-service created

$ kubectl rollout status deployment/devops-info-service
deployment "devops-info-service" successfully rolled out
```

```bash
$ kubectl get deployments,pods,svc -o wide
deployment.apps/devops-info-service   3/3   3   3   ...   mituta/devops-info-service:lab02
service/devops-info-service           NodePort   10.108.200.64   80:30080/TCP
pod/devops-info-service-...           1/1   Running   ...   10.244.0.3
pod/devops-info-service-...           1/1   Running   ...   10.244.0.4
pod/devops-info-service-...           1/1   Running   ...   10.244.0.5
```

### Endpoint checks

```bash
$ minikube service devops-info-service --url
http://127.0.0.1:62882
```

```bash
$ curl http://127.0.0.1:62882/health
{"status":"healthy","timestamp":"2026-03-25T17:30:42.314483Z","uptime_seconds":71}

$ curl http://127.0.0.1:62882/ | python3 -m json.tool
{
  "service": {"name": "devops-info-service", "version": "1.0.0", ...},
  "system": {"platform": "Linux", "python_version": "3.13.11", ...},
  "runtime": {...}
}
```

### Scaling, rolling update, rollback

```bash
$ kubectl scale deployment/devops-info-service --replicas=5
deployment.apps/devops-info-service scaled

$ kubectl get deployment devops-info-service
NAME                  READY   UP-TO-DATE   AVAILABLE
devops-info-service   5/5     5            5
```

```bash
$ kubectl set env deployment/devops-info-service APP_RELEASE=v2
deployment.apps/devops-info-service env updated

$ kubectl rollout history deployment/devops-info-service
REVISION  CHANGE-CAUSE
1         <none>
2         <none>
```

```bash
$ kubectl rollout undo deployment/devops-info-service
deployment.apps/devops-info-service rolled back

$ kubectl get deployment devops-info-service -o jsonpath='{.spec.replicas}{"\n"}{.spec.template.spec.containers[0].env[1].name}{"="}{.spec.template.spec.containers[0].env[1].value}{"\n"}'
5
APP_RELEASE=v1
```

### Bonus evidence (Ingress + TLS)

```bash
$ kubectl apply -f k8s/deployment-app2.yml
deployment.apps/devops-info-service-app2 created

$ kubectl apply -f k8s/service-app2.yml
service/devops-info-service-app2 created
```

```bash
$ minikube addons enable ingress
The 'ingress' addon is enabled
```

```bash
$ kubectl apply -f k8s/ingress.yml
ingress.networking.k8s.io/devops-info-ingress created

$ kubectl get ingress
NAME                  CLASS   HOSTS               ADDRESS        PORTS
devops-info-ingress   nginx   local.example.com   192.168.49.2   80, 443
```

```bash
$ curl -sk --resolve local.example.com:8443:127.0.0.1 https://local.example.com:8443/app1/health
{"status":"healthy","timestamp":"2026-03-25T17:36:04.851997Z","uptime_seconds":253}

$ curl -sk --resolve local.example.com:8443:127.0.0.1 https://local.example.com:8443/app2/health
{"status":"healthy","timestamp":"2026-03-25T17:36:04.890708Z","uptime_seconds":194}
```

Note: HTTPS verification used temporary `kubectl port-forward` to ingress controller (`8443:443`) for deterministic local testing.

## 8) Challenges and Debugging Notes

- During minikube startup there was a warning about high Docker disk usage (`85%`). Cluster still started successfully.
- With Docker driver on macOS, `minikube service --url` requires keeping terminal session open while testing URL.
- Direct testing of ingress via node IP/NodePort was unreliable in this local setup, so validation was done with `kubectl port-forward` + `curl --resolve`.

Useful debug commands:

```bash
kubectl get events --sort-by=.metadata.creationTimestamp
kubectl describe pod <pod-name>
kubectl logs <pod-name>
kubectl get endpoints devops-info-service
kubectl describe ingress devops-info-ingress
```

## 9) What Still Needs To Be Done Manually

1. Add screenshots for submission (cluster info, `kubectl get all`, and working curl responses).
2. If you want clean HTTPS without port-forward, add `/etc/hosts` entry and run `minikube tunnel`.
3. Optionally run a long zero-downtime loop during rollout and include output snippet.
4. Recreate TLS files locally before applying ingress in a fresh cluster (`openssl ...`, then `kubectl create secret tls ...`).

## 10) Why Ingress Over Only NodePort

- Single entrypoint for multiple services.
- L7 routing by host/path (`/app1`, `/app2`) instead of only TCP port mapping.
- Centralized TLS termination.
- Easier evolution to production patterns than many exposed NodePorts.
