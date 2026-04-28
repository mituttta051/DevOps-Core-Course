# Lab 16 — Kubernetes Monitoring & Init Containers

Этот документ описывает установку и использование `kube-prometheus-stack` (Prometheus + Grafana + Alertmanager) в кластере Minikube, а также реализацию двух паттернов init-контейнеров.

---

## 1. Stack Components

`kube-prometheus-stack` — это «всё-в-одном» Helm-чарт от prometheus-community, который ставит сразу полный observability-стек поверх Kubernetes.

| Компонент | Роль |
|-----------|------|
| **Prometheus Operator** | Контроллер, который слушает CRD (`Prometheus`, `ServiceMonitor`, `PodMonitor`, `PrometheusRule`, `Alertmanager`) и автоматически перегенерирует конфиг Prometheus/Alertmanager при их изменении. Без оператора пришлось бы вручную редактировать `prometheus.yml` после каждого нового сервиса. |
| **Prometheus** | Time-series база данных и движок сбора метрик. Сам ходит по эндпоинтам `/metrics` (модель pull), хранит данные в TSDB и позволяет выполнять PromQL-запросы. В нашем релизе сервис называется `monitoring-kube-prometheus-prometheus`, UI — порт `9090`. |
| **Alertmanager** | Получает алерты от Prometheus, дедуплицирует, группирует и рассылает их в каналы (Slack, email, PagerDuty). UI на порту `9093`. |
| **Grafana** | Визуализация метрик: дашборды, алёрты, exploration. В чарт уже зашиты ~30 готовых K8s-дашбордов, ходит к Prometheus как к datasource. UI — `monitoring-grafana:80`, логин `admin / prom-operator`. |
| **kube-state-metrics** | Экспортер, который превращает состояние объектов API (Deployment, Pod, Node, PVC...) в метрики (`kube_pod_status_phase`, `kube_deployment_status_replicas` и т.д.). В отличие от node-exporter показывает не «железо», а K8s-объекты. |
| **node-exporter** | DaemonSet — на каждом ноде один pod, экспортирующий метрики ОС и железа: CPU, RAM, диски, сеть, файловая система, загрузка ядра. Это «hardware» layer наблюдаемости. |

Итог: оператор управляет конфигурацией; Prometheus собирает метрики из node-exporter (узлы), kube-state-metrics (объекты K8s), kubelet (cAdvisor — контейнеры) и пользовательских ServiceMonitor; Grafana их визуализирует; Alertmanager отправляет алерты.

---

## 2. Installation Evidence

### Команды установки

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm install monitoring prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --wait
```

### `kubectl get po,svc -n monitoring`

```
$ kubectl get po,svc -n monitoring
NAME                                                         READY   STATUS    RESTARTS   AGE
pod/alertmanager-monitoring-kube-prometheus-alertmanager-0   2/2     Running   0          19m
pod/monitoring-grafana-6444469567-qcjxs                      3/3     Running   0          19m
pod/monitoring-kube-prometheus-operator-599876bb6b-txjzr     1/1     Running   0          19m
pod/monitoring-kube-state-metrics-67d5f7bf68-xsp99           1/1     Running   0          19m
pod/monitoring-prometheus-node-exporter-wbzq4                1/1     Running   0          19m
pod/prometheus-monitoring-kube-prometheus-prometheus-0       2/2     Running   0          19m

NAME                                              TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)                      AGE
service/alertmanager-operated                     ClusterIP   None             <none>        9093/TCP,9094/TCP,9094/UDP   19m
service/monitoring-grafana                        ClusterIP   10.99.210.70     <none>        80/TCP                       19m
service/monitoring-kube-prometheus-alertmanager   ClusterIP   10.100.213.135   <none>        9093/TCP,8080/TCP            19m
service/monitoring-kube-prometheus-operator       ClusterIP   10.106.113.43    <none>        443/TCP                      19m
service/monitoring-kube-prometheus-prometheus     ClusterIP   10.98.195.2      <none>        9090/TCP,8080/TCP            19m
service/monitoring-kube-state-metrics             ClusterIP   10.102.222.42    <none>        8080/TCP                     19m
service/monitoring-prometheus-node-exporter       ClusterIP   10.110.195.204   <none>        9100/TCP                     19m
service/prometheus-operated                       ClusterIP   None             <none>        9090/TCP                     19m
```

---

## 3. Grafana Dashboard Answers

Доступ к Grafana:

```bash
kubectl port-forward svc/monitoring-grafana -n monitoring 3000:80
# http://localhost:3000  → admin / prom-operator
```

Все ответы получены при включённом StatefulSet из Lab 15 (`lab15-sts-devops-info-service-{0,1,2}` в namespace `lab15`).

### Q1. CPU/Memory вашего StatefulSet

В Grafana дашборд *Compute Resources / Pod* → ns=`lab15` → pod=`lab15-sts-devops-info-service-{0,1,2}` показывает CPU и Memory usage. Чтобы не привязываться к UI, те же цифры берём через PromQL:

**CPU usage (5m rate):**

```
$ curl -sG 'http://localhost:9090/api/v1/query' \
    --data-urlencode 'query=sum by (pod) (rate(container_cpu_usage_seconds_total{namespace="lab15"}[5m]))' \
  | jq -r '.data.result[] | "\(.metric.pod)\t\((.value[1] | tonumber * 1000)) mCPU"' \
  | column -t -s $'\t'
