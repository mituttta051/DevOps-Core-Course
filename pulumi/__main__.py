import pulumi
import pulumi_yandex as yandex

config = pulumi.Config()
folder_id = config.require("folder_id")
zone = config.get("zone") or "ru-central1-a"
instance_name = config.get("instance_name") or "lab04-vm"
allowed_ssh_cidr = config.require("allowed_ssh_cidr")
ssh_public_key = config.require("ssh_public_key")

network = yandex.vpc.Network(
    "lab04-network",
    name="lab04-network",
)

subnet = yandex.vpc.Subnet(
    "lab04-subnet",
    name="lab04-subnet",
    network_id=network.id,
    zone=zone,
    v4_cidr_blocks=["10.0.1.0/24"],
)

security_group = yandex.vpc.SecurityGroup(
    "lab04-sg",
    name="lab04-sg",
    network_id=network.id,
    ingress=[
        yandex.vpc.SecurityGroupIngressArgs(
            protocol="TCP",
            port=22,
            v4_cidr_blocks=[allowed_ssh_cidr],
        ),
        yandex.vpc.SecurityGroupIngressArgs(
            protocol="TCP",
            port=80,
            v4_cidr_blocks=["0.0.0.0/0"],
        ),
        yandex.vpc.SecurityGroupIngressArgs(
            protocol="TCP",
            port=5000,
            v4_cidr_blocks=["0.0.0.0/0"],
        ),
    ],
    egress=[
        yandex.vpc.SecurityGroupEgressArgs(
            protocol="ANY",
            v4_cidr_blocks=["0.0.0.0/0"],
        ),
    ],
)

ubuntu_image = yandex.compute.get_compute_image(family="ubuntu-2204-lts")

instance = yandex.compute.Instance(
    "lab04-vm",
    name=instance_name,
    zone=zone,
    platform_id="standard-v3",
    labels={"lab": "lab04"},
    resources=yandex.compute.InstanceResourcesArgs(
        cores=2,
        core_fraction=20,
        memory=1,
    ),
    boot_disk=yandex.compute.InstanceBootDiskArgs(
        initialize_params=yandex.compute.InstanceBootDiskInitializeParamsArgs(
            image_id=ubuntu_image.id,
            size=10,
            type_id="network-hdd",
        ),
    ),
    network_interfaces=[
        yandex.compute.InstanceNetworkInterfaceArgs(
            subnet_id=subnet.id,
            nat=True,
            security_group_ids=[security_group.id],
        ),
    ],
    metadata={
        "ssh-keys": f"ubuntu:{ssh_public_key}",
    },
)

pulumi.export("public_ip", instance.network_interfaces[0].nat_ip_address)
pulumi.export("ssh_command", instance.network_interfaces[0].nat_ip_address.apply(lambda ip: f"ssh ubuntu@{ip}"))
pulumi.export("instance_id", instance.id)
