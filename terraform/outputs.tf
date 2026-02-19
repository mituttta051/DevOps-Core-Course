output "public_ip" {
  value       = yandex_compute_instance.lab04.network_interface[0].nat_ip_address
  description = "Public IP address of the VM"
}

output "ssh_command" {
  value       = "ssh ubuntu@${yandex_compute_instance.lab04.network_interface[0].nat_ip_address}"
  description = "SSH connection command"
}

output "instance_id" {
  value       = yandex_compute_instance.lab04.id
  description = "Yandex Compute instance ID"
}