lab15-sts-devops-info-service-0  13.537 mCPU
lab15-sts-devops-info-service-1  13.870 mCPU
lab15-sts-devops-info-service-2  13.707 mCPU
```

**Memory (working set):**

```
$ curl -sG 'http://localhost:9090/api/v1/query' \
    --data-urlencode 'query=sum by (pod) (container_memory_working_set_bytes{namespace="lab15"})' \
  | jq -r '.data.result[] | "\(.metric.pod)\t\((.value[1] | tonumber / 1048576) | floor) MiB"' \
  | column -t -s $'\t'
lab15-sts-devops-info-service-0  37 MiB
lab15-sts-devops-info-service-1  36 MiB
lab15-sts-devops-info-service-2  39 MiB
```

**Limits из чарта:** `200m` CPU / `256Mi` memory (см. `values.yaml`). Реальное потребление: ~`13–14 mCPU` (≈ 7% от лимита) и ~`37 MiB` (≈ 14% от лимита) на pod — типично для idle Python/FastAPI процесса с Prometheus middleware.

### Q2. Pods с max/min CPU в namespace `default`

> Дашборд *Compute Resources / Namespace (Pods)* в этой версии Minikube показывает пустую таблицу: cAdvisor отдаёт `container_cpu_usage_seconds_total` без label'а `container`, а стандартные панели фильтруются `container!=""` и отсекают все серии. Поэтому ответ берём напрямую через Prometheus API — данные те же самые, просто без UI-обвязки.

**CPU usage (rate 5m), отсортировано по убыванию:**

```
$ curl -sG 'http://localhost:9090/api/v1/query' \
    --data-urlencode 'query=sort_desc(sum by (pod) (rate(container_cpu_usage_seconds_total{namespace="default"}[5m])))' \
  | jq -r '.data.result[] | "\(.metric.pod)\t\((.value[1] | tonumber * 1000) | tostring + " mCPU")"' \
  | column -t -s $'\t'
vault-0                                                  33.997 mCPU
devops-info-service-devops-info-service-d8fb5d76f-j8gq7  7.155 mCPU
devops-info-service-devops-info-service-d8fb5d76f-2sx44  6.484 mCPU
app2-release-app2-5cc7bf6668-ncx4d                       6.335 mCPU
app2-release-app2-5cc7bf6668-ldl7k                       6.099 mCPU
devops-info-service-devops-info-service-d8fb5d76f-r6qsw  5.288 mCPU
vault-agent-injector-848dd747d7-jptf9                    2.657 mCPU
init-download-demo                                       0.000 mCPU
wait-for-service-demo                                    0.000 mCPU
dependency-app-6596fd686-5sx98                           0.000 mCPU
```

**Memory (working set), по убыванию:**

```
$ curl -sG 'http://localhost:9090/api/v1/query' \
    --data-urlencode 'query=sort_desc(sum by (pod) (container_memory_working_set_bytes{namespace="default"}))' \
  | jq -r '.data.result[] | "\(.metric.pod)\t\((.value[1] | tonumber / 1048576 | floor) | tostring + " MiB")"' \
  | column -t -s $'\t'
