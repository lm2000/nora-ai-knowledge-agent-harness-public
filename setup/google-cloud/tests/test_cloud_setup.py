"""Offline contract tests. No cloud command is executed."""
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('nora_cloud_setup', ROOT/'03-cloud-setup.py')
cli = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = cli
spec.loader.exec_module(cli)
C = dict(PROJECT_ID='nora-rag-dev', REGION='us-central1', ZONE='us-central1-a', VECTOR_DB='qdrant', MACHINE_TYPE='e2-standard-4', DISK_SIZE_GB='200', BACKUP_BUCKET_NAME='nora-rag-dev-backup', OPERATOR_EMAIL='operator@example.com', NETWORK='nora-rag-net', SUBNET='nora-rag-subnet', SUBNET_CIDR='10.42.0.0/24', ROUTER='nora-rag-router', NAT='nora-rag-nat', VM_NAME='nora-rag-vm', DATA_DISK='nora-qdrant-data', SERVICE_ACCOUNT='nora-agent-sa', SECRET_NAME='nora-api-key')
P = 'https://www.googleapis.com/compute/v1/projects/nora-rag-dev/'
R = P+'regions/us-central1'
Z = P+'zones/us-central1-a'
N = P+'global/networks/nora-rag-net'
S = R+'/subnetworks/nora-rag-subnet'
FIX = {
 'network': dict(name=C['NETWORK'], autoCreateSubnetworks=False),
 'subnet': dict(name=C['SUBNET'], region=R, network=N, ipCidrRange=C['SUBNET_CIDR']),
 'router': dict(name=C['ROUTER'], region=R, network=N),
 'nat': dict(name=C['NAT'], natIpAllocateOption='AUTO_ONLY', sourceSubnetworkIpRangesToNat='LIST_OF_SUBNETWORKS', subnetworks=[dict(name=S, sourceIpRangesToNat=['ALL_IP_RANGES'])]),
 'firewall': dict(name=C['NETWORK']+'-iap-ssh', network=N, direction='INGRESS', sourceRanges=['35.235.240.0/20'], targetTags=['nora-iap'], allowed=[dict(IPProtocol='tcp', ports=['22'])]),
 'sa': dict(name='projects/nora-rag-dev/serviceAccounts/'+cli.sa_email(C), email=cli.sa_email(C), disabled=False),
 'bucket': dict(name=C['BACKUP_BUCKET_NAME'], location='US-CENTRAL1', iamConfiguration=dict(uniformBucketLevelAccess=dict(enabled=True), publicAccessPrevention='enforced')),
 'disk': dict(name=C['DATA_DISK'], zone=Z, type=Z+'/diskTypes/pd-balanced', sizeGb='200'),
 'secret': dict(name='projects/12345/secrets/'+C['SECRET_NAME'], replication=dict(automatic={})),
 'boot': dict(name='boot', zone=Z, type=Z+'/diskTypes/pd-balanced', sizeGb='30', selfLink=Z+'/disks/boot', sourceImage='https://www.googleapis.com/compute/v1/projects/ubuntu-os-cloud/global/images/ubuntu-2404-noble-amd64-v20260901'),
 'vm': dict(name=C['VM_NAME'], zone=Z, machineType=Z+'/machineTypes/e2-standard-4', networkInterfaces=[dict(network=N, subnetwork=S)], serviceAccounts=[dict(email=cli.sa_email(C), scopes=['https://www.googleapis.com/auth/cloud-platform'])], tags=dict(items=['nora-iap']), metadata=dict(items=[dict(key='enable-oslogin', value='TRUE')]), disks=[dict(boot=True, source=Z+'/disks/boot'), dict(boot=False, source=Z+'/disks/'+C['DATA_DISK'], deviceName=C['DATA_DISK'], autoDelete=False, mode='READ_WRITE')])
}


