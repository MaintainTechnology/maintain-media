"""Offline deployment failure-path tests. Every AWS subprocess is blocked or mocked."""

from __future__ import annotations

import copy
import importlib.util
import io
import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("deploy_session_under_test", Path(__file__).with_name("deploy_session.py"))
assert SPEC and SPEC.loader
deployment = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(deployment)

ACCOUNT = "052530979168"
OPERATOR_IP = "8.8.8.8"
INSTANCE_ARN = f"arn:aws:lightsail:{deployment.REGION}:{ACCOUNT}:Instance/11111111-1111-4111-8111-111111111111"


class DeploymentSessionTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(patch.stopall)
        patch.object(deployment.subprocess, "run", side_effect=AssertionError("Unmocked AWS subprocess is forbidden")).start()
        patch.object(deployment.time, "sleep").start()
        self.events = []
        patch.object(deployment, "emit", side_effect=self.events.append).start()
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.public_key = Path(self.directory.name) / "fixture.pub"
        self.public_key.write_text("ssh-rsa c3ludGhldGlj fixture-test\n", encoding="ascii")
        self.args = SimpleNamespace(aws="never-run-aws", profile="synthetic-profile", account=ACCOUNT,
                                    public_key=str(self.public_key), operator_ip=OPERATOR_IP)
        self.session = deployment.Session(self.args)

    def owned_user(self):
        return {"User": {"UserName": self.session.user, "Path": "/maintain-media/",
                         "Tags": [{"Key": "Project", "Value": deployment.PROJECT},
                                  {"Key": "DeploymentId", "Value": self.session.nonce}]}}

    def instance(self):
        return {"name": deployment.NAME, "arn": INSTANCE_ARN, "bundleId": deployment.BUNDLE,
                "blueprintId": deployment.BLUEPRINT, "location": {"regionName": deployment.REGION},
                "hardware": {"ramSizeInGb": 8, "cpuCount": 2}, "addOns": [],
                "tags": [{"key": "Project", "value": deployment.PROJECT},
                         {"key": "DeploymentId", "value": self.session.nonce}]}

    @staticmethod
    def firewall():
        return {"portStates": [{"state": "open", "fromPort": 22, "toPort": 22, "protocol": "tcp",
                                "cidrs": [OPERATOR_IP + "/32"], "ipv6Cidrs": [], "cidrListAliases": []}]}

    def test_uncertain_user_creation_is_reconciled_and_owned_identity_removed(self):
        calls = []

        def cloud(service, operation, params=None, **kwargs):
            calls.append((service, operation, params))
            if operation == "get-caller-identity":
                return {"Account": ACCOUNT}
            if operation == "get-account-plan-state":
                return {"accountPlanType": "FREE", "accountPlanStatus": "ACTIVE", "accountPlanRemainingCredits": {"amount": 100}}
            if operation == "create-user":
                raise deployment.AwsFailure("iam:create-user:OUTCOME_UNKNOWN")
            if operation == "get-user":
                return self.owned_user()
            if operation == "list-access-keys":
                return {"AccessKeyMetadata": []}
            if operation in {"put-user-policy", "delete-user-policy", "delete-user"}:
                return {}
            self.fail(f"Unexpected operation: {operation}")

        self.session.call = cloud
        with self.assertRaisesRegex(deployment.AwsFailure, "OUTCOME_UNKNOWN"):
            self.session.start()
        self.assertTrue(self.session.bootstrap_attempted)
        self.assertFalse(self.session.created_user)
        self.session.finish()
        self.assertIn("delete-user", [operation for _, operation, _ in calls])
        self.assertFalse(self.session.cleanup_failed)
        policies = [json.loads(params["PolicyDocument"]) for _, operation, params in calls if operation == "put-user-policy"]
        self.assertEqual(policies[0]["Statement"][0]["Effect"], "Deny")

    def test_unknown_created_access_key_is_discovered_and_deleted_after_deny(self):
        calls = []
        keys = [{"AccessKeyId": "synthetic-unknown-bootstrap-key"}]

        def cloud(service, operation, params=None, **kwargs):
            calls.append((operation, params))
            if operation == "get-caller-identity":
                return {"Account": ACCOUNT}
            if operation == "get-account-plan-state":
                return {"accountPlanType": "FREE", "accountPlanStatus": "ACTIVE", "accountPlanRemainingCredits": {"amount": 100}}
            if operation == "create-access-key":
                raise deployment.AwsFailure("iam:create-access-key:OUTCOME_UNKNOWN")
            if operation == "get-user":
                return self.owned_user()
            if operation == "list-access-keys":
                return {"AccessKeyMetadata": copy.deepcopy(keys)}
            if operation == "delete-access-key":
                self.assertEqual(params["AccessKeyId"], "synthetic-unknown-bootstrap-key")
                keys.clear()
                return {}
            if operation in {"create-user", "put-user-policy", "delete-user-policy", "delete-user"}:
                return {}
            self.fail(f"Unexpected operation: {operation}")

        self.session.call = cloud
        with self.assertRaisesRegex(deployment.AwsFailure, "OUTCOME_UNKNOWN"):
            self.session.start()
        self.assertIsNone(self.session.key_id)
        self.session.finish()
        deny_index = next(index for index, (operation, params) in enumerate(calls)
                          if operation == "put-user-policy" and json.loads(params["PolicyDocument"])["Statement"][0]["Effect"] == "Deny")
        delete_index = next(index for index, (operation, _) in enumerate(calls) if operation == "delete-access-key")
        self.assertLess(deny_index, delete_index)
        self.assertFalse(keys)
        self.assertFalse(self.session.cleanup_failed)

    def test_cleanup_never_mutates_another_sessions_identity_and_clears_memory(self):
        self.session.bootstrap_attempted = True
        self.session.temp_env = {"AWS_SECRET_ACCESS_KEY": "synthetic-secret"}
        self.session.private_values = ["synthetic-secret"]
        foreign = self.owned_user()
        foreign["User"]["Tags"][1]["Value"] = "another-session"
        operations = []

        def cloud(service, operation, params=None, **kwargs):
            operations.append(operation)
            self.assertEqual(operation, "get-user")
            return foreign

        self.session.call = cloud
        with self.assertRaisesRegex(deployment.AwsFailure, "ownership tag"):
            self.session.finish()
        self.assertEqual(operations, ["get-user"])
        self.assertEqual(self.session.temp_env, {})
        self.assertEqual(self.session.private_values, [])

    def test_failed_key_deletion_retains_deny_identity_and_reports_cleanup_failure(self):
        self.session.bootstrap_attempted = True
        self.session.temp_env = {"AWS_SECRET_ACCESS_KEY": "synthetic-secret"}
        self.session.private_values = ["synthetic-secret"]
        operations = []

        def cloud(service, operation, params=None, **kwargs):
            operations.append(operation)
            if operation == "get-user":
                return self.owned_user()
            if operation == "put-user-policy":
                self.assertEqual(json.loads(params["PolicyDocument"])["Statement"][0]["Effect"], "Deny")
                return {}
            if operation == "list-access-keys":
                return {"AccessKeyMetadata": [{"AccessKeyId": "synthetic-key"}]}
            if operation == "delete-access-key":
                raise deployment.AwsFailure("iam:delete-access-key:OUTCOME_UNKNOWN")
            if operation == "get-bundles":
                raise deployment.AwsFailure("lightsail:get-bundles:AccessDeniedException")
            self.fail(f"Unexpected operation: {operation}")

        self.session.call = cloud
        self.session.finish()
        self.assertLess(operations.index("put-user-policy"), operations.index("delete-access-key"))
        self.assertNotIn("delete-user-policy", operations)
        self.assertNotIn("delete-user", operations)
        self.assertTrue(self.session.cleanup_failed)
        self.assertEqual(self.session.temp_env, {})
        self.assertEqual(self.session.private_values, [])

    def test_creation_payload_is_single_approved_instance_and_policy_uses_returned_arn(self):
        calls = []

        def cloud(service, operation, params=None, **kwargs):
            calls.append((operation, params, kwargs))
            if operation == "get-instances":
                return {"instances": []}
            if operation == "get-instance":
                return {"instance": self.instance()}
            if operation == "get-instance-port-states":
                return self.firewall()
            if operation in {"import-key-pair", "create-instances", "put-user-policy", "put-instance-public-ports"}:
                return {}
            self.fail(f"Unexpected operation: {operation}")

        self.session.call = cloud
        self.session.create()
        imported = next(params for operation, params, _ in calls if operation == "import-key-pair")
        self.assertEqual(imported["publicKeyBase64"], self.public_key.read_text().strip())
        self.assertTrue(imported["publicKeyBase64"].startswith("ssh-rsa "))
        creates = [params for operation, params, _ in calls if operation == "create-instances"]
        self.assertEqual(len(creates), 1)
        self.assertEqual(creates[0]["instanceNames"], [deployment.NAME])
        self.assertEqual(creates[0]["bundleId"], "large_3_2")
        self.assertEqual(creates[0]["blueprintId"], "ubuntu_24_04")
        self.assertEqual(creates[0]["availabilityZone"], "ap-southeast-2a")
        self.assertNotIn("addOns", creates[0])
        reduced = next(json.loads(params["PolicyDocument"]) for operation, params, _ in calls if operation == "put-user-policy")
        scoped = next(statement for statement in reduced["Statement"] if statement["Sid"] == "OnlyCreatedInstance")
        self.assertEqual(scoped["Resource"], INSTANCE_ARN)
        self.assertNotIn("SingleControllerLaunch", [statement["Sid"] for statement in reduced["Statement"]])
        self.assertTrue(self.session.firewall_verified)
        with self.assertRaisesRegex(deployment.AwsFailure, "already attempted"):
            self.session.create()

    def test_uncertain_instance_response_reconciles_same_instance_without_second_creation(self):
        operations = []

        def cloud(service, operation, params=None, **kwargs):
            operations.append(operation)
            if operation == "get-instances":
                return {"instances": []}
            if operation == "create-instances":
                raise deployment.AwsFailure("lightsail:create-instances:OUTCOME_UNKNOWN")
            if operation == "get-instance":
                return {"instance": self.instance()}
            if operation == "get-instance-port-states":
                return self.firewall()
            if operation in {"import-key-pair", "put-user-policy", "put-instance-public-ports"}:
                return {}
            self.fail(f"Unexpected operation: {operation}")

        self.session.call = cloud
        self.session.create()
        self.assertEqual(operations.count("create-instances"), 1)
        self.assertTrue(self.session.created_instance)
        self.assertTrue(self.session.firewall_verified)
        self.assertLess(operations.index("put-user-policy"), operations.index("put-instance-public-ports"))

    def test_existing_instances_prevent_key_import_and_creation(self):
        operations = []

        def cloud(service, operation, params=None, **kwargs):
            operations.append(operation)
            return {"instances": [{"name": "existing-workload"}]}

        self.session.call = cloud
        with self.assertRaisesRegex(deployment.AwsFailure, "existing Sydney instances"):
            self.session.create()
        self.assertEqual(operations, ["get-instances"])

    def test_foreign_or_unapproved_instance_is_never_adopted(self):
        mutations = [
            {"arn": INSTANCE_ARN.replace(ACCOUNT, "111111111111")},
            {"location": {"regionName": "us-east-1"}},
            {"hardware": {"ramSizeInGb": 16, "cpuCount": 2}},
            {"addOns": [{"name": "AutoSnapshot", "status": "Enabled"}]},
            {"tags": [{"key": "Project", "value": deployment.PROJECT}, {"key": "DeploymentId", "value": "foreign"}]},
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                instance = {**self.instance(), **mutation}
                self.session.call = lambda *args, captured=instance, **kwargs: {"instance": captured}
                with self.assertRaisesRegex(deployment.AwsFailure, "does not match"):
                    self.session.status()
                self.assertIsNone(self.session.instance_arn)

    def test_firewall_rejects_extra_ports_public_cidrs_ipv6_and_stale_previous_success(self):
        bad_results = []
        extra_port = self.firewall()
        extra_port["portStates"].append({"state": "open", "fromPort": 80, "toPort": 80, "protocol": "tcp", "cidrs": ["0.0.0.0/0"]})
        bad_results.append(extra_port)
        for change in [{"cidrs": ["0.0.0.0/0"]}, {"ipv6Cidrs": ["::/0"]}, {"cidrListAliases": ["lightsail-connect"]}]:
            result = self.firewall()
            result["portStates"][0].update(change)
            bad_results.append(result)
        for result in bad_results:
            with self.subTest(result=result):
                self.session.instance_arn = INSTANCE_ARN
                self.session.firewall_verified = True
                self.session.call = lambda service, operation, *args, captured=result, **kwargs: captured if operation == "get-instance-port-states" else {}
                with self.assertRaisesRegex(deployment.AwsFailure, "firewall readback"):
                    self.session.ports()
                self.assertFalse(self.session.firewall_verified)

    def test_policy_has_expiry_region_and_bounded_creation_tag_keys(self):
        policy = self.session.policy(create=True)
        for statement in policy["Statement"]:
            self.assertEqual(statement["Effect"], "Allow")
            self.assertEqual(statement["Condition"]["StringEquals"]["aws:RequestedRegion"], deployment.REGION)
            self.assertIn("aws:CurrentTime", statement["Condition"]["DateLessThan"])
        create = next(statement for statement in policy["Statement"] if statement["Sid"] == "SingleControllerLaunch")
        self.assertEqual(create["Condition"]["ForAllValues:StringEquals"]["aws:TagKeys"], ["Project", "DeploymentId"])
        self.assertEqual(create["Resource"], "*")
        self.assertNotIn("OnlyCreatedInstance", [statement["Sid"] for statement in policy["Statement"]])

    def test_cli_timeout_error_cannot_echo_captured_credentials(self):
        self.session.temp_env = {"AWS_SECRET_ACCESS_KEY": "synthetic-private-key", "AWS_SESSION_TOKEN": "synthetic-private-token"}
        with patch.object(deployment.subprocess, "run", side_effect=subprocess.TimeoutExpired(["aws"], 90, output="synthetic-private-token")), \
                self.assertRaisesRegex(deployment.AwsFailure, "^lightsail:get-bundles:OUTCOME_UNKNOWN$"):
            self.session.call("lightsail", "get-bundles")

    def test_main_reports_unresolved_creation_as_failure_even_without_known_instance(self):
        def unresolved(session):
            session.create_attempted = True
            raise deployment.AwsFailure("Creation outcome remains unknown")

        argv = ["deploy_session.py", "--aws", "never-run-aws", "--profile", "synthetic",
                "--account", ACCOUNT, "--public-key", str(self.public_key), "--operator-ip", OPERATOR_IP]
        with patch.object(deployment.sys, "argv", argv), patch.object(deployment.sys, "stdin", io.StringIO("create\nfinish\n")), \
                patch.object(deployment.Session, "start"), patch.object(deployment.Session, "create", unresolved), \
                patch.object(deployment.Session, "finish"), redirect_stdout(io.StringIO()):
            self.assertEqual(deployment.main(), 1)


if __name__ == "__main__":
    unittest.main()
