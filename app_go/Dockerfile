FROM golang:1.21-alpine AS builder

WORKDIR /build

COPY go.mod go.sum ./
RUN go mod download

COPY main.go .
RUN CGO_ENABLED=0 go build -ldflags="-w -s" -o /app/service .

FROM alpine:3.19

RUN addgroup -g 1000 -S appuser \
    && adduser -u 1000 -S appuser -G appuser

WORKDIR /app

COPY --from=builder /app/service .
RUN chown appuser:appuser /app/service

USER appuser

EXPOSE 5000

CMD ["./service"]
