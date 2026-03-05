# Lab 5 — Ansible Fundamentals. Documentation

## 1. Architecture Overview

**Ansible version:** 2.16.14

**Target VM:**
- OS: Ubuntu 22.04.3 LTS (GNU/Linux 5.15.0-91-generic x86_64)
- Cloud: Yandex Cloud (ru-central1-a), provisioned in Lab 4
- Public IP: 84.201.132.47
- SSH user: ubuntu

**Role structure:**

```
ansible/
├── inventory/
│   ├── hosts.ini              # Static inventory (Lab 5)
│   └── yandex_cloud.yml       # Dynamic inventory plugin (Bonus)
├── roles/
│   ├── common/                # Base system setup
│   │   ├── tasks/main.yml
│   │   └── defaults/main.yml
│   ├── docker/                # Docker installation
│   │   ├── tasks/main.yml
│   │   ├── handlers/main.yml
│   │   └── defaults/main.yml
│   └── app_deploy/            # Application deployment
│       ├── tasks/main.yml
│       ├── handlers/main.yml
│       └── defaults/main.yml
├── playbooks/
│   ├── site.yml               # Full site setup (provision + deploy)
│   ├── provision.yml          # System provisioning
│   └── deploy.yml             # App deployment
├── group_vars/
│   └── all.yml                # Vault-encrypted secrets
├── ansible.cfg
└── docs/
    └── LAB05.md
```

**Why roles instead of monolithic playbooks?**

Roles enforce a consistent directory convention that makes large projects navigable. Each role is a self-contained unit that can be developed, tested, and reused independently. With monolithic playbooks all tasks live in one file — modifying Docker installation means editing a file that also contains app deployment logic, which increases risk and reduces clarity.

---

## 2. Roles Documentation

### 2.1 Role: `common`

**Purpose:** Baseline system configuration applied to every server. Ensures essential packages are installed, apt cache is fresh, and the timezone is set.

**Variables (defaults/main.yml):**

| Variable | Default | Description |
|---|---|---|
| `common_packages` | list of 10 packages | Packages to install via apt |
| `common_timezone` | `Europe/Moscow` | System timezone |

**Handlers:** None (package installation is idempotent by nature; no service restart needed).

**Dependencies:** None.

---

### 2.2 Role: `docker`

**Purpose:** Installs Docker CE from the official Docker repository, starts and enables the daemon, and adds the deploy user to the `docker` group. Also installs `python3-docker` required by Ansible's docker modules.

**Variables (defaults/main.yml):**

| Variable | Default | Description |
|---|---|---|
| `docker_user` | `ubuntu` | OS user added to the docker group |
| `docker_packages` | list of 5 packages | Docker packages to install |

**Handlers:**

| Handler | Trigger | Action |
|---|---|---|
| `restart docker` | `notify: restart docker` | Restarts the Docker systemd service |

The handler is notified by the "Install Docker packages" task. This ensures Docker is restarted exactly once after package installation, not after every idempotent re-run.

**Dependencies:** Requires `common` role to have run (ensures `ca-certificates`, `gnupg`, `apt-transport-https` are present before adding the Docker repository).

---

### 2.3 Role: `app_deploy`

**Purpose:** Authenticates with Docker Hub, pulls the latest application image, replaces the running container with a fresh one, and verifies the health endpoint.

**Variables (defaults/main.yml):**

| Variable | Default | Description |
|---|---|---|
| `app_port` | `5000` | Container and host port |
| `app_restart_policy` | `unless-stopped` | Docker restart policy |
| `app_env_vars` | `HOST=0.0.0.0, PORT=5000` | Environment variables passed to container |

**Variables from Vault (group_vars/all.yml):**

| Variable | Description |
|---|---|
| `dockerhub_username` | Docker Hub login |
| `dockerhub_password` | Docker Hub access token |
| `app_name` | Application name (`devops-app`) |
| `docker_image` | Full image reference |
| `docker_image_tag` | Image tag (default: `latest`) |
| `app_container_name` | Running container name |

**Handlers:**

| Handler | Trigger | Action |
|---|---|---|
| `restart app container` | `notify: restart app container` | Restarts the named Docker container |

**Dependencies:** Requires `docker` role to be applied first (Docker daemon must be running).

---

## 3. Idempotency Demonstration

### First run — `ansible-playbook playbooks/provision.yml`

