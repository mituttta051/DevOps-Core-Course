package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestHealthHandler(t *testing.T) {
	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	rr := httptest.NewRecorder()
	healthHandler(rr, req)
	if rr.Code != http.StatusOK {
		t.Errorf("health: expected status 200, got %d", rr.Code)
	}
	ct := rr.Header().Get("Content-Type")
	if ct != "application/json" {
		t.Errorf("health: expected Content-Type application/json, got %s", ct)
	}
	var body HealthResponse
	if err := json.NewDecoder(rr.Body).Decode(&body); err != nil {
		t.Fatalf("health: decode json: %v", err)
	}
	if body.Status != "healthy" {
		t.Errorf("health: expected status healthy, got %s", body.Status)
	}
	if body.UptimeSeconds < 0 {
		t.Errorf("health: uptime_seconds should be non-negative, got %d", body.UptimeSeconds)
	}
}

func TestMainHandler(t *testing.T) {
	req := httptest.NewRequest(http.MethodGet, "/", nil)
	rr := httptest.NewRecorder()
	mainHandler(rr, req)
	if rr.Code != http.StatusOK {
		t.Errorf("main: expected status 200, got %d", rr.Code)
	}
	ct := rr.Header().Get("Content-Type")
	if ct != "application/json" {
		t.Errorf("main: expected Content-Type application/json, got %s", ct)
	}
	var body ServiceInfo
	if err := json.NewDecoder(rr.Body).Decode(&body); err != nil {
		t.Fatalf("main: decode json: %v", err)
	}
	if body.Service.Name != "devops-info-service" {
		t.Errorf("main: expected service name devops-info-service, got %s", body.Service.Name)
	}
	if body.Runtime.Timezone != "UTC" {
		t.Errorf("main: expected timezone UTC, got %s", body.Runtime.Timezone)
	}
}
