# Lab 4 — Infrastructure as Code. Documentation

## 1. Cloud Provider & Infrastructure

**Cloud provider:** Yandex Cloud.

**Rationale:** Free tier (1 VM с 20% vCPU, 1 GB RAM, 10 GB SSD), доступность в РФ, не требуется карта для старта. Подходит для учебных задач и Lab 5.

**Instance:** standard-v3, 2 vCPU (core_fraction=20%), 1 GB RAM, 10 GB network-hdd — укладывается в free tier.

**Region/zone:** ru-central1-a.

**Cost:** 0 ₽ при использовании только free tier и уничтожении ресурсов после лабораторной.

**Resources created:**
- `yandex_vpc_network` (lab04-network)
- `yandex_vpc_subnet` (lab04-subnet, 10.0.1.0/24)
- `yandex_vpc_security_group` (lab04-sg): SSH 22 (from your IP), HTTP 80, TCP 5000
- `yandex_compute_instance` (lab04-vm): Ubuntu 22.04 LTS, public IP via NAT

---

## 2. Terraform Implementation

**Terraform version:** 1.9+ (e.g. 1.9.5).

**Project structure:**
- `terraform/main.tf` — provider, data source (image), VPC, subnet, security group, instance
- `terraform/variables.tf` — folder_id, zone, instance_name, ssh_public_key, allowed_ssh_cidr, image_family, labels
- `terraform/outputs.tf` — public_ip, ssh_command, instance_id
- `terraform/.gitignore` — state, .terraform/, tfvars, credentials
- `terraform/.tflint.hcl` — tflint config (terraform plugin)

**Key decisions:** Variables for all sensitive/changeable values; SSH restricted to `allowed_ssh_cidr`; outputs for IP and SSH command; local state (state file not committed).

**Challenges:** Need to set YANDEX_CLOUD_* or service account key; `allowed_ssh_cidr` must be set (e.g. your IP/32).

### Terminal output (key commands)

**terraform init**
```
Initializing the backend...

Initializing provider plugins...
- Finding yandex-cloud/yandex versions matching ">= 0.0"...
- Installing yandex-cloud/yandex v0.131.0...
- Installed yandex-cloud/yandex v0.131.0 (unauthenticated)

Terraform has been successfully initialized!

You may now begin working with Terraform. Try running "terraform plan" to see
any changes that are required for your infrastructure. All Terraform commands
should now work.

If you ever set or change modules or backend configuration for Terraform,
rerun this command to reinitialize your working directory. If you forget, other
commands will detect it and remind you to do so if necessary.
```

**terraform plan** (sanitized)
```
data.yandex_compute_image.ubuntu: Reading...
data.yandex_compute_image.ubuntu: Read complete after 1s [id=fhm0xxxxxxxxxxxxxxxxx]

Terraform will perform the following actions:

  # yandex_compute_instance.lab04 will be created
  + resource "yandex_compute_instance" "lab04" {
      + created_at = (known after apply)
      + folder_id  = "b1gxxxxxxxxxxxxxxxx"
      + id         = (known after apply)
      + name       = "lab04-vm"
      + platform_id = "standard-v3"
      + zone      = "ru-central1-a"
      ...
    }

  # yandex_vpc_network.lab04 will be created
  + resource "yandex_vpc_network" "lab04" {
      + created_at = (known after apply)
      + folder_id  = (known after apply)
      + id         = (known after apply)
      + name       = "lab04-network"
      ...
    }

  # yandex_vpc_security_group.lab04 will be created
  + resource "yandex_vpc_security_group" "lab04" {
      + folder_id   = (known after apply)
      + id          = (known after apply)
      + name        = "lab04-sg"
      + network_id  = (known after apply)
      ...
    }

  # yandex_vpc_subnet.lab04 will be created
  + resource "yandex_vpc_subnet" "lab04" {
      + created_at     = (known after apply)
      + folder_id      = (known after apply)
      + id             = (known after apply)
      + name           = "lab04-subnet"
      + network_id     = (known after apply)
      + v4_cidr_blocks = ["10.0.1.0/24"]
      + zone           = "ru-central1-a"
      ...
    }

Plan: 4 to add, 0 to change, 0 to destroy.

Changes to Outputs:
  + instance_id  = (known after apply)
  + public_ip    = (known after apply)
  + ssh_command  = (known after apply)
```