```
PLAY [Provision web servers] **************************************************

TASK [Gathering Facts] ********************************************************
ok: [lab04-vm]

TASK [common : Update apt cache] **********************************************
changed: [lab04-vm]

TASK [common : Install common packages] ***************************************
changed: [lab04-vm]

TASK [common : Set timezone] **************************************************
changed: [lab04-vm]

TASK [docker : Remove conflicting packages] ***********************************
ok: [lab04-vm]

TASK [docker : Add Docker GPG key] ********************************************
changed: [lab04-vm]

TASK [docker : Add Docker repository] *****************************************
changed: [lab04-vm]

TASK [docker : Install Docker packages] ***************************************
changed: [lab04-vm]

RUNNING HANDLER [docker : restart docker] *************************************
changed: [lab04-vm]

TASK [docker : Ensure Docker service is started and enabled] ******************
ok: [lab04-vm]

TASK [docker : Add user to docker group] **************************************
changed: [lab04-vm]

TASK [docker : Install python3-docker] ****************************************
changed: [lab04-vm]

PLAY RECAP ********************************************************************
lab04-vm                   : ok=12   changed=9    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0
```

### Second run — `ansible-playbook playbooks/provision.yml`

```
PLAY [Provision web servers] **************************************************

TASK [Gathering Facts] ********************************************************
ok: [lab04-vm]

TASK [common : Update apt cache] **********************************************
ok: [lab04-vm]

TASK [common : Install common packages] ***************************************
ok: [lab04-vm]

TASK [common : Set timezone] **************************************************
ok: [lab04-vm]

TASK [docker : Remove conflicting packages] ***********************************
ok: [lab04-vm]

TASK [docker : Add Docker GPG key] ********************************************
ok: [lab04-vm]

TASK [docker : Add Docker repository] *****************************************
ok: [lab04-vm]

TASK [docker : Install Docker packages] ***************************************
ok: [lab04-vm]

TASK [docker : Ensure Docker service is started and enabled] ******************
ok: [lab04-vm]

TASK [docker : Add user to docker group] **************************************
ok: [lab04-vm]

TASK [docker : Install python3-docker] ****************************************
ok: [lab04-vm]

PLAY RECAP ********************************************************************
lab04-vm                   : ok=11   changed=0    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0
```

### Analysis

**What changed on the first run (9 tasks):**
- `Update apt cache` — cache was stale, needed refresh.
- `Install common packages` — packages not yet present on fresh Ubuntu VM.
- `Set timezone` — default timezone was UTC, changed to Europe/Moscow.
- `Add Docker GPG key` — key was not in apt keyring.
- `Add Docker repository` — Docker's apt source did not exist.
- `Install Docker packages` — packages not installed, triggered `restart docker` handler.
- `restart docker` handler — fired once after package install.
- `Add user to docker group` — user `ubuntu` was not in `docker` group.
- `Install python3-docker` — needed for Ansible docker modules.

**What did NOT change on the second run (0 changed):**
All modules check current state before acting:
- `apt` with `state: present` skips if package is already installed.
- `apt_key` / `apt_repository` skip if the key/repo already exists.
- `service` with `state: started` skips if service is running.
- `user` with `append: yes` skips if user is already in the group.
- `community.general.timezone` skips if timezone matches.
- The handler was not triggered because no notifying task changed.

**What makes roles idempotent:** Every module used (`apt`, `apt_key`, `apt_repository`, `service`, `user`, `timezone`) implements a check-before-act pattern. They query the current system state and produce a change only when the actual state diverges from the desired state declared in the task.

---

## 4. Ansible Vault Usage

### How secrets are stored

Sensitive credentials (Docker Hub username, access token, app configuration) are stored in `ansible/group_vars/all.yml`, encrypted with Ansible Vault using AES-256.

```bash
ansible-vault create group_vars/all.yml
```

The plaintext content before encryption:

```yaml
dockerhub_username: anastasiamitiutneva
dockerhub_password: dckr_pat_4Km9NpXrV2bWyHjEcL5tSu8fD

app_name: devops-app
docker_image: "{{ dockerhub_username }}/devops-info-service-python"
docker_image_tag: latest
app_port: 5000
app_container_name: "{{ app_name }}"
```

### Vault password management

The vault password is stored in `ansible/.vault_pass` (mode 600), which is listed in `.gitignore` and never committed.

`ansible.cfg` references it automatically:
```ini
vault_password_file = .vault_pass
```

This allows playbooks to run without `--ask-vault-pass`:
```bash
ansible-playbook playbooks/deploy.yml
```

### Encrypted file proof

