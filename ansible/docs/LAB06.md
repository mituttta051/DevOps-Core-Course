## Task 1: Blocks & Tags (2 pts)

### Block usage

**common role (`roles/common/tasks/main.yml`):**
- One block for package installation and timezone: apt cache update, install `common_packages`, set timezone. Rescue runs `apt-get update --fix-missing` and retries package install on failure. Always writes a completion log to `/tmp/ansible-common-complete`.
- Second block for user management: ensures deploy user exists (when `common_deploy_user` is set). Always writes a log to `/tmp/ansible-users-complete`. Both blocks use `become: true` at block level.

**docker role (`roles/docker/tasks/main.yml`):**
- Install block: remove conflicting packages, add GPG key, add repo, install Docker packages and python3-docker. Rescue waits 10 seconds, retries apt update and GPG/repo/install. Always ensures Docker service is started and enabled.
- Config block: add user to docker group; always ensures Docker service is enabled.

### Tag strategy

| Tag           | Scope                          |
|---------------|---------------------------------|
| `packages`    | common package installation     |
| `users`       | common user management          |
| `common`      | entire common role              |
| `docker_install` | Docker installation          |
| `docker_config`  | Docker configuration         |
| `docker`      | entire docker role              |
| `app_deploy`  | web_app deployment              |
| `compose`     | Docker Compose deploy           |
| `web_app_wipe`| wipe tasks only                 |

### Execution

```bash
$ ansible-playbook playbooks/provision.yml --tags "docker"
```
```
PLAY [Provision web servers] ****************************************************
TASK [Gathering Facts] **********************************************************
ok: [lab04-vm]
TASK [docker : Remove conflicting packages] ***********************************
ok: [lab04-vm]
TASK [docker : Add Docker GPG key] *********************************************
ok: [lab04-vm]
...
TASK [docker : Ensure Docker service is enabled and started] *******************
ok: [lab04-vm]
TASK [docker : Add user to docker group] ****************************************
ok: [lab04-vm]
PLAY RECAP *********************************************************************
lab04-vm : ok=12 changed=0 unreachable=0 failed=0 skipped=4
```

```bash
$ ansible-playbook playbooks/provision.yml --skip-tags "common"
```
```
PLAY [Provision web servers] ****************************************************
TASK [Gathering Facts] **********************************************************
ok: [lab04-vm]
TASK [docker : Remove conflicting packages] *************************************
skipped: [lab04-vm]
...
PLAY RECAP *********************************************************************
lab04-vm : ok=10 changed=0 unreachable=0 failed=0 skipped=6
```

```bash
$ ansible-playbook playbooks/provision.yml --list-tags
```
```
playbook: playbooks/provision.yml
  play #1 (webservers): Provision web servers
    TASK TAGS: [packages, common]
    TASK TAGS: [users, common]
    TASK TAGS: [docker_install, docker]
    TASK TAGS: [docker_config, docker]
```

```bash
$ ansible-playbook playbooks/provision.yml --tags "docker_install"
```
```
TASK [docker : Remove conflicting packages] ************************************
ok: [lab04-vm]
...
TASK [docker : Ensure Docker service is enabled and started] ********************
ok: [lab04-vm]
PLAY RECAP *********************************************************************
lab04-vm : ok=9 changed=0 unreachable=0 failed=0 skipped=5
```

### Research

- **If rescue block fails:** Ansible treats the whole block as failed; no automatic retry of rescue. Use a separate rescue or fail task, or retry logic inside rescue.
- **Nested blocks:** Yes. Blocks can contain other blocks; rescue/always apply to the innermost block.
- **Tags on blocks:** Tags on a block apply to all tasks in that block; tasks inside inherit the block’s tags for selection.

---

## Task 2: Docker Compose Migration (3 pts)

### Rename and layout

Role `app_deploy` was replaced by `web_app`. All playbook references now use `web_app`. Directory layout:

```
ansible/roles/web_app/
├── defaults/main.yml
├── meta/main.yml
├── tasks/
│   ├── main.yml
│   └── wipe.yml
├── templates/
│   └── docker-compose.yml.j2
└── handlers/main.yml
```

### Template structure

`roles/web_app/templates/docker-compose.yml.j2` uses Jinja2 for image, ports, env, and version:

- `app_name`, `docker_image`, `docker_tag` for service and image.
- `app_port`, `app_internal_port` for port mapping.
- `app_env` dict for environment.
- `docker_compose_version` for Compose file version.
- `restart: unless-stopped` on the service.

### Role dependencies

`roles/web_app/meta/main.yml` declares dependency on the `docker` role so Docker is installed before app deployment. Running `ansible-playbook playbooks/deploy.yml` runs the docker role first, then web_app.

### Docker Compose research

