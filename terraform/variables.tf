variable "yandex_folder_id" {
  type        = string
  description = "Yandex Cloud folder ID"
}

variable "yandex_zone" {
  type        = string
  default     = "ru-central1-a"
  description = "Yandex Cloud zone"
}

variable "instance_name" {
  type        = string
  default     = "lab04-vm"
  description = "VM instance name"
}

variable "ssh_public_key" {
  type        = string
  sensitive   = true
  description = "SSH public key content for VM (e.g. content of ~/.ssh/id_rsa.pub)"
}

variable "allowed_ssh_cidr" {
  type        = string
  description = "CIDR block allowed for SSH (e.g. your IP/32)"
}

variable "image_family" {
  type        = string
  default     = "ubuntu-2204-lts"
  description = "Image family for VM"
}

variable "labels" {
  type        = map(string)
  default     = {}
  description = "Labels for resources"
}
