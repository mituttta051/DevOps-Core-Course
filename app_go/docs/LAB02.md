# Lab 2 — Multi-Stage Docker Build (Go)

## Multi-Stage Build Strategy

The Dockerfile has two stages:

1. **Builder (golang:1.21-alpine):** Compiles the Go application. We copy `go.mod` and `go.sum` first and run `go mod download` so the dependency layer is cached when only source code changes. Then we copy `main.go` and build a static binary with `CGO_ENABLED=0` and `-ldflags="-w -s"` (strip debug info, reduce size). The binary is written to `/app/service`.

2. **Runtime (alpine:3.19):** Final image contains only the compiled binary. We create a non-root user `appuser`, copy the binary from the builder with `COPY --from=builder`, set ownership, switch to `appuser`, and run the service. No Go toolchain, no source code, no build tools.

Static linking (`CGO_ENABLED=0`) means the binary does not depend on glibc or other libraries from the builder, so it runs on minimal Alpine. The runtime stage does not need to install Go or any build dependencies.

---

## Size Comparison

After building, compare sizes:

```bash
docker build -t devops-info-service-go:lab02 .
docker images devops-info-service-go:lab02
docker images golang:1.21-alpine
```

**Builder stage (golang:1.21-alpine):** ~300+ MB (Go compiler, standard library, tools).

**Final image (alpine:3.19 + binary):** **17.3 MB** — under 20 MB. The binary is on the order of 8–12 MB; Alpine base is small.

**Why not use the builder as the final image?** The builder includes the full Go toolchain, source, and build cache. That increases attack surface, image size, and push/pull time. The runtime only needs the single executable.

---

## Why Multi-Stage Builds Matter for Compiled Languages

- **Size:** The final image ships only the binary and a minimal base (e.g. Alpine). Compilers and SDKs stay in the builder and are discarded.
- **Security:** Fewer packages and no build tools in the final image reduce the number of potential vulnerabilities and limit what an attacker can do if the container is compromised.
- **Efficiency:** Smaller images deploy and start faster and use less storage and bandwidth in registries and clusters.

---

## Build Process and Image Sizes

### Build

From `app_go/`:

```bash
docker build -t devops-info-service-go:lab02 .
```

Build output:

```
#0 building with "desktop-linux" instance using docker driver
#1 [internal] load build definition from Dockerfile
#2 [internal] load metadata for golang:1.21-alpine, alpine:3.19
#3 [internal] load .dockerignore
#4 [internal] load build context
#5 [builder 1/6] FROM golang:1.21-alpine
#6 [builder 2/6] WORKDIR /build
#7 [builder 3/6] COPY go.mod go.sum ./
#8 [builder 4/6] RUN go mod download
#9 [builder 5/6] COPY main.go .
#10 [builder 6/6] RUN CGO_ENABLED=0 go build -ldflags="-w -s" -o /app/service .
#11 [stage-1 1/5] FROM alpine:3.19
#12 [stage-1 2/5] RUN addgroup -g 1000 -S appuser && adduser -u 1000 -S appuser -G appuser
#13 [stage-1 3/5] WORKDIR /app
#14 [stage-1 4/5] COPY --from=builder /app/service .
#15 [stage-1 5/5] RUN chown appuser:appuser /app/service
#16 exporting to image
#17 naming to docker.io/library/devops-info-service-go:lab02 done
```

### Image sizes

```bash
docker images devops-info-service-go:lab02
```

**Final image:** `devops-info-service-go:lab02` — **17.3 MB** (under 20 MB). Builder stage (golang:1.21-alpine) is ~300+ MB; the runtime image keeps only the binary and Alpine base.

### Run and test

```bash
docker run -p 8080:5000 devops-info-service-go:lab02
```

With the container running:

```bash
curl http://localhost:8080/
curl http://localhost:8080/health
```

`GET /` response (excerpt):

```json
{"service":{"name":"devops-info-service","version":"1.0.0","framework":"Go (net/http + gorilla/mux)"},"system":{"hostname":"...","platform":"linux","go_version":"go1.21.13"},"runtime":{...},"request":{...},"endpoints":[...]}
```

`GET /health` response:

```json
{"status":"healthy","timestamp":"2026-02-04T11:44:10.469Z","uptime_seconds":1}
```

---

## Technical Explanation of Each Stage

### Stage 1: builder
- **FROM golang:1.21-alpine:** Provides Go 1.21 and standard tools on a small base.
- **WORKDIR /build:** All following commands run in `/build`.
- **COPY go.mod go.sum + go mod download:** Dependencies are fetched in a separate layer so code-only changes do not re-download modules.
- **COPY main.go + go build:** Build the binary with CGO disabled (static link) and `-ldflags="-w -s"` to shrink the binary. Output is `/app/service` so the path is known for `COPY --from=builder`.

### Stage 2: runtime
- **FROM alpine:3.19:** Minimal base; no compiler or Go.
- **addgroup / adduser:** Create `appuser` so the process does not run as root.
- **COPY --from=builder /app/service .:** Bring only the binary from the builder; nothing else from the builder stage is in the final image.
- **chown, USER appuser:** Binary is owned by `appuser`; the process runs as that user.
- **EXPOSE 5000:** Documents the app port.
- **CMD ["./service"]:** Run the binary. The app reads `HOST` and `PORT` from the environment (defaults 0.0.0.0:5000).

---

## Security Benefits

- **Smaller attack surface:** No shell, no package manager, no compiler in the final image. Fewer components to patch or exploit.
- **Non-root execution:** The service runs as `appuser`; a compromise has limited privileges inside the container.
- **No build artifacts:** Source code and build cache stay in the builder and are not present in the image you run or ship.
