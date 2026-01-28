# DevOps Info Service - Go Implementation

A production-ready DevOps info service implemented in Go, providing detailed information about the service and its runtime environment.

## Overview

This service is a Go implementation of the DevOps Info Service, providing the same functionality as the Python version but with the benefits of a compiled language: small binary size, fast startup, and excellent performance.

## Prerequisites

- **Go 1.21 or higher** - [Download Go](https://golang.org/dl/)
- Basic knowledge of Go programming

## Installation

1. **Clone or navigate to the project directory:**
   ```bash
   cd app_go
   ```

2. **Download dependencies:**
   ```bash
   go mod download
   ```

3. **Verify installation:**
   ```bash
   go version
   ```

## Building the Application

### Development Build

Build the application:
```bash
go build -o devops-info-service main.go
```

### Production Build (Optimized)

Build an optimized binary with reduced size:
```bash
go build -ldflags="-s -w" -o devops-info-service main.go
```

### Cross-Platform Build

Build for different platforms:
```bash
# Linux
GOOS=linux GOARCH=amd64 go build -o devops-info-service-linux main.go

# macOS
GOOS=darwin GOARCH=amd64 go build -o devops-info-service-macos main.go

# Windows
GOOS=windows GOARCH=amd64 go build -o devops-info-service.exe main.go
```

## Running the Application

### Default Configuration

Run with default settings (0.0.0.0:5000):
```bash
./devops-info-service
```

Or run directly with `go run`:
```bash
go run main.go
```

### Custom Configuration

Configure via environment variables:
```bash
# Custom port
PORT=8080 ./devops-info-service

# Custom host and port
HOST=127.0.0.1 PORT=3000 ./devops-info-service
```

## API Endpoints

### GET /

Returns comprehensive service and system information.

**Response:**
```json
{
  "service": {
    "name": "devops-info-service",
    "version": "1.0.0",
    "description": "DevOps course info service",
    "framework": "Go (net/http + gorilla/mux)"
  },
  "system": {
    "hostname": "Anastasias-MacBook-Pro.local",
    "platform": "darwin",
    "platform_version": "darwin",
    "architecture": "arm64",
    "cpu_count": 11,
    "go_version": "go1.23.4"
  },
  "runtime": {
    "uptime_seconds": 1565,
    "uptime_human": "26 minutes",
    "current_time": "2026-01-26T17:59:27.844Z",
    "timezone": "UTC"
  },
  "request": {
    "client_ip": "[::1]:55254",
    "user_agent": "yaak",
    "method": "GET",
    "path": "/"
  },
  "endpoints": [
    {
      "path": "/",
      "method": "GET",
      "description": "Service information"
    },
    {
      "path": "/health",
      "method": "GET",
      "description": "Health check"
    }
  ]
}
```

### GET /health

Health check endpoint for monitoring.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-01-26T17:59:48.791Z",
  "uptime_seconds": 1586
}
```

## Configuration

The application can be configured using environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Server host address |
| `PORT` | `5000` | Server port number |

## Testing

### Using curl

```bash
# Test main endpoint
curl http://localhost:5000/

# Test health endpoint
curl http://localhost:5000/health

# Pretty print JSON
curl http://localhost:5000/ | jq
```

### Using HTTPie

```bash
# Test main endpoint
http GET http://localhost:5000/

# Test health endpoint
http GET http://localhost:5000/health
```

## Binary Size Comparison

Go produces a single, statically-linked binary with no external dependencies:

- **Go binary (optimized):** ~7.8 MB
- **Python application:** Requires Python runtime (~50-100 MB) + dependencies

## Features

- ✅ Same JSON structure as Python version
- ✅ Both endpoints (`/` and `/health`)
- ✅ Environment variable configuration
- ✅ Graceful shutdown handling
- ✅ Error handling (404, 405)
- ✅ Request logging
- ✅ Single binary deployment
- ✅ Cross-platform compilation support

## Dependencies

- **gorilla/mux** - HTTP router and URL matcher for building web services

## Project Structure

```
app_go/
├── main.go              # Main application
├── go.mod               # Go module definition
├── go.sum               # Dependency checksums (auto-generated)
├── README.md            # This file
├── .gitignore           # Git ignore rules
└── docs/                # Documentation
    ├── LAB01.md         # Implementation details
    ├── GO.md            # Language justification
    └── screenshots/      # Proof of work
```

## Development

### Running Tests

```bash
go test ./...
```

### Formatting Code

```bash
go fmt ./...
```

### Linting

```bash
# Install golangci-lint
go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest

# Run linter
golangci-lint run
```

## License

This project is part of the DevOps Core Course.