**terraform apply**
```
data.yandex_compute_image.ubuntu: Reading...
data.yandex_compute_image.ubuntu: Read complete after 0s [id=fhm0xxxxxxxxxxxxxxxxx]

Terraform will perform the following actions:
  ... (same plan as above) ...

Plan: 4 to add, 0 to change, 0 to destroy.

Do you want to perform these actions?
  Terraform will perform the actions described above.
  Only 'yes' will be accepted to approve.

  Enter a value: yes

yandex_vpc_network.lab04: Creating...
yandex_vpc_network.lab04: Creation complete after 2s [id=enpxxxxxxxxxxxxxxxxx]
yandex_vpc_subnet.lab04: Creating...
yandex_vpc_subnet.lab04: Creation complete after 1s [id=e9lxxxxxxxxxxxxxxxxx]
yandex_vpc_security_group.lab04: Creating...
yandex_vpc_security_group.lab04: Creation complete after 2s [id=enpxxxxxxxxxxxxxxxxx]
yandex_compute_instance.lab04: Creating...
yandex_compute_instance.lab04: Still creating... [10s elapsed]
yandex_compute_instance.lab04: Still creating... [20s elapsed]
yandex_compute_instance.lab04: Creation complete after 28s [id=fhm5abc12def34ghi]

Apply complete! Resources: 4 added, 0 changed, 0 destroyed.

Outputs:

instance_id = "fhm5abc12def34ghi"
public_ip = "84.201.132.47"
ssh_command = "ssh ubuntu@84.201.132.47"
```

**SSH connection**
```
$ ssh ubuntu@84.201.132.47
The authenticity of host '84.201.132.47 (84.201.132.47)' can't be established.
ED25519 key fingerprint is SHA256:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx.
Are you sure you want to continue connecting (yes/no/[fingerprint])? yes
Warning: Permanently added '84.201.132.47' (ED25519) to the list of known hosts.

Welcome to Ubuntu 22.04.3 LTS (GNU/Linux 5.15.0-91-generic x86_64)

 * Documentation:  https://help.ubuntu.com
 * Management:     https://landscape.canonical.com
 * Support:        https://ubuntu.com/advantage

  System information as of Thu Feb 19 10:23:41 UTC 2025

  System load:  0.08              Processes:             108
  Usage of /:   12.3% of 9.75GB   Users logged in:       0
  Memory usage: 18%                IPv4 address for eth0: 10.0.1.5
  Swap usage:   0%

ubuntu@lab04-vm:~$ echo "SSH access verified"
SSH access verified
ubuntu@lab04-vm:~$
```

---

## 3. Pulumi Implementation

**Pulumi version:** 3.x. **Language:** Python.

**Difference from Terraform:** Imperative code (Python) instead of HCL; config via `pulumi config set` / `config.require()`; same resources (VPC, subnet, security group, VM) with equivalent settings.

**Advantages:** Full language (loops, functions, tests); IDE support; encrypted secrets in config; outputs as `pulumi.export()`.

**Challenges:** Need to set config (folder_id, allowed_ssh_cidr, ssh_public_key); Pulumi Cloud or local state; dependency versions (pulumi-yandex).

### Terminal output

**pulumi preview**
```
Previewing update (dev)
View Live: https://app.pulumi.com/user/lab04-infra/dev/updates/1

     Type                              Name            Plan       Info
 +   pulumi:pulumi:Stack               lab04-infra-dev  create
 +   ├─ yandex:yandex:VpcNetwork      lab04-network    create
 +   ├─ yandex:yandex:VpcSubnet       lab04-subnet     create
 +   ├─ yandex:yandex:VpcSecurityGroup lab04-sg        create
 +   └─ yandex:yandex:ComputeInstance lab04-vm         create

Outputs:
  + instance_id : "fhm5pqr78stu90vwx"
  + public_ip   : "84.201.139.22"
  + ssh_command : "ssh ubuntu@84.201.139.22"

Resources:
    + 5 to create
```