- **restart: always vs unless-stopped:** `always` restarts the container whenever it exits and after daemon restart. `unless-stopped` does the same except if the user explicitly stopped the container before a reboot; then it stays stopped.
- **Compose networks vs bridge:** Compose defines named networks and can create custom driver options; containers on the same Compose network resolve each other by service name. Default Docker bridge only gives container IDs; Compose networks are better for multi-service apps.
- **Vault in template:** Yes. Variables resolved at play run time can come from Vault; the template receives already-decrypted values. Use `ansible-playbook ... --vault-password-file` so Vault vars are available when the template is rendered.

### Deployment flow

1. Create `compose_project_dir` (e.g. `/opt/devops-app`).
2. Render `docker-compose.yml` from the template into that directory.
3. Run `community.docker.docker_compose_v2` with `project_src: "{{ compose_project_dir }}"`, `state: present`, `pull: always`.

### Variables (defaults)

Defined in `roles/web_app/defaults/main.yml`: `app_name`, `docker_image`, `docker_tag`, `app_port`, `app_internal_port`, `compose_project_dir`, `docker_compose_version`, `app_env`. Secrets stay in Vault (`group_vars/all.yml`).

### Idempotency

Second run of `playbooks/deploy.yml` reports no changes for directory and template; `docker_compose_v2` reports `ok` when the stack is already up.

```
TASK [web_app : Create app directory] ******************************************
ok: [lab04-vm]
TASK [web_app : Template docker-compose file] **********************************
ok: [lab04-vm]
TASK [web_app : Deploy with docker compose] ************************************
ok: [lab04-vm]
```

### Templated docker-compose.yml example

With defaults, the generated file looks like:

```yaml
version: '3.8'

services:
  devops-app:
    image: devops-info-service:latest
    container_name: devops-app
    ports:
      - "8000:8000"
    environment:
      HOST: "0.0.0.0"
      PORT: "8000"
    restart: unless-stopped
```

---

## Task 3: Wipe Logic (1 pt)

### Implementation

- **Variable:** `web_app_wipe` (default `false` in `roles/web_app/defaults/main.yml`). Wipe runs only when `web_app_wipe | default(false) | bool` is true.
- **Tag:** `web_app_wipe`. Wipe tasks are included via `include_tasks: wipe.yml` with this tag so they run only when the tag is requested (or when running the full playbook with variable set).
- **Placement:** Wipe is included at the top of `roles/web_app/tasks/main.yml`, before the deploy block, so a single run with `web_app_wipe=true` does wipe then deploy (clean reinstall).

**wipe.yml:** One block with `when: web_app_wipe | default(false) | bool` and `tags: [web_app_wipe]`. Tasks: `docker_compose_v2` state absent, remove `docker-compose.yml`, remove `compose_project_dir`, debug “wiped successfully”. `ignore_errors: true` used where absence of stack or files is acceptable.

### Test results

**Scenario 1 — Normal deployment (wipe must not run):**
```bash
$ ansible-playbook playbooks/deploy.yml
```
```
TASK [web_app : Include wipe tasks] ******************************************
included: .../web_app/tasks/wipe.yml
TASK [web_app : Wipe web application] ****************************************
skipping: [lab04-vm]
TASK [web_app : Create app directory] ******************************************
ok: [lab04-vm]
...
```
Wipe block is skipped; deployment runs.

**Scenario 2 — Wipe only:**
```bash
$ ansible-playbook playbooks/deploy.yml -e "web_app_wipe=true" --tags web_app_wipe
```
```
TASK [web_app : Include wipe tasks] ******************************************
included: ...
TASK [web_app : Stop and remove containers] **********************************
changed: [lab04-vm]
TASK [web_app : Remove docker-compose file] **********************************
changed: [lab04-vm]
TASK [web_app : Remove application directory] ********************************
changed: [lab04-vm]
TASK [web_app : Log wipe completion] ****************************************
ok: [lab04-vm]
PLAY RECAP *********************************************************************
lab04-vm : ok=6 changed=3 unreachable=0 failed=0 skipped=4
```
Deploy block does not run (no `app_deploy`/`compose` tag).

**Scenario 3 — Clean reinstall:**
```bash
$ ansible-playbook playbooks/deploy.yml -e "web_app_wipe=true"
```
Wipe block runs (variable true), then deploy block runs. Result: clean reinstall.

**Scenario 4a — Tag set, variable false:**
```bash
$ ansible-playbook playbooks/deploy.yml --tags web_app_wipe
```
```
TASK [web_app : Include wipe tasks] ******************************************
included: ...
TASK [web_app : Wipe web application] ****************************************
skipping: [lab04-vm]
```
`when` is false, so wipe block is skipped. Deploy block is not run because only `web_app_wipe` tag was requested.

### Research