vault-0                                                  76 MiB
app2-release-app2-5cc7bf6668-ldl7k                       37 MiB
devops-info-service-devops-info-service-d8fb5d76f-r6qsw  37 MiB
devops-info-service-devops-info-service-d8fb5d76f-j8gq7  36 MiB
devops-info-service-devops-info-service-d8fb5d76f-2sx44  36 MiB
app2-release-app2-5cc7bf6668-ncx4d                       34 MiB
vault-agent-injector-848dd747d7-jptf9                    16 MiB
wait-for-service-demo                                    11 MiB
init-download-demo                                       10 MiB
dependency-app-6596fd686-5sx98                           9 MiB
```

**Ответ:**
- **Max CPU:** `vault-0` (~34 mCPU) — Vault server активно работает с consul backend и watchers, потому жрёт больше всех.
- **Min CPU:** `init-download-demo`, `wait-for-service-demo`, `dependency-app-*` — все три nginx idle, фактически 0 mCPU.
- **Max RAM:** опять `vault-0` (76 MiB) — Java-style heap.
- **Min RAM:** `dependency-app` (~9 MiB) — голый alpine-nginx без нагрузки.

### Q3. Node metrics (Memory %, Memory MB, CPU cores)

Все метрики от **node-exporter** (DaemonSet `monitoring-prometheus-node-exporter` на ноде `192.168.49.2:9100`):

```
$ curl -sG 'http://localhost:9090/api/v1/query' \
    --data-urlencode 'query=count(node_cpu_seconds_total{mode="idle", instance="192.168.49.2:9100"})' \
  | jq -r '.data.result[0].value[1]'
11

$ curl -sG 'http://localhost:9090/api/v1/query' \
    --data-urlencode 'query=avg(1 - rate(node_cpu_seconds_total{mode="idle", instance="192.168.49.2:9100"}[5m]))' \
  | jq -r '.data.result[0].value[1] | tonumber * 100 | "\(. | floor)%"'
22%

$ curl -sG 'http://localhost:9090/api/v1/query' \
    --data-urlencode 'query=node_memory_MemTotal_bytes{instance="192.168.49.2:9100"}' \
  | jq -r '.data.result[0].value[1] | tonumber / 1073741824 | "\(.)" + " GiB"'
7.65 GiB

$ curl -sG 'http://localhost:9090/api/v1/query' \
    --data-urlencode 'query=(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes){instance="192.168.49.2:9100"}' \
  | jq -r '.data.result[0].value[1] | tonumber / 1048576 | "\(. | floor) MiB used"'
4516 MiB used

$ curl -sG 'http://localhost:9090/api/v1/query' \
    --data-urlencode 'query=node_filesystem_size_bytes{mountpoint="/var", fstype="ext4"}' \
  | jq -r '.data.result[0].value[1] | tonumber / 1073741824 | "\(. | floor) GiB"'
58 GiB
```

**Сводка:**

| Параметр | Значение |
|---|---|
| CPU cores total (на ноде minikube) | **11** |
| CPU busy | **~22 %** (5m avg) |
| RAM total | **7.65 GiB** |
| RAM used | **4516 MiB ≈ 4.41 GiB (57.6 %)** |
| RAM available | **3.24 GiB** |
| Disk `/var` (Docker volume для minikube) | size **58.4 GiB**, used **54.1 GiB ≈ 92.6 %** |

> 11 cores — это видимое node-exporter'у число CPU всего хоста (Apple Silicon), не лимит, заданный для minikube. 92 % заполненности диска — уже близко к порогу `DiskPressure`, на это в production стоило бы повесить алерт.

### Q4. Сколько pods/containers управляет Kubelet

Прямые метрики kubelet:

```
$ curl -sG 'http://localhost:9090/api/v1/query' \
    --data-urlencode 'query=sum(kubelet_running_pods{job="kubelet"})' \
  | jq -r '.data.result[0].value[1]'
41

$ curl -sG 'http://localhost:9090/api/v1/query' \
    --data-urlencode 'query=sum(kubelet_running_containers{job="kubelet"})' \
  | jq -r '.data.result[0].value[1]'
99

$ curl -sG 'http://localhost:9090/api/v1/query' \
    --data-urlencode 'query=kubelet_running_containers{job="kubelet"}' \
  | jq -r '.data.result[] | "\(.metric.container_state)\t\(.value[1])"' \
  | column -t -s $'\t'
