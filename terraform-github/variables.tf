variable "github_token" {
  type        = string
  sensitive   = true
  description = "GitHub personal access token"
}

variable "repository_name" {
  type        = string
  default     = "DevOps-Core-Course"
  description = "GitHub repository name"
}

variable "repository_description" {
  type        = string
  default     = "DevOps course lab assignments"
  description = "Repository description"
}

variable "repository_visibility" {
  type        = string
  default     = "public"
  description = "Repository visibility (public or private)"
}

variable "has_issues" {
  type        = bool
  default     = true
  description = "Enable issues"
}

variable "has_wiki" {
  type        = bool
  default     = false
  description = "Enable wiki"
}

variable "has_projects" {
  type        = bool
  default     = false
  description = "Enable projects"
}
