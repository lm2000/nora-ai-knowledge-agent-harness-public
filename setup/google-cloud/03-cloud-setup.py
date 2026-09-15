#!/usr/bin/env python3
"""User-run provisioning. Preview is offline; --apply executes one selected stage."""
import argparse
import ipaddress
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from helpers import load_config, validate_config

BASE = Path(__file__).resolve().parent
KEYS = {'OPERATOR_EMAIL', 'NETWORK', 'SUBNET', 'SUBNET_CIDR', 'ROUTER', 'NAT',
        'VM_NAME', 'DATA_DISK', 'SERVICE_ACCOUNT', 'SECRET_NAME'}
STAGES = ('check', 'apis', 'network', 'identity', 'storage', 'vm')


def configuration(core, extra):
    c = load_config(Path(core))
    validate_config(c)
    e = {}
    for n, raw in enumerate(Path(extra).read_text().splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if '=' not in line:
            raise ValueError(f'CLI config line {n}: expected KEY=VALUE')
        k, v = map(str.strip, line.split('=', 1))
        if k not in KEYS or k in e:
            raise ValueError(f'CLI config line {n}: unknown or duplicate key')
        e[k] = v
    for k in sorted(KEYS):
        if not e.get(k):
            raise ValueError(f'Missing CLI configuration: {k}')
    if not re.fullmatch(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}', e['OPERATOR_EMAIL']):
        raise ValueError('OPERATOR_EMAIL must be a Google account email')
    for k in KEYS - {'OPERATOR_EMAIL', 'SUBNET_CIDR'}:
        limit = 30 if k == 'SERVICE_ACCOUNT' else 50  # leave room for firewall suffix
        if not re.fullmatch(r'[a-z][a-z0-9-]*[a-z0-9]', e[k]) or not 2 <= len(e[k]) <= limit:
            raise ValueError(f'{k}: use 2-{limit} lowercase letters/digits/hyphens')
    if len(e['SERVICE_ACCOUNT']) < 6:
        raise ValueError('SERVICE_ACCOUNT must have at least 6 characters')
    net = ipaddress.ip_network(e['SUBNET_CIDR'], strict=True)
    if net.version != 4 or not 8 <= net.prefixlen <= 29 or not net.is_private:
        raise ValueError('SUBNET_CIDR must be a private IPv4 network with /8 through /29')
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,61}[a-z0-9]', c['BACKUP_BUCKET_NAME']):
        raise ValueError('BACKUP_BUCKET_NAME must have 3-63 lowercase letters/digits/hyphens')
    c.update(e)
    return c


def require(condition, message):
    if not condition:
        raise ValueError(message)


def suffix(value, ending):
    return isinstance(value, str) and value.endswith('/' + ending)


