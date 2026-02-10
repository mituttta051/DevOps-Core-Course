# Lab 2 — Docker Containerization

## 1. Docker Best Practices Applied

### Non-root user
The container runs as user `appuser` (UID 1000), not root. A dedicated group and user are created with `groupadd`/`useradd`; after copying the app, ownership is set with `chown` and `USER appuser` switches the process. Running as non-root limits the impact of a compromise and follows principle of least privilege.

### Specific base image version
`FROM python:3.13-slim` pins the exact variant and version. Slim omits common build tools and extras, reducing size and attack surface. Pinning avoids surprise breakage when the base is updated.

### Layer ordering and dependency caching
`requirements.txt` is copied and `pip install` is run before copying `app.py`. Dependencies change less often than application code, so this order lets Docker reuse the dependency layer when only code changes, speeding up rebuilds.

### Copy only necessary files
Only `requirements.txt` and `app.py` are copied. Application code is the minimum needed to run the service.

### .dockerignore
A `.dockerignore` file excludes `__pycache__`, `*.pyc`, `venv`, `.git`, `docs`, `tests`, IDE files, and similar. This shrinks the build context sent to the daemon and avoids accidentally including secrets or dev artifacts in the image.

### No cache for pip
`pip install --no-cache-dir` avoids storing the pip cache in the image, reducing layer size.

### Explicit EXPOSE
`EXPOSE 5000` documents the port the app listens on. It does not publish the port; `docker run -p` does. It helps operators and tools know which port to map.

---

## 2. Image Information & Decisions

### Base image
**Chosen:** `python:3.13-slim`

**Reasoning:** Python 3.13 is current; slim is smaller than the default image and does not include compilers or many optional packages. Alpine was not chosen to avoid musl/glibc and build issues with some wheels; slim is a good balance of size and compatibility.

### Final image size
**189 MB** (from `docker images devops-info-service:lab02`). Slim-based images for this app are typically in the 150–200 MB range. Assessment: acceptable for a small web service; further reduction would require multi-stage builds or distroless if needed.

### Layer structure
1. Base (python:3.13-slim)
2. User/group creation
3. WORKDIR
4. requirements.txt + pip install (reused when only code changes)
5. app.py copy
6. chown + USER

### Optimization choices
- Single `RUN` for user/group creation to avoid extra layers.
- Dependencies before application code for better cache use.
- `--no-cache-dir` for pip to keep the image smaller.
- `.dockerignore` to keep build context small and avoid unneeded files.

---

## 3. Build & Run Process

### Build

From `app_python/`:

```bash
docker build -t devops-info-service:lab02 .
```

Build output:

```
#0 building with "desktop-linux" instance using docker driver
#1 [internal] load build definition from Dockerfile
#1 transferring dockerfile: 460B done
#2 [internal] load metadata for docker.io/library/python:3.13-slim
#3 [internal] load .dockerignore
#4 [internal] load build context
#5 [1/7] FROM docker.io/library/python:3.13-slim
#6 [2/7] RUN groupadd --gid 1000 appuser     && useradd --uid 1000 --gid appuser --shell /bin/sh --create-home appuser
#7 [3/7] WORKDIR /app
#8 [4/7] COPY requirements.txt .
#9 [5/7] RUN pip install --no-cache-dir -r requirements.txt
#10 [6/7] COPY app.py .
#11 [7/7] RUN chown -R appuser:appuser /app
#12 exporting to image
#13 naming to docker.io/library/devops-info-service:lab02 done
```

---

### Run

```bash
docker run -p 8080:5000 devops-info-service:lab02
```

Container startup logs:

```
INFO:     Started server process [1]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:5000 (Press CTRL+C to quit)
```

---

### Test endpoints

With the container running and port mapped (e.g. 8080:5000):

```bash
curl http://localhost:8080/
curl http://localhost:8080/health
```

`GET /` response (excerpt):

```json
{"service":{"name":"devops-info-service","version":"1.0.0","description":"DevOps course info service","framework":"FastAPI"},"system":{"hostname":"...","platform":"Linux","python_version":"3.13.11"},"runtime":{...},"request":{...},"endpoints":[...]}
```

`GET /health` response:

```json
{"status":"healthy","timestamp":"2026-02-04T10:38:03.052182Z","uptime_seconds":6}
```

---

### Docker Hub

- **Repository URL:** https://hub.docker.com/r/mituta/devops-info-service

**Tagging strategy:** Image is tagged as `<docker-hub-username>/<repo-name>:<tag>`. The tag identifies the image and version; `lab02` marks this as the Lab 2 submission. For production I would use semantic versions or commit SHAs.

Push output:

```
The push refers to repository [docker.io/mituta/devops-info-service]
e771daa01571: Pushed 
b8671b075063: Pushed 
5b6f9b9d62d8: Pushed 
4977bdb631d5: Pushed 
f96a151634d7: Pushed 
f50f058759d5: Pushed 
083605e5ab90: Mounted from library/python 
675d3200abe3: Mounted from library/python 
e6060824c6b0: Mounted from library/python 
a0e71ab2b234: Mounted from library/python 
lab02: digest: sha256:12432e1b1e514d24f670acacfb5746210e6bdfd41e97f83fc1adb0f1a797d06b size: 2408
```

---

## 4. Technical Analysis

### Why the Dockerfile works this way
Dependencies are installed in their own layer so that changes to `app.py` do not invalidate the pip layer. The app runs as `appuser` so the process does not have root inside the container. `WORKDIR` sets a fixed path so `COPY` and runtime behavior are predictable. The CMD runs uvicorn as the application server with host `0.0.0.0` so the service is reachable from outside the container.

### Changing layer order
If we copied `app.py` before `requirements.txt` and then ran `pip install`, any change to `app.py` would invalidate the layer that runs `pip install`. Every code change would trigger a full dependency reinstall and slow down builds. Putting dependencies first keeps that layer stable when only code changes.

### Security considerations
- **Non-root user:** Process runs as unprivileged user; a breakout or exploit is less able to alter system files or run as root.
- **Minimal base:** Slim image has fewer packages and thus fewer potential vulnerabilities.
- **No unnecessary files:** `.dockerignore` and limited `COPY` reduce the chance of including secrets, scripts, or dev tools in the image.
- **Explicit dependencies:** Pinned in `requirements.txt` and installed in a controlled way instead of ad-hoc installs.

### How .dockerignore improves the build
The daemon only receives files that are not ignored. Excluding `__pycache__`, `venv`, `.git`, `docs`, and similar reduces the amount of data sent on each build and can speed up `docker build`. It also prevents those paths from being copied into the image if you ever use a broad `COPY . .`, and avoids accidentally including sensitive or irrelevant files.

---

## 5. Challenges & Solutions

**1. App not reachable from the host**

The app was bound to `127.0.0.1` when developed locally. Inside the container, that loopback address only accepts connections from inside the container, so requests from the host (e.g. `curl http://localhost:8080/`) never reached the app. Fix: run uvicorn with `--host 0.0.0.0` in the Dockerfile CMD so the server listens on all interfaces. The app still reads `HOST` from the environment; we set the host explicitly in CMD so the container behaves correctly regardless of env.

**2. Permission denied after switching to non-root user**

After adding `USER appuser`, the container failed at startup with permission errors on files in `/app`. The files were copied as root and owned by root, so `appuser` could not read them. Fix: run `chown -R appuser:appuser /app` before the `USER appuser` line so the non-root user owns the application directory and can read `app.py` and execute the process.
