{{- define "devops-info-service.name" -}}
{{- include "common.name" . }}
{{- end }}

{{- define "devops-info-service.fullname" -}}
{{- include "common.fullname" . }}
{{- end }}

{{- define "devops-info-service.chart" -}}
{{- include "common.chart" . }}
{{- end }}

{{- define "devops-info-service.labels" -}}
{{- include "common.labels" . }}
{{- end }}

{{- define "devops-info-service.selectorLabels" -}}
{{- include "common.selectorLabels" . }}
{{- end }}

{{- define "devops-info-service.envVars" -}}
- name: APP_NAME
  value: {{ include "devops-info-service.fullname" . }}
- name: APP_ENV
  value: {{ .Values.environment | default "production" }}
- name: LOG_LEVEL
  value: {{ .Values.logLevel | default "info" }}
{{- end -}}