def validate_resource(kind, r, c):
    """Compare API metadata, fail closed on missing required properties."""
    p, z, region = c['PROJECT_ID'], c['ZONE'], c['REGION']
    ref = lambda value, path: suffix(value, f'projects/{p}/{path}')
    regional = lambda value: ref(value, f'regions/{region}')
    network = lambda value: ref(value, f'global/networks/{c["NETWORK"]}')
    subnet = lambda value: ref(value, f'regions/{region}/subnetworks/{c["SUBNET"]}')
    ok = False
    if kind == 'network':
        ok = r.get('autoCreateSubnetworks') is False
    elif kind == 'subnet':
        ok = regional(r.get('region')) and network(r.get('network')) and r.get('ipCidrRange') == c['SUBNET_CIDR']
    elif kind == 'router':
        ok = regional(r.get('region')) and network(r.get('network'))
    elif kind == 'nat':
        subs = r.get('subnetworks', [])
        ok = (r.get('natIpAllocateOption') == 'AUTO_ONLY' and
              r.get('sourceSubnetworkIpRangesToNat') == 'LIST_OF_SUBNETWORKS' and
              len(subs) == 1 and subnet(subs[0].get('name')) and
              set(subs[0].get('sourceIpRangesToNat', [])) in ({'ALL_IP_RANGES'}, {'PRIMARY_IP_RANGE'}))
    elif kind == 'firewall':
        allowed = r.get('allowed', [])
        ok = (network(r.get('network')) and r.get('direction') == 'INGRESS' and
              not r.get('disabled', False) and not r.get('denied') and
              r.get('sourceRanges') == ['35.235.240.0/20'] and
              r.get('targetTags') == ['nora-iap'] and not r.get('sourceTags') and
              not r.get('sourceServiceAccounts') and not r.get('targetServiceAccounts') and
              len(allowed) == 1 and allowed[0].get('IPProtocol') in ('tcp', '6') and
              allowed[0].get('ports') == ['22'])
    elif kind == 'sa':
        ok = r.get('email') == sa_email(c) and not r.get('disabled', False)
    elif kind == 'bucket':
        iam = r.get('iamConfiguration', {})
        ok = (str(r.get('location', '')).lower() == region and
              iam.get('uniformBucketLevelAccess', {}).get('enabled') is True and
              iam.get('publicAccessPrevention') == 'enforced')
    elif kind in ('disk', 'boot'):
        size = c['DISK_SIZE_GB'] if kind == 'disk' else '30'
        ok = (ref(r.get('zone'), f'zones/{z}') and
              ref(r.get('type'), f'zones/{z}/diskTypes/pd-balanced') and
              str(r.get('sizeGb')) == size)
        if kind == 'boot':
            ok = ok and '/projects/ubuntu-os-cloud/global/images/ubuntu-2404-noble-amd64-' in r.get('sourceImage', '')
    elif kind == 'secret':
        ok = 'automatic' in r.get('replication', {})
    elif kind == 'vm':
        interfaces, accounts, disks = r.get('networkInterfaces', []), r.get('serviceAccounts', []), r.get('disks', [])
        meta = {i.get('key'): i.get('value') for i in r.get('metadata', {}).get('items', [])}
        data = [d for d in disks if d.get('boot') is not True]
        boots = [d for d in disks if d.get('boot') is True]
        ok = (ref(r.get('zone'), f'zones/{z}') and
              ref(r.get('machineType'), f'zones/{z}/machineTypes/{c["MACHINE_TYPE"]}') and
              len(interfaces) == 1 and subnet(interfaces[0].get('subnetwork')) and
              network(interfaces[0].get('network')) and not interfaces[0].get('accessConfigs') and
              not interfaces[0].get('ipv6AccessConfigs') and
              set(r.get('tags', {}).get('items', [])) == {'nora-iap'} and
              len(accounts) == 1 and accounts[0].get('email') == sa_email(c) and
              'https://www.googleapis.com/auth/cloud-platform' in accounts[0].get('scopes', []) and
              str(meta.get('enable-oslogin', '')).upper() == 'TRUE' and
              len(boots) == 1 and len(data) == 1 and
              ref(data[0].get('source'), f'zones/{z}/disks/{c["DATA_DISK"]}') and
              data[0].get('deviceName') == c['DATA_DISK'] and data[0].get('autoDelete') is False and
              data[0].get('mode') == 'READ_WRITE')
    require(ok, f'Existing {kind} differs from the requested setup; inspect it before continuing. Nothing is overwritten.')


def sa_email(c):
    return f'{c["SERVICE_ACCOUNT"]}@{c["PROJECT_ID"]}.iam.gserviceaccount.com'


@dataclass
class Resource:
    kind: str
    name: str
    lookup: list
    create: list
    parent: str = ''  # NATs are embedded in the router list response