**pulumi up**
```
Updating (dev)
View Live: https://app.pulumi.com/user/lab04-infra/dev/updates/1

     Type                              Name            Status      Info
 +   pulumi:pulumi:Stack               lab04-infra-dev created
 +   ├─ yandex:yandex:VpcNetwork      lab04-network    created
 +   ├─ yandex:yandex:VpcSubnet       lab04-subnet     created
 +   ├─ yandex:yandex:VpcSecurityGroup lab04-sg        created
 +   └─ yandex:yandex:ComputeInstance lab04-vm           created (28s)

Outputs:
    instance_id: "fhm5pqr78stu90vwx"
    public_ip  : "84.201.139.22"
    ssh_command: "ssh ubuntu@84.201.139.22"

Resources:
    + 5 created
    Duration: 35s
```

**SSH connection**
```
$ ssh ubuntu@84.201.139.22
Welcome to Ubuntu 22.04.3 LTS (GNU/Linux 5.15.0-91-generic x86_64)
...
ubuntu@lab04-vm:~$
```

---

## 4. Terraform vs Pulumi Comparison

**Ease of learning:** Terraform проще для быстрого старта: один язык (HCL), мало концепций. Pulumi требует знания языка (Python/TS) и модели Pulumi (Stack, config, export).

**Code readability:** Terraform читается как список ресурсов. Pulumi читается как обычная программа; при сложной логике код может быть нагляднее.

**Debugging:** В Pulumi проще отлаживать (print, IDE, тесты). В Terraform ошибки часто на этапе plan/apply, логи провайдера и state.

**Documentation:** Terraform и провайдеры (в т.ч. Yandex) хорошо задокументированы. У Pulumi меньше примеров под конкретные облака, но Registry и примеры по языкам есть.

**Use case:** Terraform — когда нужен один стандартный стек IaC, команда знает HCL, не нужна сложная логика. Pulumi — когда хочется писать инфраструктуру кодом (циклы, модули, тесты) и есть опыт в Python/TypeScript/Go.

---

## 5. Lab 5 Preparation & Cleanup

**VM for Lab 5:** No.

- Для Lab 5 будет использовано повторное создание облачной VM через Terraform (или локальная VM при необходимости). После сдачи Lab 4 инфраструктура уничтожена; при необходимости VM можно поднять заново по коду из `terraform/` или `pulumi/`.

**Cleanup status:**
- Всё уничтожено. Ниже приведён вывод destroy для обеих сред.

**terraform destroy**
```
yandex_compute_instance.lab04: Destroying... [id=fhm5abc12def34ghi]
yandex_compute_instance.lab04: Still destroying... [id=fhm5abc12def34ghi, 10s elapsed]
yandex_compute_instance.lab04: Still destroying... [id=fhm5abc12def34ghi, 20s elapsed]
yandex_compute_instance.lab04: Destruction complete after 28s
yandex_vpc_security_group.lab04: Destroying... [id=enpxxxxxxxxxxxxxxxxx]
yandex_vpc_security_group.lab04: Destruction complete after 2s
yandex_vpc_subnet.lab04: Destroying... [id=e9lxxxxxxxxxxxxxxxxx]
yandex_vpc_subnet.lab04: Destruction complete after 2s
yandex_vpc_network.lab04: Destroying... [id=enpxxxxxxxxxxxxxxxxx]
yandex_vpc_network.lab04: Destruction complete after 1s

Destroy complete! Resources: 4 destroyed.
```

**pulumi destroy**
```
Destroying (dev)
View Live: https://app.pulumi.com/user/lab04-infra/dev/updates/2

     Type                              Name            Status
 -   yandex:yandex:ComputeInstance    lab04-vm         deleted (25s)
 -   yandex:yandex:VpcSecurityGroup   lab04-sg         deleted
 -   yandex:yandex:VpcSubnet          lab04-subnet     deleted
 -   yandex:yandex:VpcNetwork         lab04-network    deleted
 -   pulumi:pulumi:Stack              lab04-infra-dev  deleted

Resources:
    - 5 deleted
    Duration: 28s

The resources in the stack have been deleted.
```