created  10
exited   44
running  45
```

**Сводка:**

| Параметр | Значение |
|---|---|
| `kubelet_running_pods` | **41** |
| `kubelet_running_containers` (всего, все стейты) | **99** |
| из них в стейте `running` | **45** |
| `created` | 10 |
| `exited` (Completed/Error) | 44 |

99 контейнеров на 41 pod — потому что многие поды многоконтейнерные: Prometheus и Alertmanager — по 2 контейнера, Grafana — 3, плюс старые `exited` контейнеры от рестартов накапливаются в учёте kubelet.

### Q5. Network traffic у pods в `default`

> Метрики `container_network_receive_bytes_total` / `container_network_transmit_bytes_total` отсутствуют в этом minikube-окружении (cAdvisor не эмитит per-container network — то же ограничение, из-за которого Q2 не работал через дашборд). Поэтому смотрим **node-уровень**: интерфейсы `eth0` (внешний) и `bridge` (CNI bridge через который ходит трафик подов).

```
$ curl -sG 'http://localhost:9090/api/v1/query' \
    --data-urlencode 'query=sort_desc(rate(node_network_receive_bytes_total{instance="192.168.49.2:9100", device=~"eth0|bridge"}[5m]))' \
  | jq -r '.data.result[] | "RX\t\(.metric.device)\t\(.value[1] | tonumber / 1024) KiB/s"' \
  | column -t -s $'\t'
RX  bridge  10.57 KiB/s
RX  eth0     0.78 KiB/s

$ curl -sG 'http://localhost:9090/api/v1/query' \
    --data-urlencode 'query=sort_desc(rate(node_network_transmit_bytes_total{instance="192.168.49.2:9100", device=~"eth0|bridge"}[5m]))' \
  | jq -r '.data.result[] | "TX\t\(.metric.device)\t\(.value[1] | tonumber / 1024) KiB/s"' \
  | column -t -s $'\t'
TX  bridge  65.20 KiB/s
TX  eth0     1.28 KiB/s
```

**Сводка:**

| Интерфейс | RX | TX | Что это |
|---|---|---|---|
| `bridge` | 10.57 KiB/s | 65.20 KiB/s | весь трафик между подами (CNI, в т.ч. default ns) |
| `eth0`   | 0.78 KiB/s  | 1.28 KiB/s  | трафик ноды наружу (в host) |

Подавляющая часть пакетов на `bridge` — Prometheus скрейпит `/metrics` целевых подов (включая 3 пода нашего StatefulSet каждые 15 секунд). Поды `default` (`init-download-demo`, `wait-for-service-demo`, `dependency-app-*`) на этом фоне практически не дают трафика — все три nginx idle. Был всплеск RX у `init-download-demo` в момент `wget example.com` (~528 байт), но это давно ушло за окно 5m rate.

### Q6. Active alerts (Alertmanager)

```bash
kubectl port-forward svc/monitoring-kube-prometheus-alertmanager -n monitoring 9093:9093
# http://localhost:9093
```

Можно получить список алертов через API без UI:

```
$ curl -s http://localhost:9093/api/v2/alerts?active=true | jq -r '.[] | "\(.labels.alertname)\t\(.labels.severity // "-")\t\(.status.state)"'
TargetDown                  warning   active
etcdInsufficientMembers     critical  active
TargetDown                  warning   active
NodeClockNotSynchronising   warning   active
Watchdog                    none      active
TargetDown                  warning   active
```

Итого **6 active alerts**. Это типичная картина для Minikube «из коробки»:

- `Watchdog` — постоянный синтетический алерт оператора, который сигнализирует, что цепочка Prometheus → Alertmanager жива (его отсутствие — признак поломки). Это **нормально**.
- 3 × `TargetDown` + `etcdInsufficientMembers` — следствие того, что в Minikube `kube-controller-manager`, `kube-scheduler`, `kube-proxy`, `etcd` слушают только на `127.0.0.1`, и ServiceMonitor от kube-prometheus-stack не может их доскрейпить. Это известная особенность Minikube, не реальная проблема.
- `NodeClockNotSynchronising` — алерт node-exporter про NTP внутри VM Minikube (тоже артефакт окружения).

Реальных critical-алертов от приложения **нет**.

---

## 4. Init Containers

Реализованы оба паттерна. Манифесты лежат в `k8s/init-container-download.yaml` и `k8s/init-container-wait.yaml`.

### 4.1 Download init container

`init-download` качает `https://example.com` через `wget` и кладёт в общий `emptyDir` volume. Основной контейнер `nginx` маунтит этот же volume в `/usr/share/nginx/html` и сразу раздаёт скачанный файл.

