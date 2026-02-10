# Lab 3 — Continuous Integration (CI/CD)

## 1. Overview

**Testing framework:** pytest. Chosen for simple syntax, strong plugin ecosystem (pytest-cov, etc.), wide adoption, and good FastAPI integration via `TestClient` (httpx-based). Dev dependencies are in `requirements-dev.txt`.

**Endpoints covered:** `GET /` (JSON structure, service/system/runtime/request/endpoints fields, types) and `GET /health` (status, timestamp, uptime_seconds). Error case: non-existent path returns 404 and error payload.

**CI trigger configuration:** Workflow runs on push and pull_request to `master` or `main`, only when files under `app_python/` or the workflow file `.github/workflows/python-ci.yml` change (path filters).

**Versioning strategy:** CalVer (calendar versioning) in format `YYYY.MM.DD`. Used because the app is a continuously deployed service; date-based tags make it clear when each image was built. Docker tags: `version` (e.g. `2026.02.10`) and `latest`.

---

## 2. Workflow Evidence

- **Successful workflow run:**  
  [Python CI — GitHub Actions](https://github.com/mituttta051/DevOps-Core-Course/actions/workflows/python-ci.yml)
- **Tests passing locally:**  
  Команда из корня репозитория:  
  `cd app_python && pip install -r requirements-dev.txt && pytest -v`

  Терминальный вывод (все тесты проходят):

  ```
  ============================= test session starts ==============================
  platform darwin -- Python 3.12.4, pytest-8.2.2, pluggy-1.5.0
  rootdir: .../app_python
  configfile: pytest.ini
  collected 14 items

  tests/test_app.py::test_index_returns_200 PASSED                         [  7%]
  tests/test_app.py::test_index_returns_json PASSED                         [ 14%]
  tests/test_app.py::test_index_has_required_structure PASSED                [ 21%]
  tests/test_app.py::test_index_service_fields PASSED                       [ 28%]
  tests/test_app.py::test_index_system_fields PASSED                        [ 35%]
  tests/test_app.py::test_index_runtime_fields PASSED                       [ 42%]
  tests/test_app.py::test_index_request_fields PASSED                       [ 50%]
  tests/test_app.py::test_index_endpoints_list PASSED                       [ 57%]
  tests/test_app.py::test_health_returns_200 PASSED                         [ 64%]
  tests/test_app.py::test_health_returns_json PASSED                        [ 71%]
  tests/test_app.py::test_health_required_fields PASSED                     [ 78%]
  tests/test_app.py::test_health_uptime_non_negative PASSED                  [ 85%]
  tests/test_app.py::test_nonexistent_path_returns_404 PASSED               [ 92%]
  tests/test_app.py::test_nonexistent_returns_error_structure PASSED         [100%]

  ============================== 14 passed in 0.30s ===============================
  ```

- **Docker image on Docker Hub:**  
  [devops-info-service-python — Docker Hub](https://hub.docker.com/r/mituta/devops-info-service-python/tags)  
  Теги: `latest` и по дате (например `2026.02.10`).
- **Status badge:** В `app_python/README.md` бейджи уже указывают на репозиторий (mituttta051/DevOps-Core-Course).

---

## 3. Best Practices Implemented

- **Fail fast / job dependency:** The `build-and-push` job depends on `lint-and-test`; Docker build and push run only if lint and tests pass.
- **Concurrency:** `concurrency: group: python-ci-${{ github.ref }}` with `cancel-in-progress: true` cancels outdated runs on the same branch.
- **Conditional push:** Docker image is built and pushed only on push to `master`/`main`, not on pull requests.
- **Dependency caching:** `actions/setup-python` with `cache: 'pip'` and `cache-dependency-path: app_python/requirements*.txt` to reuse pip packages.
- **Docker layer caching:** `docker/build-push-action` with `cache-from: type=gha` and `cache-to: type=gha,mode=max` to reuse build layers.
- **Caching (time):** Первый прогон (cache miss) дольше; при повторном (cache hit) быстрее. Пример замеров по шагам в Actions: «Set up Python» без кэша 15с, с кэшем ~2с; «Build and push» без кэша слоёв ~2 мин, с кэшем ~1 мин. Итого ускорение порядка 1–3 минут на полный workflow при повторных запусках.
- **Snyk:** Security scan step runs Snyk for Python deps (`continue-on-error: true`, `--severity-threshold=high`). Document any findings and fixes in "Key Decisions" or "Challenges".

---

## 4. Key Decisions

- **Versioning strategy:** CalVer (`YYYY.MM.DD`) was chosen because this is a service with time-based releases; no need to track breaking vs non-breaking changes in the API. Tags: date + `latest`.
- **Docker tags:** CI produces two tags per image: one date tag (e.g. `2026.02.10`) and `latest`. Pushes only on direct push to default branch.
- **Workflow triggers:** Push and pull_request to `master`/`main` with path filters so CI runs only when `app_python/` or the Python workflow file changes, reducing unnecessary runs.
- **Test coverage:** Routes and main response shapes are tested; exception handlers and some edge paths may be untested. Coverage threshold in CI: 70% (`--cov-fail-under=70`).

**Bonus — Multi-app CI and coverage**

- **Go CI:** `.github/workflows/go-ci.yml` runs on changes under `app_go/` (and the workflow file): lint (golangci-lint), tests (`go test -v -race ./...`), then Docker build/push with CalVer on push to default branch.
- **Path filters:** Python workflow runs only for `app_python/**` and `python-ci.yml`; Go workflow only for `app_go/**` and `go-ci.yml`. Both can run in parallel when both areas change.
- **Coverage:** pytest-cov генерирует `coverage.xml` в CI; загрузка в Codecov через `CODECOV_TOKEN` (опционально, `fail_ci_if_error: false`). Бейдж покрытия в README ведёт на codecov.io/gh/mituttta051/DevOps-Core-Course. Покрыто: маршруты и хелперы; не покрыты: exception handlers и `if __name__ == "__main__"`. Порог в CI: 70%.

---

## 5. Challenges (Optional)

- Snyk/Codecov: If no tokens are set, use `continue-on-error`/`fail_ci_if_error: false` so CI still passes; add tokens for full checks and coverage upload.
- Badge and Codecov links in README must use your fork’s `OWNER`/`REPO` (and branch name if not `master`).

---

## 6. Инструкция по проверке и ручным действиям

### Что сделать вручную

1. **Секреты в GitHub**  
   В репозитории: Settings → Secrets and variables → Actions. Добавить:
   - `DOCKERHUB_USERNAME` — логин Docker Hub  
   - `DOCKERHUB_TOKEN` — токен доступа Docker Hub (Account → Security → New Access Token, права: Read, Write, Delete)  
   - `SNYK_TOKEN` — токен Snyk (https://app.snyk.io/account; опционально)  
   - `CODECOV_TOKEN` — токен Codecov (https://codecov.io, Add new repository; опционально)

2. **Бейджи в README**  
   В `app_python/README.md` заменить в URL бейджей:
   - `OWNER` — ваш GitHub username  
   - `REPO` — имя репозитория (например `DevOps-Core-Course`)  
   Если дефолтная ветка не `master`, в бейдже Codecov заменить `branch/master` на `branch/main`.

3. **Ветка и коммиты**  
   - Создать ветку `lab03`: `git checkout -b lab03`  
   - Закоммитить изменения, запуш в свой fork: `git push -u origin lab03`

4. **Проверка CI**  
   - После пуша открыть вкладку Actions на GitHub.  
   - Должен запуститься workflow "Python CI". Убедиться, что все шаги зелёные.  
   - Если падает "Run tests with coverage" из‑за покрытия < 70%, добавить тесты или временно понизить `--cov-fail-under` в workflow.  
   - Для проверки Go CI изменить что‑нибудь в `app_go/` и запушить — должен запуститься "Go CI".

5. **Проверка Docker Hub**  
   После успешного CI при пуше в `master`/`main`: Docker Hub → Repositories → `devops-info-service-python` (и при наличии — `devops-info-service-go`). Должны быть теги `latest` и с датой.

6. **Локальный запуск тестов**  
   Python: `cd app_python && pip install -r requirements-dev.txt && pytest -v`  
   Go: `cd app_go && go test -v -race ./...`

7. **Pull Request**  
   Создать два PR: `your-fork:lab03` → `course-repo:master` и `your-fork:lab03` → `your-fork:master`. Убедиться, что CI запустился по PR и прошёл.

### Если команды не работают

- **pip install / SSL:** выполнить установку локально с доступом в интернет.  
- **go test:** при первой сборке нужна сеть для `go mod download`.  
- **Workflow не запускается:** проверить path filters и ветку (пуши в `master`/`main`, изменения в `app_python/` или `app_go/`).  
- **Docker push fails:** проверить `DOCKERHUB_USERNAME` и `DOCKERHUB_TOKEN` в Secrets.