class Setup:
    def __init__(self, c, runner=subprocess.run):
        self.c, self.runner = c, runner

    def cmd(self, *args):
        return ['gcloud', *args, f'--project={self.c["PROJECT_ID"]}',
                f'--account={self.c["OPERATOR_EMAIL"]}', '--quiet', '--format=json']

    def run(self, command):
        try:
            result = self.runner(command, capture_output=True, text=True, shell=False, timeout=600)
        except (OSError, subprocess.TimeoutExpired):
            raise RuntimeError('gcloud could not finish. Inspect the named command manually; a timed-out mutation may have completed.') from None
        if result.returncode:
            raise RuntimeError(f'gcloud exited {result.returncode}; inspect the named command manually. No further commands were run.')
        try:
            return json.loads(result.stdout) if result.stdout.strip() else None
        except json.JSONDecodeError:
            raise RuntimeError('gcloud returned invalid JSON; no further commands were run.') from None

    def precheck(self):
        p = self.c['PROJECT_ID']
        project = self.run(self.cmd('projects', 'describe', p))
        require(isinstance(project, dict) and project.get('projectId') == p and project.get('lifecycleState') == 'ACTIVE', 'Project must exist and be ACTIVE')
        billing = self.run(self.cmd('billing', 'projects', 'describe', p))
        require(isinstance(billing, dict) and billing.get('billingEnabled') is True, 'Project billing is not enabled')

    def resources(self, stage):
        c, cmd = self.c, self.cmd
        reg, zone = f'--region={c["REGION"]}', f'--zone={c["ZONE"]}'
        net = f'--network={c["NETWORK"]}'
        def op(kind, name, group, args, lookup_args=()):
            return Resource(kind, name, cmd(*group, 'list', *lookup_args), cmd(*group, 'create', name, *args))
        if stage == 'network':
            routers = cmd('compute', 'routers', 'list')
            return [
                op('network', c['NETWORK'], ('compute', 'networks'), ['--subnet-mode=custom']),
                op('subnet', c['SUBNET'], ('compute', 'networks', 'subnets'), [net, reg, f'--range={c["SUBNET_CIDR"]}']),
                op('router', c['ROUTER'], ('compute', 'routers'), [net, reg]),
                Resource('nat', c['NAT'], routers, cmd('compute', 'routers', 'nats', 'create', c['NAT'], f'--router={c["ROUTER"]}', reg, '--auto-allocate-nat-external-ips', f'--nat-custom-subnet-ip-ranges={c["SUBNET"]}'), c['ROUTER']),
                op('firewall', c['NETWORK']+'-iap-ssh', ('compute', 'firewall-rules'), [net, '--direction=INGRESS', '--allow=tcp:22', '--source-ranges=35.235.240.0/20', '--target-tags=nora-iap'])]
        if stage == 'identity':
            return [op('sa', c['SERVICE_ACCOUNT'], ('iam', 'service-accounts'), [])]
        if stage == 'storage':
            return [Resource('bucket', c['BACKUP_BUCKET_NAME'], cmd('storage', 'buckets', 'list', '--raw'), cmd('storage', 'buckets', 'create', 'gs://'+c['BACKUP_BUCKET_NAME'], f'--location={c["REGION"]}', '--uniform-bucket-level-access', '--public-access-prevention')),
                    op('disk', c['DATA_DISK'], ('compute', 'disks'), [zone, '--type=pd-balanced', f'--size={c["DISK_SIZE_GB"]}GB']),
                    op('secret', c['SECRET_NAME'], ('secrets',), ['--replication-policy=automatic'])]
        if stage == 'vm':
            return [op('vm', c['VM_NAME'], ('compute', 'instances'), [zone, f'--machine-type={c["MACHINE_TYPE"]}', f'--subnet={c["SUBNET"]}', '--no-address', '--tags=nora-iap', f'--service-account={sa_email(c)}', '--scopes=cloud-platform', '--metadata=enable-oslogin=TRUE', '--image-family=ubuntu-2404-lts-amd64', '--image-project=ubuntu-os-cloud', '--boot-disk-size=30GB', '--boot-disk-type=pd-balanced', f'--disk=name={c["DATA_DISK"]},device-name={c["DATA_DISK"]},mode=rw,boot=no,auto-delete=no'])]
        return []

    def bindings(self, stage):
        c, cmd = self.c, self.cmd
        user = '--member=user:'+c['OPERATOR_EMAIL']
        member = '--member=serviceAccount:'+sa_email(c)
        if stage == 'identity':
            return [cmd('projects', 'add-iam-policy-binding', c['PROJECT_ID'], user, '--role='+role, '--condition=None') for role in ('roles/iap.tunnelResourceAccessor', 'roles/compute.osAdminLogin')] + [cmd('iam', 'service-accounts', 'add-iam-policy-binding', sa_email(c), user, '--role=roles/iam.serviceAccountUser', '--condition=None')]
        if stage == 'storage':
            return [cmd('storage', 'buckets', 'add-iam-policy-binding', 'gs://'+c['BACKUP_BUCKET_NAME'], member, '--role=roles/storage.objectAdmin', '--condition=None'), cmd('secrets', 'add-iam-policy-binding', c['SECRET_NAME'], member, '--role=roles/secretmanager.secretAccessor', '--condition=None')]
        return []

    def lookup(self, op, cache):
        key = tuple(op.lookup)
        if key not in cache:
            data = self.run(op.lookup)
            require(isinstance(data, list) and all(isinstance(x, dict) for x in data), 'Resource list must be a JSON array')
            cache[key] = data
        data = cache[key]
        if op.parent:
            parents = [r for r in data if r.get('name') == op.parent]
            require(len(parents) <= 1, 'Ambiguous router name across regions')
            if parents:
                validate_resource('router', parents[0], self.c)
            data = parents[0].get('nats', []) if parents else []
        if op.kind == 'sa':
            found = [r for r in data if r.get('email') == sa_email(self.c)]
        else:
            found = [r for r in data if str(r.get('name', '')).split('/')[-1] == op.name]
        require(len(found) <= 1, f'Ambiguous {op.kind} name across scopes')
        if found:
            validate_resource(op.kind, found[0], self.c)
            return found[0]
        return None

    def execute(self, stage, apply=False):
        require(stage in STAGES, 'Unknown stage')
        ops, bindings = self.resources(stage), self.bindings(stage)
        api_names = [s+'.googleapis.com' for s in ('compute', 'secretmanager', 'iap', 'iam', 'storage')]
        checks = [self.cmd('projects', 'describe', self.c['PROJECT_ID']), self.cmd('billing', 'projects', 'describe', self.c['PROJECT_ID'])]
        if not apply:
            print('OFFLINE PREVIEW: conditional commands; no cloud state was read.')
            commands = checks + [o.lookup for o in ops] + [o.create for o in ops] + bindings
            if stage == 'apis':
                commands += [self.cmd('services', 'list', '--enabled'), self.cmd('services', 'enable', *api_names)]
            if stage == 'storage':
                commands += [o.lookup for o in self.resources('identity')]
            if stage == 'vm':
                commands += [o.lookup for dep in ('network', 'identity', 'storage') for o in self.resources(dep)] + [self.cmd('compute', 'disks', 'list')]
            for command in commands:
                print(shlex.join(command))
            return
        print('Check project and billing')
        self.precheck()
        if stage == 'apis':
            enabled = self.run(self.cmd('services', 'list', '--enabled'))
            require(isinstance(enabled, list), 'API list must be a JSON array')
            names = {r.get('config', {}).get('name') or str(r.get('name', '')).split('/')[-1] for r in enabled}
            missing = [n for n in api_names if n not in names]
            if missing:
                print('Enable required APIs')
                self.run(self.cmd('services', 'enable', *missing))
            print('API stage complete')
            return
        # Inspect all resources before this stage makes its first change.
        cache, pending = {}, []
        if stage == 'storage':
            require(self.lookup(self.resources('identity')[0], cache) is not None, 'Run identity stage first')
        if stage == 'vm':
            dependencies = self.resources('network') + self.resources('identity') + self.resources('storage')
            for dependency in dependencies:
                require(self.lookup(dependency, cache) is not None, 'Run earlier stages first: missing '+dependency.kind)
        for op in ops:
            print('Inspect '+op.kind+' '+op.name)
            existing = self.lookup(op, cache)
            if existing is None:
                pending.append(op)
            elif op.kind == 'vm':
                boot = next(d for d in existing['disks'] if d.get('boot'))
                disks = self.run(self.cmd('compute', 'disks', 'list'))
                require(isinstance(disks, list), 'Disk list must be an array')
                matches = [d for d in disks if d.get('selfLink') == boot.get('source')]
                require(len(matches) == 1, 'Cannot verify existing VM boot disk')
                validate_resource('boot', matches[0], self.c)
            else:
                print('Matching resource: skip creation')
        for op in pending:
            print('Create '+op.kind+' '+op.name)
            self.run(op.create)
            require(self.lookup(op, {}) is not None, f'Created {op.kind} was not returned by readback; stop and inspect')
        for command in bindings:
            print('Ensure IAM binding: '+shlex.join(command))
            self.run(command)
        print(f'{stage} stage complete. No application installed; secret payload is a separate user step.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=BASE/'config.env')
    parser.add_argument('--cli-config', type=Path, default=BASE/'cli.env')
    parser.add_argument('--stage', required=True, choices=STAGES)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args(argv)
    try:
        Setup(configuration(args.config, args.cli_config)).execute(args.stage, args.apply)
    except (ValueError, RuntimeError, OSError) as exc:
        print('Stopped: '+str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
