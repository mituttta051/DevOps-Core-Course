# Lab 15 — StatefulSets & Persistent Storage

Workload migration from `Deployment` / `Rollout` (Lab 10‑14) to a **StatefulSet** with per‑pod `PersistentVolumeClaim`s, a **headless Service**, and verified DNS‑based pod identity.

Release: `lab15-sts` in namespace `lab15`
Chart: [`k8s/devops-info-service`](devops-info-service)
Values: [`values-statefulset.yaml`](devops-info-service/values-statefulset.yaml)

---

## 1. StatefulSet Overview

### Why StatefulSet here

The Python service keeps its visit counter on disk (`VISITS_FILE`, read/written by [`app_python/app.py`](../app_python/app.py) lines 83, 90‑100). With a `Deployment` all pods race for the same `PVC` (`ReadWriteOnce` → only one pod can mount) and we lose per‑pod state on reschedule. `StatefulSet` fixes this:

| Property                | `Deployment` / `Rollout`            | `StatefulSet`                                      |
| ----------------------- | ----------------------------------- | -------------------------------------------------- |
| Pod names               | `...-<rs-hash>-<rand>`              | `<name>-0`, `<name>-1`, `<name>-2` (stable)        |
| Storage                 | One shared PVC or none              | One PVC per pod via `volumeClaimTemplates`         |
| Scale order             | Parallel                            | Ordered `0 → 1 → 2` (and reverse on scale‑in)      |
| Network identity        | Service VIP only                    | Stable DNS: `pod-0.<headless>.<ns>.svc.cluster.local` |
| Update strategies       | `Recreate`, `RollingUpdate`         | `RollingUpdate` (with `partition`), `OnDelete`     |
| Good for                | Stateless HTTP, progressive delivery | DBs, queues, anything with per‑pod on‑disk state   |

### Headless Service

A Service with `clusterIP: None` does **not** load‑balance. It returns one DNS `A` record per Ready pod, plus per‑pod records for Pod‑addressable DNS. This is what gives each StatefulSet pod its own stable hostname. The regular `ClusterIP` Service is kept for external clients that just want any pod.

### Relation to previous labs

- Builds on the Lab 12 persistence work (`VISITS_FILE=/data/visits`) and the Lab 10 Helm chart.
- Rollouts (Lab 14) stay in the chart — `deployment.yaml`, `rollout.yaml`, and `statefulset.yaml` are mutually exclusive via `rollout.enabled` / `statefulset.enabled` flags.
- Compatible with ArgoCD (Lab 13): the existing Argo `Application` is untouched; this lab is installed as a separate release `lab15-sts` in its own namespace.

---

## 2. Resource Verification

```console
$ kubectl get po,sts,svc,pvc -n lab15 -o wide
NAME                                  READY   STATUS    RESTARTS   AGE    IP            NODE       NOMINATED NODE   READINESS GATES
pod/lab15-sts-devops-info-service-0   1/1     Running   0          108m   10.244.1.7    minikube   <none>           <none>
pod/lab15-sts-devops-info-service-1   1/1     Running   0          109m   10.244.1.5    minikube   <none>           <none>
pod/lab15-sts-devops-info-service-2   1/1     Running   0          96m    10.244.1.10   minikube   <none>           <none>

NAME                                             READY   AGE    CONTAINERS            IMAGES
statefulset.apps/lab15-sts-devops-info-service   3/3     109m   devops-info-service   mituta/devops-info-service:lab12

NAME                                             TYPE        CLUSTER-IP     EXTERNAL-IP   PORT(S)   AGE    SELECTOR
service/lab15-sts-devops-info-service            ClusterIP   10.96.135.47   <none>        80/TCP    109m   app.kubernetes.io/instance=lab15-sts,app.kubernetes.io/name=devops-info-service
service/lab15-sts-devops-info-service-headless   ClusterIP   None           <none>        80/TCP    109m   app.kubernetes.io/instance=lab15-sts,app.kubernetes.io/name=devops-info-service

NAME                                                         STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS   AGE    VOLUMEMODE
persistentvolumeclaim/data-lab15-sts-devops-info-service-0   Bound    pvc-a9fb6499-e6dc-4910-bd45-11bbd30da137   100Mi      RWO            standard       109m   Filesystem
persistentvolumeclaim/data-lab15-sts-devops-info-service-1   Bound    pvc-ce6c233d-f150-42eb-a280-eb5d834978bb   100Mi      RWO            standard       109m   Filesystem
persistentvolumeclaim/data-lab15-sts-devops-info-service-2   Bound    pvc-66a299ac-dceb-4c88-8ca0-9e931929b0d7   100Mi      RWO            standard       109m   Filesystem
```

