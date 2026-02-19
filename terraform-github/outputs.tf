output "repository_full_name" {
  value       = github_repository.course_repo.full_name
  description = "Full name of the repository (owner/name)"
}

output "repository_html_url" {
  value       = github_repository.course_repo.html_url
  description = "Repository URL"
}