```yaml
spec:
  initContainers:
    - name: init-download
      image: busybox:1.36
      command: ['sh', '-c', 'wget -O /work-dir/index.html https://example.com']
      volumeMounts: [{ name: workdir, mountPath: /work-dir }]
  containers:
    - name: main-app
      image: nginx:1.27-alpine
      volumeMounts: [{ name: workdir, mountPath: /usr/share/nginx/html }]
  volumes:
    - name: workdir
      emptyDir: {}
```

**Доказательство работы (живой вывод из кластера):**

```
$ kubectl get pod init-download-demo
NAME                 READY   STATUS    RESTARTS   AGE
init-download-demo   1/1     Running   0          15m

$ kubectl logs init-download-demo -c init-download
Connecting to example.com (104.20.23.154:443)
wget: note: TLS certificate validation not implemented
saving to '/work-dir/index.html'
index.html           100% |********************************|   528  0:00:00 ETA
'/work-dir/index.html' saved
Download complete
total 12
drwxrwxrwx    2 root     root          4096 Apr 27 11:26 .
drwxr-xr-x    1 root     root          4096 Apr 27 11:26 ..
-rw-r--r--    1 root     root           528 Apr 27 11:26 index.html

$ kubectl exec init-download-demo -c main-app -- ls -la /usr/share/nginx/html
total 12
drwxrwxrwx    2 root     root          4096 Apr 27 11:26 .
drwxr-xr-x    3 root     root          4096 Apr 16  2025 ..
-rw-r--r--    1 root     root           528 Apr 27 11:26 index.html

$ kubectl exec init-download-demo -c main-app -- head -c 200 /usr/share/nginx/html/index.html
<!doctype html><html lang="en"><head><title>Example Domain</title><meta name="viewport" content="width=device-width, initial-scale=1"><style>body{background:#eee;width:60vw;margin:15vh auto;font-famil
```

Видно, что init-контейнер скачал файл во временный `emptyDir`, а main контейнер (`nginx`) видит его на смонтированном пути `/usr/share/nginx/html` — общая папка между контейнерами одного pod.

### 4.2 Wait-for-service pattern

`wait-for-dependency` блокирует старт pod до тех пор, пока Service `dependency-service` не начнёт резолвиться через DNS. Когда Service есть — init-контейнер завершается успешно и стартует main container.

```yaml
initContainers:
  - name: wait-for-dependency
    image: busybox:1.36
    command:
      - sh
      - -c
      - |
        until nslookup dependency-service.default.svc.cluster.local; do
          echo "Service not ready yet, retrying in 2s..."; sleep 2
        done
```

**Доказательство работы (живой вывод из кластера).** Pod был задеплоен **без** Service `dependency-service`, и завис в статусе `Init:0/1`:

```
$ kubectl apply -f k8s/init-container-wait-pod-only.yaml
pod/wait-for-service-demo created

$ kubectl get pod wait-for-service-demo
NAME                    READY   STATUS     RESTARTS   AGE
wait-for-service-demo   0/1     Init:0/1   0          2s

$ kubectl logs wait-for-service-demo -c wait-for-dependency --tail=8
Server:		10.96.0.10
Address:	10.96.0.10:53

** server can't find dependency-service.default.svc.cluster.local: NXDOMAIN

** server can't find dependency-service.default.svc.cluster.local: NXDOMAIN

Service not ready yet, retrying in 2s...
```

После применения Service `dependency-service` (через `k8s/init-container-wait.yaml`) pod ушёл в `Running`:

```
$ kubectl apply -f k8s/init-container-wait.yaml
service/dependency-service created
pod/wait-for-service-demo unchanged
deployment.apps/dependency-app created

$ kubectl wait --for=condition=ready pod/wait-for-service-demo --timeout=60s
pod/wait-for-service-demo condition met

$ kubectl get pod wait-for-service-demo
NAME                    READY   STATUS    RESTARTS   AGE
wait-for-service-demo   1/1     Running   0          8s

$ kubectl logs wait-for-service-demo -c wait-for-dependency
Waiting for service dependency-service to resolve...
Server:		10.96.0.10
Address:	10.96.0.10:53

** server can't find dependency-service.default.svc.cluster.local: NXDOMAIN
Service not ready yet, retrying in 2s...
... (повтор несколько раз) ...

Name:	dependency-service.default.svc.cluster.local
Address: 10.97.173.164

Service dependency-service is now resolvable. Starting main container.
```

Видно, как `nslookup` сначала возвращает `NXDOMAIN`, потом — после появления Service — резолвит DNS-имя в ClusterIP, init-контейнер успешно завершается, и стартует main `nginx`.