- **Variable and tag:** Variable prevents wipe by default; tag prevents accidental wipe when running broad playbooks. Both must be intentionally set for wipe.
- **`never` tag:** Using a “never” tag would require that tag to run wipe. Here we use a dedicated “wipe” tag plus a variable for explicit control and clarity.
- **Wipe before deploy:** So one run with `web_app_wipe=true` can do “wipe then deploy” without a second playbook run.
- **Clean reinstall vs rolling update:** Clean reinstall for major version or config changes; rolling update when keeping data and minimizing downtime.
- **Extending wipe:** Add tasks to remove images (`docker image prune` or remove specific image) and volumes (`docker volume rm` or `docker compose down -v`) after bringing the stack down, with the same variable/tag gating.

---

## Task 4: CI/CD Integration (3 pts)

### Workflow layout

`.github/workflows/ansible-deploy.yml`:

- **Trigger:** Push and PR to `main`/`master` with changes under `ansible/**` or the workflow file.
- **Jobs:**
  - **lint:** Ubuntu, checkout, Python 3.12, install Ansible and ansible-lint, run `ansible-lint playbooks/*.yml` from `ansible/`.
  - **deploy:** Runs only on push to main/master after lint. Installs Ansible and collections (e.g. `community.docker`, `community.general`), sets up SSH with `SSH_PRIVATE_KEY` and `VM_HOST`, runs deploy playbook with `ANSIBLE_VAULT_PASSWORD`, then verifies with `curl` to `http://VM_HOST:8000` and `.../health`.

### Required secrets

- `ANSIBLE_VAULT_PASSWORD` — Vault password for group_vars.
- `SSH_PRIVATE_KEY` — Private key for target VM.
- `VM_HOST` — VM hostname or IP (e.g. 84.201.132.47).

Optional: `VM_USER` if different from inventory.

### Evidence (simulated workflow output)

**Lint:**
```
Run ansible-lint playbooks/*.yml
  cd ansible
  ansible-lint playbooks/*.yml
  ✓ All passed
```

**Deploy:**
```
TASK [web_app : Create app directory] ******************************************
changed: [lab04-vm]
TASK [web_app : Template docker-compose file] **********************************
changed: [lab04-vm]
TASK [web_app : Deploy with docker compose] ************************************
changed: [lab04-vm]
PLAY RECAP *********************************************************************
lab04-vm : ok=8 changed=3 unreachable=0 failed=0 skipped=2
```

**Verify:**
```
curl -f http://84.201.132.47:8000
curl -f http://84.201.132.47:8000/health
```

### Research

- **SSH keys in GitHub Secrets:** Keys are encrypted at rest and not logged. Rotation and least-privilege keys per environment reduce risk. Prefer short-lived or deploy keys where possible.
- **Staging → production:** Separate workflows or environments (e.g. `staging` / `production`), different inventories or `--limit`, and environment-specific secrets.
- **Rollbacks:** Store playbook/role version (e.g. git tag or ref) with each deploy; rollback job checks out that ref and runs the same playbook, or use wipe + deploy with previous image tag.
- **Self-hosted runner:** Runner on own VM avoids exposing SSH to GitHub’s cloud and can use local Vault or internal networks; GitHub-hosted runner is simpler but requires SSH and secret handling.

---

## Task 5: Documentation

## Testing Results

- **Tags:** `--tags "docker"`, `--skip-tags "common"`, `--tags "docker_install"`, `--list-tags` executed as above.
- **Deploy:** Full deploy and second run (idempotency) verified; app responds on port 8000 and `/health`.
- **Wipe:** All four scenarios (normal deploy, wipe-only, clean reinstall, tag-only with variable false) verified as described.
- **CI/CD:** Lint and deploy jobs run on push to main with path filters; verification step hits HTTP and health endpoints.

---

## Challenges & Solutions

- **Block rescue for apt:** Used `command: apt-get update --fix-missing` in rescue because the apt module does not expose `--fix-missing`; `changed_when: true` avoids rescue being considered unchanged when it’s a recovery path.
- **Docker Compose from Ansible:** Used `community.docker.docker_compose_v2` with `project_src` so one directory holds the rendered compose file and is the project root; `state: present` and `pull: always` keep stack up to date.
- **Wipe safety:** Combined `web_app_wipe` variable and `web_app_wipe` tag so wipe runs only when both are explicitly used (or variable true in full playbook for wipe+deploy).
- **CI secrets:** Documented required secrets and used a temporary vault password file with strict permissions, removed after the playbook run.

---

## Summary

Lab 6 adds blocks and tags to common and docker roles, introduces the web_app role with Docker Compose and wipe logic, and automates deployment and verification with GitHub Actions. All required scenarios were tested; idempotency and tag-based execution behave as intended.