Key observations:

- Pods have ordinal suffixes (`-0`, `-1`, `-2`) — guaranteed by StatefulSet.
- Two services: normal `ClusterIP` for external access and `headless` (`ClusterIP: None`) for DNS‑based pod addressing.
- Three PVCs, named `data-<sts-name>-<ordinal>`, generated automatically from `volumeClaimTemplates`.

---

## 3. Network Identity (Stable DNS)

From inside `pod-0`, each sibling resolves to its own stable FQDN:

```console
$ kubectl exec -n lab15 lab15-sts-devops-info-service-0 -- \
    getent hosts \
      lab15-sts-devops-info-service-0.lab15-sts-devops-info-service-headless.lab15.svc.cluster.local \
      lab15-sts-devops-info-service-1.lab15-sts-devops-info-service-headless.lab15.svc.cluster.local \
      lab15-sts-devops-info-service-2.lab15-sts-devops-info-service-headless.lab15.svc.cluster.local
10.244.1.7   lab15-sts-devops-info-service-0.lab15-sts-devops-info-service-headless.lab15.svc.cluster.local lab15-sts-devops-info-service-0
10.244.1.5   lab15-sts-devops-info-service-1.lab15-sts-devops-info-service-headless.lab15.svc.cluster.local
10.244.1.10  lab15-sts-devops-info-service-2.lab15-sts-devops-info-service-headless.lab15.svc.cluster.local
```

Pattern: `<pod-name>.<headless-service>.<namespace>.svc.cluster.local`

The headless service itself returns **all** pod IPs (one record per Ready pod), not a VIP:

```console
$ kubectl exec -n lab15 lab15-sts-devops-info-service-0 -- \
    getent hosts lab15-sts-devops-info-service-headless.lab15.svc.cluster.local
10.244.1.7   lab15-sts-devops-info-service-headless.lab15.svc.cluster.local
10.244.1.5   lab15-sts-devops-info-service-headless.lab15.svc.cluster.local
10.244.1.10  lab15-sts-devops-info-service-headless.lab15.svc.cluster.local
```

---

## 4. Per‑Pod Storage Evidence

Each pod has its own `/data` volume (backed by its own PVC), so the visit counter diverges per pod. After hitting `pod-0` five times, `pod-1` three times, `pod-2` once:

```console
$ kubectl port-forward -n lab15 pod/lab15-sts-devops-info-service-0 18080:5000 &
$ kubectl port-forward -n lab15 pod/lab15-sts-devops-info-service-1 18081:5000 &
$ kubectl port-forward -n lab15 pod/lab15-sts-devops-info-service-2 18082:5000 &

$ for i in 1 2 3 4 5; do curl -s -o /dev/null localhost:18080/; done
$ for i in 1 2 3;     do curl -s -o /dev/null localhost:18081/; done
$ for i in 1;         do curl -s -o /dev/null localhost:18082/; done

$ curl -s localhost:18080/visits
{"visits":5}
$ curl -s localhost:18081/visits
{"visits":3}
$ curl -s localhost:18082/visits
{"visits":1}
```

Files on disk confirm the split — each pod writes to its own PVC:

```console
$ for i in 0 1 2; do
    echo "pod-$i:"
    kubectl exec -n lab15 lab15-sts-devops-info-service-$i -- cat /data/visits
  done
pod-0:
5
pod-1:
3
pod-2:
1
```

Hitting `pod-1` would never change `pod-0`'s counter: their PVCs (`data-...-0` and `data-...-1`) are different volumes. This is exactly what you cannot get from a `Deployment`.

---

## 5. Persistence Test (Data Survives Pod Deletion)

```console
$ kubectl exec -n lab15 lab15-sts-devops-info-service-0 -- cat /data/visits
5

$ kubectl delete pod -n lab15 lab15-sts-devops-info-service-0
pod "lab15-sts-devops-info-service-0" deleted from lab15 namespace

$ kubectl wait --for=condition=ready pod/lab15-sts-devops-info-service-0 \
    -n lab15 --timeout=60s
pod/lab15-sts-devops-info-service-0 condition met

$ kubectl exec -n lab15 lab15-sts-devops-info-service-0 -- cat /data/visits
5
```

The PVC `data-lab15-sts-devops-info-service-0` is reattached to the replacement pod with the same ordinal. Data survives.

---

## 6. Bonus — Update Strategies

### RollingUpdate with `partition: 2`

Values file: [`values-sts-partition.yaml`](devops-info-service/values-sts-partition.yaml).

With `partition: 2`, only pods with ordinal **≥ 2** are updated (i.e. just `pod-2` in a 3‑replica set). This is the building block for staged / canary‑style updates on stateful workloads.