class Fake:
    def __init__(self, existing=()):
        self.state = {k: copy.deepcopy(FIX[k]) for k in existing}
        self.calls = []
        self.fail = None
        setup = cli.Setup(C)
        self.ops = [o for stage in cli.STAGES for o in setup.resources(stage)]

    def __call__(self, cmd, **kwargs):
        self.calls.append(cmd)
        assert kwargs['shell'] is False
        if self.fail and self.fail(cmd):
            return subprocess.CompletedProcess(cmd, 1, '', 'SECRET_CANARY provider diagnostic')
        if cmd[1:3] == ['projects', 'describe']:
            data = dict(projectId=C['PROJECT_ID'], lifecycleState='ACTIVE')
        elif cmd[1:4] == ['billing', 'projects', 'describe']:
            data = dict(billingEnabled=True)
        elif cmd[1:3] == ['services', 'list']:
            data = []
        elif 'create' in cmd:
            op = next(o for o in self.ops if o.create == cmd)
            self.state[op.kind] = copy.deepcopy(FIX[op.kind])
            if op.kind == 'vm':
                self.state['boot'] = copy.deepcopy(FIX['boot'])
            data = self.state[op.kind]
        elif 'list' in cmd:
            matching = [o for o in self.ops if o.lookup == cmd and o.kind != 'nat']
            assert matching, cmd
            kind = matching[0].kind
            data = [copy.deepcopy(self.state[kind])] if kind in self.state else []
            if kind == 'router' and data:
                data[0]['nats'] = [copy.deepcopy(self.state['nat'])] if 'nat' in self.state else []
            if kind == 'disk' and 'boot' in self.state:
                data.append(copy.deepcopy(self.state['boot']))
        else:
            data = {}
        return subprocess.CompletedProcess(cmd, 0, json.dumps(data), '')


