# Lab 4 — Terraform (Yandex Cloud)

## Prerequisites

- Terraform 1.9+
- Yandex Cloud account, folder ID, and authentication (env vars or service account key)

## Setup

1. Set authentication (e.g. `export YANDEX_CLOUD_ID`, `YANDEX_FOLDER_ID`, `YANDEX_TOKEN` or use service account key file).
2. Create `terraform.tfvars` (do not commit) with:
   - `yandex_folder_id`
   - `allowed_ssh_cidr` (your IP as `x.x.x.x/32`)
   - `ssh_public_key` (contents of `~/.ssh/id_rsa.pub`)
3. Run `terraform init`, `terraform plan`, `terraform apply`.
4. Connect: `ssh ubuntu@$(terraform output -raw public_ip)`.

## Cleanup

`terraform destroy`