```console
$ helm upgrade lab15-sts . -f values-sts-partition.yaml \
    --set podAnnotations.rev=v2 -n lab15
Release "lab15-sts" has been upgraded. Happy Helming!

$ kubectl get sts lab15-sts-devops-info-service -n lab15 \
    -o jsonpath='{.spec.updateStrategy}'; echo
{"rollingUpdate":{"maxUnavailable":1,"partition":2},"type":"RollingUpdate"}

$ kubectl get pods -n lab15
NAME                              READY   STATUS    RESTARTS   AGE
lab15-sts-devops-info-service-0   1/1     Running   0          10m    # untouched
lab15-sts-devops-info-service-1   1/1     Running   0          11m    # untouched
lab15-sts-devops-info-service-2   1/1     Running   0          22s    # updated
```

Only `pod-2` got recreated; `pod-0` and `pod-1` keep their original age because their ordinals are below the partition.

### `OnDelete`

Values file: [`values-sts-ondelete.yaml`](devops-info-service/values-sts-ondelete.yaml).

Under `updateStrategy.type: OnDelete` the controller never recreates pods on spec change — operators delete pods manually, one by one, in whatever order suits them. Use cases: DBs where a leader must be drained before a restart, or clusters needing externally‑coordinated rollouts.

```console
$ helm upgrade lab15-sts . -f values-sts-ondelete.yaml \
    --set podAnnotations.rev=v3 -n lab15
Release "lab15-sts" has been upgraded. Happy Helming!

$ kubectl get sts lab15-sts-devops-info-service -n lab15 \
    -o jsonpath='{.spec.updateStrategy}'; echo
{"type":"OnDelete"}

# Pods keep running the OLD spec — no automatic rollout.
$ kubectl get pods -n lab15
NAME                              READY   STATUS    RESTARTS   AGE
lab15-sts-devops-info-service-0   1/1     Running   0          10m
lab15-sts-devops-info-service-1   1/1     Running   0          12m
lab15-sts-devops-info-service-2   1/1     Running   0          36s

# Update is opt‑in: delete a pod to pick up the new spec.
$ kubectl delete pod -n lab15 lab15-sts-devops-info-service-2
pod "lab15-sts-devops-info-service-2" deleted from lab15 namespace
$ kubectl get pods -n lab15
NAME                              READY   STATUS    RESTARTS   AGE
lab15-sts-devops-info-service-0   1/1     Running   0          11m
lab15-sts-devops-info-service-1   1/1     Running   0          12m
lab15-sts-devops-info-service-2   1/1     Running   0          7s     # manually recycled
```

---

## 7. How it's wired in the chart

New / changed files:

- [`templates/statefulset.yaml`](devops-info-service/templates/statefulset.yaml) — the new StatefulSet (gated by `statefulset.enabled`).
- [`templates/service-headless.yaml`](devops-info-service/templates/service-headless.yaml) — headless Service (`clusterIP: None`).
- [`templates/deployment.yaml`](devops-info-service/templates/deployment.yaml) — now guarded: `if (not rollout.enabled) and (not statefulset.enabled)`.
- [`templates/rollout.yaml`](devops-info-service/templates/rollout.yaml) — guarded: `if rollout.enabled and (not statefulset.enabled)`.
- [`templates/pvc.yaml`](devops-info-service/templates/pvc.yaml) — shared PVC suppressed when the StatefulSet is active (PVCs come from `volumeClaimTemplates`).
- [`values.yaml`](devops-info-service/values.yaml) — added `statefulset.*` block.
- [`values-statefulset.yaml`](devops-info-service/values-statefulset.yaml) — baseline StatefulSet values.
- [`values-sts-partition.yaml`](devops-info-service/values-sts-partition.yaml) — partition=2 rollout.
- [`values-sts-ondelete.yaml`](devops-info-service/values-sts-ondelete.yaml) — OnDelete strategy.

`VISITS_FILE=/data/visits` is injected into the pod spec so the app's counter persists on the per‑pod PVC.

---

## 8. Reproduce Locally

```bash
minikube start
kubectl create namespace lab15

helm install lab15-sts ./k8s/devops-info-service \
  -f ./k8s/devops-info-service/values-statefulset.yaml \
  -n lab15

kubectl get po,sts,svc,pvc -n lab15
```

Cleanup:

```bash
helm uninstall lab15-sts -n lab15
kubectl delete pvc -l app.kubernetes.io/instance=lab15-sts -n lab15
kubectl delete namespace lab15
```

> Note: StatefulSet PVCs are **not** deleted automatically on `helm uninstall` — this is a K8s safety default so you don't lose data. Delete them explicitly when you're sure.