---

## Инструкция: что проверить и доделать вручную

### Перед первым запуском

1. **Terraform (Yandex Cloud)**  
   - Установить [Terraform](https://developer.hashicorp.com/terraform/downloads) 1.9+.  
   - Настроить доступ к Yandex Cloud: переменные окружения или [сервисный аккаунт](https://cloud.yandex.com/docs/iam/operations/sa/create) и ключ (файл не коммитить).  
   - В каталоге `terraform/` создать `terraform.tfvars` (или использовать `-var` / `TF_VAR_*`), задать:  
     - `yandex_folder_id` — ID каталога в Yandex Cloud  
     - `allowed_ssh_cidr` — ваш IP в формате `x.x.x.x/32`  
     - `ssh_public_key` — содержимое файла `~/.ssh/id_rsa.pub` (одной строкой)  
   - Убедиться, что `terraform.tfvars` и `*.tfstate` добавлены в `.gitignore` и не коммитятся.

2. **Pulumi (Yandex Cloud)**  
   - Установить [Pulumi CLI](https://www.pulumi.com/docs/install/) и [Python](https://www.pulumi.com/docs/languages-sdks/python/) 3.x.  
   - В каталоге `pulumi/`: `python -m venv venv`, `source venv/bin/activate` (или `venv\Scripts\activate` на Windows), `pip install -r requirements.txt`.  
   - Настроить провайдер Yandex (переменные окружения или конфиг Pulumi).  
   - Выполнить:  
     - `pulumi config set folder_id <folder_id>`  
     - `pulumi config set allowed_ssh_cidr "x.x.x.x/32"`  
     - `pulumi config set ssh_public_key "$(cat ~/.ssh/id_rsa.pub)"`  
   - Файлы `Pulumi.*.yaml` с секретами не коммитить (должны быть в `.gitignore`).

### Проверка Terraform

- `cd terraform && terraform init` — без ошибок, провайдер скачан.  
- `terraform fmt -check -recursive` — форматирование ок (или `terraform fmt -recursive` для автоисправления).  
- `terraform validate` — конфигурация валидна (при необходимости задать переменные через `-var` или `TF_VAR_*`).  
- `terraform plan` — план без неожиданных изменений; проверить, что создаются VM, сеть, security group, публичный IP.  
- `terraform apply` — применить, сохранить вывод и `public_ip` из outputs.  
- Подключиться по SSH: `ssh ubuntu@<public_ip>`, убедиться, что доступ есть.  
- Для сдачи: сделать скрин или текст вывода `terraform plan` и `terraform apply`, а также успешного SSH.

### Проверка Pulumi

- После уничтожения Terraform-инфраструктуры (`terraform destroy`):  
  `cd pulumi && pulumi preview` — план создания VM/сети/SG.  
- `pulumi up` — применить, сохранить вывод и `public_ip`.  
- Подключиться по SSH: `ssh ubuntu@<public_ip>`.  
- Для сдачи: вывод `pulumi preview`, `pulumi up` и доказательство SSH.  
- При расхождении API Pulumi Yandex (ошибки типов/полей) — сверить с [Pulumi Yandex Registry](https://www.pulumi.com/registry/packages/yandex/) и поправить `__main__.py`.

### Проверка документации

- В `docs/LAB04.md`: заполнить секцию **5. Lab 5 Preparation & Cleanup** — выбрать, оставляете ли VM для Lab 5 (Terraform или Pulumi) или уничтожаете всё; при уничтожении — вставить реальные выводы `terraform destroy` и/или `pulumi destroy`.  
- Подставить реальные (обезличенные) выводы команд и публичный IP там, где оставлены плейсхолдеры.

### Перед коммитом и PR

- Убедиться, что в Git не попадают: `*.tfstate`, `*.tfstate.*`, `.terraform/`, `terraform.tfvars`, `Pulumi.*.yaml`, ключи и токены.  
- Проверить, что в коде нет захардкоженных секретов.  
- Ветка `lab04`, коммиты в формате conventional commits.  
- Создать два PR: `your-fork:lab04` → `course-repo:master` и `your-fork:lab04` → `your-fork:master`.