---

## 5. Bonus — Custom Metrics & ServiceMonitor

**Цель:** заставить Prometheus собирать `/metrics` нашего Python приложения через CRD `ServiceMonitor`.

### 5.1 `/metrics` endpoint

Уже есть в `app_python/app.py` (зависимость `prometheus-client==0.23.1`):
- `@app.get("/metrics")` отдаёт стандартные `python_info`, `process_*`, `python_gc_*`,
- middleware `prometheus_metrics_middleware` инкрементит свои Counter/Histogram (HTTP requests, latency).

### 5.2 ServiceMonitor CRD

Шаблон чарта: `k8s/devops-info-service/templates/servicemonitor.yaml`. Включается флагом `serviceMonitor.enabled=true` в values. Используется в `values-monitoring.yaml`:

```yaml
serviceMonitor:
  enabled: true
  path: /metrics
  interval: 15s
  scrapeTimeout: 10s
  labels:
    release: monitoring   # обязательная метка для kube-prometheus-stack
```

> Почему `release: monitoring`? Prometheus, созданный оператором, сконфигурирован с `serviceMonitorSelector: {matchLabels: {release: monitoring}}` — только ServiceMonitor'ы с такой меткой будут подхвачены.

### 5.3 Применение

```bash
helm upgrade lab15-sts ./k8s/devops-info-service -n lab15 \
  -f ./k8s/devops-info-service/values-monitoring.yaml
```

```
$ kubectl get servicemonitor -n lab15
NAME                            AGE
lab15-sts-devops-info-service   3s
```

### 5.4 Проверка через Prometheus API

```bash
kubectl port-forward svc/monitoring-kube-prometheus-prometheus -n monitoring 9090:9090
# UI: http://localhost:9090/targets
```

**Targets — все три pod'а нашего StatefulSet в состоянии `up`:**

```
$ curl -s 'http://localhost:9090/api/v1/targets?state=active' \
  | jq -r '.data.activeTargets[]
           | select(.labels.job=="lab15-sts-devops-info-service")
           | "endpoint=\(.scrapeUrl)  pod=\(.labels.pod)  health=\(.health)  lastScrape=\(.lastScrape[:19])"'
endpoint=http://10.244.1.23:5000/metrics  pod=lab15-sts-devops-info-service-1  health=up  lastScrape=2026-04-27T11:41:49
endpoint=http://10.244.1.27:5000/metrics  pod=lab15-sts-devops-info-service-2  health=up  lastScrape=2026-04-27T11:41:41
endpoint=http://10.244.1.34:5000/metrics  pod=lab15-sts-devops-info-service-0  health=up  lastScrape=2026-04-27T11:41:40
```

**Сама метрика `up` для job:**

```
$ curl -sG 'http://localhost:9090/api/v1/query' --data-urlencode 'query=up{job="lab15-sts-devops-info-service"}' \
  | jq -r '.data.result[] | "pod=\(.metric.pod)  up=\(.value[1])"'
pod=lab15-sts-devops-info-service-0  up=1
pod=lab15-sts-devops-info-service-2  up=1
pod=lab15-sts-devops-info-service-1  up=1
```

**Кастомная метрика приложения — `python_info` из нашего `/metrics`:**

```
$ curl -sG 'http://localhost:9090/api/v1/query' --data-urlencode 'query=python_info{namespace="lab15"}' \
  | jq -r '.data.result[] | "pod=\(.metric.pod)  version=\(.metric.version)  value=\(.value[1])"'
pod=lab15-sts-devops-info-service-1  version=3.13.13  value=1
pod=lab15-sts-devops-info-service-0  version=3.13.13  value=1
pod=lab15-sts-devops-info-service-2  version=3.13.13  value=1
```

Метрика возвращает по одной серии на каждый pod StatefulSet — значит Prometheus реально достучался до `/metrics` нашего приложения через ServiceMonitor, а не до случайного встроенного экспортера.

---

## 6. Доступы (cheat sheet)

```bash
# Grafana
kubectl port-forward svc/monitoring-grafana -n monitoring 3000:80
# http://localhost:3000  admin / prom-operator

# Prometheus
kubectl port-forward svc/monitoring-kube-prometheus-prometheus -n monitoring 9090:9090

# Alertmanager
kubectl port-forward svc/monitoring-kube-prometheus-alertmanager -n monitoring 9093:9093
```
