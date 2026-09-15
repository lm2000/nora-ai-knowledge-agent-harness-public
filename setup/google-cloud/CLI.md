# Provision the cloud foundation

[Cloud foundation](README.md) · [Qdrant guide](QDRANT.md) · [Offline validation](VALIDATION.md)

Run this guide on an operator workstation with Python 3, Bash and the Google Cloud CLI. The target project must already exist with billing and the operator's required provisioning permissions.

## Configure the target

From the repository root:

```bash
cd setup/google-cloud
[ -e config.env ] || cp config.env.example config.env
[ -e cli.env ] || cp cli.env.example cli.env
```

Edit both files using plain `KEY=VALUE` lines, without shell expressions, quotes or inline comments. The scripts parse these files; they do not source them as shell code.

| File | Required choices |
| --- | --- |
| `config.env` | Project, region/zone, machine type, data-disk size, backup bucket; `VECTOR_DB=qdrant` |
| `cli.env` | Operator account, network/subnet/router/NAT, VM, disk, service account and secret names |

The bucket name must be globally available. Choose disk capacity and machine size for the intended workload; example values are not sizing results. The script cannot create a project, link billing or grant its own initial privileges.

Inspect authenticated accounts with `gcloud auth list`; use `gcloud auth login` if the intended account is absent. The provisioner specifies account/project explicitly rather than changing gcloud defaults.

## Preview before applying

From `setup/google-cloud`:

```bash
python3 03-cloud-setup.py --stage check
```

Without `--apply`, each stage prints conditional commands and starts no subprocesses. This is a plan preview, not a live resource check. An optional `bash 02-render-plan.sh` writes a local text plan and refuses to overwrite an existing output.

## Apply stages in order

For each stage, inspect its preview, then add `--apply` to execute it:

```bash
python3 03-cloud-setup.py --stage check --apply
python3 03-cloud-setup.py --stage apis --apply
python3 03-cloud-setup.py --stage network --apply
python3 03-cloud-setup.py --stage identity --apply
python3 03-cloud-setup.py --stage storage --apply
python3 03-cloud-setup.py --stage vm --apply
```

| Stage | Expected result |
| --- | --- |
| `check` | Active project and enabled billing; read-only |
| `apis` | Required Compute, IAM, IAP, Storage and Secret Manager APIs enabled |
| `network` | Custom VPC/subnet, NAT egress and tagged IAP SSH access; no public Qdrant ports |
| `identity` | Dedicated VM identity; operator IAP/OS Login and service-account-use bindings |
| `storage` | Regional private backup bucket, zonal data disk and an empty secret container; no formatting or key generation |
| `vm` | Private Ubuntu 24.04 amd64 VM, OS Login and attached data disk with auto-delete disabled |

Inspect the IAM scopes in [03-cloud-setup.py](03-cloud-setup.py) before applying; some operator roles are project-wide. API propagation, quota and organization policy can still prevent a stage from completing.

Continue with [Qdrant installation](QDRANT.md). The application bundle uses a different deployment layout; it is not installed by these stages.

## Reruns and failures

The CLI looks up named resources, skips matches and stops on mismatches or ambiguous results. A failed stage can leave earlier creations in place, including when a remote operation outlives a timeout. Inspect that operation, resolve its cause and preview the same stage again. There is no general rollback or deletion command.

The script does not reconcile all inherited IAM, unrelated firewalls or existing project configuration. Its [offline tests](VALIDATION.md) exercise expected command contracts, not every live provider response.

[Official gcloud reference](https://docs.cloud.google.com/sdk/gcloud/reference) · [Cloud NAT](https://docs.cloud.google.com/nat/docs/set-up-manage-network-address-translation)