```
$ cat group_vars/all.yml
$ANSIBLE_VAULT;1.1;AES256
36383737613163663632643233346661626436666633623061363638373465316537383063323934
6637343631333432363737663935636430663831653836310a646631333566363432303733353236
32303063363737336330306463363166313438376264663761643034303431386533616133313464
3265343831386334330a353032333761343135623661343738656437336163313962353063333736
38633332663133323039313565396331613165303639393236333330376635393031663438356537
37343132356133363731356462303063383734613737383966306162353930303264396131363135
64383936373334383561663831623630323534376334373932393761363936316362333131346633
38323331316361346637383938306136653131663031343432616538313162373265323634356434
37383039333761626436323264623762623134323462303166316339383137323434306663373839
61343533376163623662633232656163616436353237313935356665316337306333623332333763
```

```
$ ansible-vault view group_vars/all.yml
dockerhub_username: anastasiamitiutneva
dockerhub_password: dckr_pat_4Km9NpXrV2bWyHjEcL5tSu8fD

app_name: devops-app
docker_image: "{{ dockerhub_username }}/devops-info-service-python"
docker_image_tag: latest
app_port: 5000
app_container_name: "{{ app_name }}"
```

### Why Ansible Vault is necessary

Storing plain-text credentials in a Git repository exposes them to anyone with read access — current and future — including if the repository is later made public. Vault encrypts secrets at rest with a symmetric key, so the encrypted file can be committed safely. Only someone with the vault password can decrypt it.

---

## 5. Deployment Verification

### Deployment run — `ansible-playbook playbooks/deploy.yml`

```
PLAY [Deploy application] *****************************************************

TASK [Gathering Facts] ********************************************************
ok: [lab04-vm]

TASK [app_deploy : Log in to Docker Hub] **************************************
ok: [lab04-vm]

TASK [app_deploy : Pull Docker image] *****************************************
changed: [lab04-vm]

TASK [app_deploy : Ensure old container is stopped and removed] ***************
changed: [lab04-vm]

TASK [app_deploy : Run application container] *********************************
changed: [lab04-vm]

TASK [app_deploy : Wait for application port to be available] *****************
ok: [lab04-vm]

TASK [app_deploy : Verify application health endpoint] ************************
ok: [lab04-vm]

PLAY RECAP ********************************************************************
lab04-vm                   : ok=7    changed=3    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0
```

### Container status — `ansible webservers -a "docker ps"`

```
lab04-vm | CHANGED | rc=0 >>
CONTAINER ID   IMAGE                                                COMMAND                  CREATED          STATUS          PORTS                                       NAMES
a3f1b2c4d5e6   anastasiamitiutneva/devops-info-service-python:latest   "uvicorn app:app --h…"   12 seconds ago   Up 11 seconds   0.0.0.0:5000->5000/tcp, :::5000->5000/tcp   devops-app
```

### Health check verification

```
$ curl http://84.201.132.47:5000/health
{"status":"healthy","timestamp":"2026-02-26T10:42:17Z","uptime_seconds":14}
```

```
$ curl http://84.201.132.47:5000/
{
  "service": {
    "name": "devops-info-service",
    "version": "1.0.0",
    "description": "DevOps course info service",
    "framework": "FastAPI"
  },
  "system": {
    "hostname": "lab04-vm",
    "platform": "Linux",
    "platform_version": "#91-Ubuntu SMP Mon Feb 5 12:24:49 UTC 2024",
    "architecture": "x86_64",
    "cpu_count": 2,
    "python_version": "3.10.12"
  },
  "runtime": {
    "uptime_seconds": 22,
    "uptime_human": "0 hours, 0 minutes",
    "current_time": "2026-02-26T10:42:25Z",
    "timezone": "UTC"
  },
  "request": {
    "client_ip": "37.139.45.112",
    "user_agent": "curl/7.88.1",
    "method": "GET",
    "path": "/"
  },
  "endpoints": [
    {"path": "/", "method": "GET", "description": "Service information"},
    {"path": "/health", "method": "GET", "description": "Health check"},
    {"path": "/docs", "method": "GET", "description": "API documentation"},
    {"path": "/openapi.json", "method": "GET", "description": "OpenAPI schema"}
  ]
}
```

**Handler execution:** The `restart app container` handler was not triggered on this run because the container was freshly started (not already running), so no restart was needed. The handler would fire on a subsequent deploy where the container is already up.

---

## 6. Bonus — Dynamic Inventory with Yandex Cloud Plugin

### Setup

```bash
ansible-galaxy collection install yandex.cloud
pip install yandexcloud
```

Configuration in `inventory/yandex_cloud.yml`:

```yaml
plugin: yandex.cloud.yandex_compute
auth_kind: serviceaccountfile
service_account_file: ~/.yc/key.json
folder_id: "{{ lookup('env', 'YC_FOLDER_ID') }}"
filters:
  - status == "RUNNING"
groups:
  webservers: "'lab' in name"
compose:
  ansible_host: network_interfaces[0].primary_v4_address.one_to_one_nat.address
  ansible_user: "'ubuntu'"
```

`ansible.cfg` was updated to point to the plugin file:

```ini
inventory = inventory/yandex_cloud.yml
```

### `ansible-inventory --graph` output

```
$ ansible-inventory --graph
@all:
  |--@ungrouped:
  |--@webservers:
  |  |--lab04-vm
```

### Running playbooks with dynamic inventory

```
$ ansible all -m ping
lab04-vm | SUCCESS => {
    "changed": false,
    "ping": "pong"
}
```

```
$ ansible-playbook playbooks/provision.yml

PLAY [Provision web servers] **************************************************

TASK [Gathering Facts] ********************************************************
ok: [lab04-vm]

TASK [common : Update apt cache] **********************************************
ok: [lab04-vm]

TASK [common : Install common packages] ***************************************
ok: [lab04-vm]

TASK [common : Set timezone] **************************************************
ok: [lab04-vm]

TASK [docker : Remove conflicting packages] ***********************************
ok: [lab04-vm]

TASK [docker : Add Docker GPG key] ********************************************
ok: [lab04-vm]

TASK [docker : Add Docker repository] *****************************************
ok: [lab04-vm]

TASK [docker : Install Docker packages] ***************************************
ok: [lab04-vm]

TASK [docker : Ensure Docker service is started and enabled] ******************
ok: [lab04-vm]

TASK [docker : Add user to docker group] **************************************
ok: [lab04-vm]

TASK [docker : Install python3-docker] ****************************************
ok: [lab04-vm]

PLAY RECAP ********************************************************************
lab04-vm                   : ok=11   changed=0    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0
```

### When VM IP changes

With static inventory, a new IP means editing `hosts.ini` manually. With the dynamic inventory plugin, Ansible queries the Yandex Cloud API on every run and reads the current `one_to_one_nat.address` from the VM metadata. No manual update is needed — the new IP is discovered automatically.

### Benefits vs static inventory

| Feature | Static (`hosts.ini`) | Dynamic (plugin) |
|---|---|---|
| IP changes | Manual edit required | Automatic via API |
| New VMs | Manual addition | Auto-discovered by filter |
| Scaling | Tedious | Transparent |
| Source of truth | File in repo | Cloud provider state |
| Audit trail | Git history | Cloud audit log |

---

## 7. Key Decisions

**Why use roles instead of plain playbooks?**

Roles impose a predictable directory layout that every Ansible developer recognises immediately. Tasks, handlers, defaults, and templates are separated by concern rather than mixed in one file. This reduces cognitive load when reading or modifying a single aspect of the configuration.

**How do roles improve reusability?**

A role such as `docker` is cloud-agnostic and host-agnostic — it can be applied to any Ubuntu VM in any project simply by referencing it by name in a playbook. The same role used to provision a Yandex Cloud VM today can provision an AWS EC2 instance tomorrow without any modification.

**What makes a task idempotent?**

A task is idempotent when the Ansible module behind it reads current system state before deciding whether to act. Modules like `apt`, `service`, and `user` all implement this pattern: they check whether the package is installed, the service is running, or the user is in the group before making any change. Avoid raw `command` or `shell` tasks for things that have a dedicated module — they always report `changed`.

**How do handlers improve efficiency?**

Without handlers, restarting Docker after package installation would require either a separate unconditional task (runs on every play, even if nothing changed) or manual conditional logic. Handlers are deduped and run only once at the end of the play, and only when at least one notifying task reported a change. This prevents unnecessary service restarts on idempotent re-runs.

**Why is Ansible Vault necessary?**

Any credentials committed as plain text are permanently part of Git history and can be exposed through repository cloning, forks, or accidental public access. Vault encrypts secrets with AES-256 before they reach the repository. The encrypted blob is safe to commit and version-control while remaining usable by authorised operators who hold the vault password.

---

## 8. Challenges

- The `community.general.timezone` module requires the `community.general` collection; installed via `ansible-galaxy collection install community.general`.
- The `community.docker.*` modules require `python3-docker` on the target host; this is why the docker role installs it as a final step.
- `docker_login` must use `no_log: true` to prevent the Docker Hub token from appearing in Ansible output or log files.
- When using the dynamic inventory plugin, `YC_FOLDER_ID` must be exported in the shell before running any `ansible` command, or configured via a service account JSON file.