class ProvisioningTests(unittest.TestCase):
    def execute(self, fake, stage, apply=True):
        with contextlib.redirect_stdout(io.StringIO()):
            return cli.Setup(C, fake).execute(stage, apply)

    def test_preview_all_stages_never_calls_runner(self):
        def forbidden(*args, **kwargs):
            self.fail('Preview invoked a process')
        for stage in cli.STAGES:
            self.execute(forbidden, stage, False)

    def test_network_create_then_repeat_skips(self):
        fake = Fake()
        self.execute(fake, 'network')
        self.assertEqual(sum('create' in c for c in fake.calls), 5)
        fake.calls.clear()
        self.execute(fake, 'network')
        self.assertFalse(any('create' in c for c in fake.calls))

    def test_lookup_error_before_any_stage_mutation_and_no_stderr_leak(self):
        fake = Fake()
        fake.fail = lambda c: 'firewall-rules' in c
        with self.assertRaisesRegex(RuntimeError, 'exited 1') as error:
            self.execute(fake, 'network')
        self.assertNotIn('SECRET_CANARY', str(error.exception))
        self.assertFalse(any('create' in c for c in fake.calls))

    def test_all_resource_mismatches_rejected(self):
        changes = {'network': ('autoCreateSubnetworks', True), 'subnet': ('ipCidrRange', '10.43.0.0/24'), 'router': ('network', 'wrong'), 'nat': ('natIpAllocateOption', 'MANUAL_ONLY'), 'firewall': ('sourceRanges', ['0.0.0.0/0']), 'sa': ('disabled', True), 'bucket': ('location', 'EU'), 'disk': ('sizeGb', '20'), 'secret': ('replication', {'userManaged': {}}), 'vm': ('machineType', Z+'/machineTypes/e2-micro'), 'boot': ('sourceImage', 'debian')}
        for kind, (key, value) in changes.items():
            with self.subTest(kind=kind):
                cli.validate_resource(kind, FIX[kind], C)
                bad = copy.deepcopy(FIX[kind]); bad[key] = value
                with self.assertRaises(ValueError):
                    cli.validate_resource(kind, bad, C)

    def test_late_mismatch_prevents_earlier_creates(self):
        fake = Fake(['firewall'])
        fake.state['firewall']['sourceRanges'] = ['0.0.0.0/0']
        with self.assertRaises(ValueError):
            self.execute(fake, 'network')
        self.assertFalse(any('create' in c for c in fake.calls))

    def test_billing_disabled_stops(self):
        fake = Fake()
        def runner(cmd, **kw):
            if cmd[1:4] == ['billing', 'projects', 'describe']:
                return subprocess.CompletedProcess(cmd, 0, '{"billingEnabled": false}', '')
            return fake(cmd, **kw)
        with self.assertRaisesRegex(ValueError, 'billing'):
            self.execute(runner, 'network')
        self.assertFalse(any('create' in c for c in fake.calls))

    def test_selected_stage_identity_and_exact_iam(self):
        fake = Fake()
        self.execute(fake, 'identity')
        bindings = [c for c in fake.calls if 'add-iam-policy-binding' in c]
        self.assertEqual(len(bindings), 3)
        self.assertTrue(all('--member=user:'+C['OPERATOR_EMAIL'] in c for c in bindings))
        sa = next(c for c in bindings if '--role=roles/iam.serviceAccountUser' in c)
        self.assertEqual(sa[1:4], ['iam', 'service-accounts', 'add-iam-policy-binding'])
        self.assertIn(cli.sa_email(C), sa)
        self.assertFalse(any('instances' in c or 'buckets' in c for c in fake.calls))

    def test_storage_scope_and_zonal_disk(self):
        fake = Fake(['sa'])
        self.execute(fake, 'storage')
        disk = next(c for c in fake.calls if 'disks' in c and 'create' in c)
        self.assertIn('--zone=us-central1-a', disk)
        self.assertNotIn('--region=us-central1', disk)
        bucket = next(c for c in fake.calls if '--role=roles/storage.objectAdmin' in c)
        self.assertEqual(bucket[1:4], ['storage', 'buckets', 'add-iam-policy-binding'])
        self.assertIn('gs://'+C['BACKUP_BUCKET_NAME'], bucket)
        self.assertFalse(any('versions' in c or '--data-file' in ' '.join(c) for c in fake.calls))

    def test_vm_dependencies_and_private_image_flags(self):
        fake = Fake()
        with self.assertRaises(ValueError):
            self.execute(fake, 'vm')
        self.assertFalse(any('create' in c for c in fake.calls))
        fake = Fake([k for k in FIX if k not in ('vm', 'boot')])
        self.execute(fake, 'vm')
        create = next(c for c in fake.calls if 'create' in c)
        for flag in ['--no-address', '--image-family=ubuntu-2404-lts-amd64', '--image-project=ubuntu-os-cloud', '--boot-disk-size=30GB']:
            self.assertIn(flag, create)
        self.execute(fake, 'vm')  # includes existing boot-image check
        self.assertEqual(sum('create' in c for c in fake.calls), 1)

    def test_all_commands_explicit_project_account_and_no_destructive_actions(self):
        fake = Fake()
        for stage in cli.STAGES:
            self.execute(fake, stage)
        for c in fake.calls:
            self.assertIn('--project='+C['PROJECT_ID'], c)
            self.assertIn('--account='+C['OPERATOR_EMAIL'], c)
            self.assertFalse(set(c) & {'delete', 'update', 'set', 'ssh', 'scp', 'versions'})

    def test_invalid_json_stops(self):
        def fake(cmd, **kw):
            return subprocess.CompletedProcess(cmd, 0, 'not json', '')
        with self.assertRaisesRegex(RuntimeError, 'invalid JSON'):
            self.execute(fake, 'check')

    def test_cli_configuration_and_preservation(self):
        with tempfile.TemporaryDirectory() as d:
            core, extra = Path(d)/'core.env', Path(d)/'cli.env'
            core.write_text('\n'.join(k+'='+v for k,v in C.items() if k not in cli.KEYS))
            valid = '\n'.join(k+'='+C[k] for k in sorted(cli.KEYS))
            extra.write_text(valid)
            original = core.read_bytes()
            self.assertEqual(cli.configuration(core, extra), C)
            for bad in [valid+'\nNAT=duplicate', valid+'\nUNKNOWN=1', valid.replace('10.42.0.0/24', '999.1.1.1/24'), valid.replace(C['OPERATOR_EMAIL'], ''), valid.replace('nora-rag-net', 'bad;cmd')]:
                extra.write_text(bad)
                with self.assertRaises(ValueError):
                    cli.configuration(core, extra)
            self.assertEqual(core.read_bytes(), original)

    def test_existing_vm_with_public_address_is_rejected(self):
        fake = Fake(FIX)
        fake.state['vm']['networkInterfaces'][0]['accessConfigs'] = [{'natIP': '203.0.113.1'}]
        with self.assertRaisesRegex(ValueError, 'Existing vm differs'):
            self.execute(fake, 'vm')
        self.assertFalse(any('create' in c for c in fake.calls))

    def test_create_success_without_readback_stops_remaining_creates(self):
        fake = Fake()
        def runner(cmd, **kw):
            if 'create' in cmd:
                fake.calls.append(cmd)
                return subprocess.CompletedProcess(cmd, 0, '{}', '')
            return fake(cmd, **kw)
        with self.assertRaisesRegex(ValueError, 'not returned by readback'):
            self.execute(runner, 'network')
        self.assertEqual(sum('create' in c for c in fake.calls), 1)

    def test_entrypoint_requires_stage(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            cli.main([])


if __name__ == '__main__':
    unittest.main()
