"""Bounded, interactive Lightsail deployment with credentials held only in memory.

Root is used only for account verification and a disposable IAM bootstrap.
The dedicated user has no password; its one bootstrap access key is deleted as
soon as STS issues temporary credentials. No credential value is printed/saved.
The protocol accepts create/finalize/status/ports/host-keys/finish, not arbitrary
AWS commands. This controller never upgrades the account or enables add-ons.
"""

from __future__ import annotations

import argparse
import datetime as dt
import ipaddress
import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

REGION = "ap-southeast-2"
NAME = "maintain-media-abn-engine"
BUNDLE = "large_3_2"
BLUEPRINT = "ubuntu_24_04"
PROJECT = "abn-lead-gen"
POLICY_NAME = "AbnSydneyTemporaryDeployment"


class AwsFailure(RuntimeError):
    pass


def emit(value):
    print(json.dumps(value), flush=True)


class Session:
    def __init__(self, args):
        self.args = args
        self.region = REGION
        self.nonce = str(uuid.uuid4())
        self.user = "abn-deploy-" + dt.datetime.now(dt.UTC).strftime("%Y%m%d%H%M%S") + "-" + self.nonce[:6]
        self.created_user = False
        self.bootstrap_attempted = False
        self.firewall_verified = False
        self.cleanup_failed = False
        self.key_id = None
        self.temp_env = None
        self.created_instance = False
        self.create_attempted = False
        self.instance_arn = None
        self.private_values = []
        self.end = (dt.datetime.now(dt.UTC) + dt.timedelta(hours=2)).isoformat()
        self.create_end = (dt.datetime.now(dt.UTC) + dt.timedelta(minutes=15)).isoformat()
        self.base_env = dict(os.environ)
        for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "AWS_SECURITY_TOKEN", "AWS_PROFILE", "AWS_DEFAULT_PROFILE"):
            self.base_env.pop(name, None)
        self.base_env["AWS_MAX_ATTEMPTS"] = "2"
        self.base_env["AWS_PAGER"] = ""

    def call(self, service, operation, params=None, *, owner=False, region=REGION, query=None, env=None):
        command = [self.args.aws, service, operation, "--region", region,
                   "--output", "json", "--no-cli-pager", "--cli-connect-timeout", "10",
                   "--cli-read-timeout", "25"]
        if owner:
            command += ["--profile", self.args.profile]
        if params:
            command += ["--cli-input-json", json.dumps(params)]
        if query:
            command += ["--query", query]
        selected_env = env if env is not None else (self.base_env if owner else self.temp_env)
        if selected_env is None:
            raise AwsFailure("Temporary deployment credentials are not initialized")
        try:
            result = subprocess.run(command, env=selected_env, capture_output=True, text=True, timeout=90, check=False)
        except subprocess.TimeoutExpired:
            raise AwsFailure(f"{service}:{operation}:OUTCOME_UNKNOWN") from None
        if result.returncode:
            # Errors may contain identifiers, but never echo arbitrary CLI output.
            match = re.search(r"An error occurred \(([^)]+)\)", result.stderr)
            code = match.group(1) if match else "CLI_FAILURE"
            # Report only fixed, non-secret diagnostic labels, never AWS text.
            markers = [label for phrase, label in (
                ("public key", "PUBLIC_KEY"), ("base64", "BASE64"),
                ("ssh-rsa", "SSH_RSA"), ("2048", "RSA_2048"), ("4096", "RSA_4096"),
                ("key pair name", "KEY_PAIR_NAME"), ("keypairname", "KEY_PAIR_NAME"),
                ("free plan", "FREE_PLAN"), ("paid plan", "PAID_PLAN"),
                ("upgrade", "UPGRADE"), ("not supported", "UNSUPPORTED"),
                ("invalid format", "INVALID_FORMAT"), ("length", "LENGTH"),
                ("account verification", "ACCOUNT_VERIFICATION"),
            ) if phrase in result.stderr.lower()]
            suffix = ":" + ",".join(dict.fromkeys(markers)) if markers else ""
            raise AwsFailure(f"{service}:{operation}:{code}{suffix}")
        return json.loads(result.stdout) if result.stdout.strip() else {}

    def policy(self, create=False):
        condition = {"StringEquals": {"aws:RequestedRegion": REGION}, "DateLessThan": {"aws:CurrentTime": self.end}}
        statements = [{"Sid": "SydneyReadOnly", "Effect": "Allow", "Action": [
            "lightsail:GetBundles", "lightsail:GetBlueprints", "lightsail:GetRegions",
            "lightsail:GetInstances", "lightsail:GetInstance", "lightsail:GetInstanceState",
            "lightsail:GetInstancePortStates", "lightsail:GetOperation", "lightsail:GetOperationsForResource"
        ], "Resource": "*", "Condition": condition}]
        if create:
            create_condition = {"StringEquals": {"aws:RequestedRegion": REGION, "aws:RequestTag/Project": PROJECT},
                                "DateLessThan": {"aws:CurrentTime": self.create_end},
                                "ForAllValues:StringEquals": {"aws:TagKeys": ["Project", "DeploymentId"]}}
            statements += [
                {"Sid": "SingleControllerLaunch", "Effect": "Allow", "Action": "lightsail:CreateInstances",
                 "Resource": "*", "Condition": create_condition},
                {"Sid": "LaunchTag", "Effect": "Allow", "Action": "lightsail:TagResource",
                 "Resource": f"arn:aws:lightsail:{REGION}:{self.args.account}:Instance/*", "Condition": create_condition},
                {"Sid": "ImportPublicSshKey", "Effect": "Allow", "Action": "lightsail:ImportKeyPair",
                 "Resource": "*", "Condition": {"StringEquals": {"aws:RequestedRegion": REGION},
                                                "DateLessThan": {"aws:CurrentTime": self.create_end}}}
            ]
        if self.instance_arn:
            statements.append({"Sid": "OnlyCreatedInstance", "Effect": "Allow", "Action": [
                "lightsail:PutInstancePublicPorts", "lightsail:GetInstanceAccessDetails", "lightsail:UpdateInstanceMetadataOptions"
            ], "Resource": self.instance_arn, "Condition": condition})
        return {"Version": "2012-10-17", "Statement": statements}

    def put_policy(self, create=False):
        self.call("iam", "put-user-policy", {"UserName": self.user, "PolicyName": POLICY_NAME,
                  "PolicyDocument": json.dumps(self.policy(create))}, owner=True)

    def start(self):
        identity = self.call("sts", "get-caller-identity", owner=True)
        if identity.get("Account") != self.args.account:
            raise AwsFailure("Account does not match approved target")
        plan = self.call("freetier", "get-account-plan-state", owner=True, region="us-east-1")
        if plan.get("accountPlanType") != "FREE" or plan.get("accountPlanStatus") != "ACTIVE":
            raise AwsFailure("Account is not on the approved active Free plan")
        if plan.get("accountPlanRemainingCredits", {}).get("amount", 0) <= 0:
            raise AwsFailure("No Free plan credit remains")
        self.bootstrap_attempted = True
        self.call("iam", "create-user", {"UserName": self.user, "Path": "/maintain-media/",
                  "Tags": [{"Key": "Project", "Value": PROJECT}, {"Key": "DeploymentId", "Value": self.nonce}]}, owner=True)
        self.created_user = True
        self.put_policy(create=True)
        key = self.call("iam", "create-access-key", {"UserName": self.user}, owner=True)["AccessKey"]
        self.key_id = key["AccessKeyId"]
        self.private_values += [key["SecretAccessKey"]]
        bootstrap_env = dict(self.base_env, AWS_ACCESS_KEY_ID=key["AccessKeyId"], AWS_SECRET_ACCESS_KEY=key["SecretAccessKey"])
        try:
            for attempt in range(6):
                try:
                    credentials = self.call("sts", "get-session-token", {"DurationSeconds": 7200}, env=bootstrap_env)["Credentials"]
                    break
                except AwsFailure:
                    if attempt == 5:
                        raise
                    time.sleep(3)
        finally:
            self.call("iam", "delete-access-key", {"UserName": self.user, "AccessKeyId": self.key_id}, owner=True)
            self.key_id = None
            bootstrap_env.clear()
            key.clear()
        self.private_values += [credentials["SecretAccessKey"], credentials["SessionToken"]]
        self.temp_env = dict(self.base_env, AWS_ACCESS_KEY_ID=credentials["AccessKeyId"],
                             AWS_SECRET_ACCESS_KEY=credentials["SecretAccessKey"], AWS_SESSION_TOKEN=credentials["SessionToken"])
        credentials.clear()
        identity = self.call("sts", "get-caller-identity")
        expected_arn = f"arn:aws:iam::{self.args.account}:user/maintain-media/{self.user}"
        if identity.get("Arn") != expected_arn:
            raise AwsFailure("Temporary identity does not match disposable deployment user")
        bundles = self.call("lightsail", "get-bundles")["bundles"]
        candidate = next((b for b in bundles if b["bundleId"] == BUNDLE and b.get("isActive")), None)
        if not candidate or candidate["price"] != 44 or candidate["ramSizeInGb"] != 8:
            raise AwsFailure("Approved bundle/price is no longer available")
        emit({"event": "session_ready", "user": self.user, "region": REGION, "credit_usd": plan["accountPlanRemainingCredits"]["amount"],
              "temporary_credentials_expire": self.end, "bootstrap_access_key_deleted": True, "base_monthly_usd": 44})

    def status(self):
        instance = self.call("lightsail", "get-instance", {"instanceName": NAME})["instance"]
        expected_arn_prefix = f"arn:aws:lightsail:{REGION}:{self.args.account}:Instance/"
        tags = {tag["key"]: tag["value"] for tag in instance.get("tags", [])}
        if (instance.get("name") != NAME or instance.get("bundleId") != BUNDLE
                or instance.get("blueprintId") != BLUEPRINT
                or instance.get("location", {}).get("regionName") != REGION
                or not instance.get("arn", "").startswith(expected_arn_prefix)
                or tags.get("Project") != PROJECT or tags.get("DeploymentId") != self.nonce
                or instance.get("hardware", {}).get("ramSizeInGb") != 8
                or instance.get("hardware", {}).get("cpuCount") != 2
                or any(a.get("status") != "Disabled" for a in instance.get("addOns", []))):
            raise AwsFailure("Named instance does not match approved bundle/blueprint")
        self.instance_arn = instance["arn"]
        return {k: instance.get(k) for k in ("name", "arn", "state", "location", "bundleId", "blueprintId", "publicIpAddress", "privateIpAddress", "hardware", "tags", "addOns")}

    def create(self):
        if self.create_attempted:
            raise AwsFailure("Creation was already attempted; inspect the same instance instead")
        if self.call("lightsail", "get-instances").get("instances"):
            raise AwsFailure("Account has existing Sydney instances; refusing a fresh-account launch")
        public_key = Path(self.args.public_key).read_text(encoding="ascii").strip()
        if not public_key.startswith("ssh-rsa "):
            raise AwsFailure("Expected a separately generated RSA public key")
        key_name = self.user + "-ssh"
        # Despite this API field's name, Lightsail expects the OpenSSH line;
        # the RSA material inside that line is already base64 encoded.
        self.call("lightsail", "import-key-pair", {"keyPairName": key_name,
                  "publicKeyBase64": public_key})
        self.create_attempted = True
        payload = {"instanceNames": [NAME], "availabilityZone": REGION + "a", "blueprintId": BLUEPRINT,
                   "bundleId": BUNDLE, "keyPairName": key_name, "ipAddressType": "ipv4",
                   "tags": [{"key": "Project", "value": PROJECT}, {"key": "DeploymentId", "value": self.nonce}],
                   "userData": "#cloud-config\nssh_pwauth: false\ndisable_root: true\n"}
        try:
            result = self.call("lightsail", "create-instances", payload)
            self.created_instance = True
            emit({"event": "create_accepted", "operations": result.get("operations", [])})
        except AwsFailure as error:
            emit({"event": "create_response_uncertain", "error": str(error), "next": "Inspect only the same name; never create a replacement"})
        self.finalize()

    def finalize(self):
        if not self.create_attempted:
            raise AwsFailure("No creation attempt to finalize")
        for attempt in range(30):
            try:
                instance = self.status()
                self.created_instance = True
                break
            except AwsFailure:
                if attempt == 29:
                    self.put_policy(create=False)
                    raise
                if attempt % 5 == 0:
                    emit({"event": "waiting_for_instance_reconciliation", "instance_name": NAME})
                time.sleep(3)
        self.put_policy(create=False)
        emit({"event": "creation_permissions_removed", "instance": instance})
        self.ports()

    def ports(self):
        self.firewall_verified = False
        if not self.instance_arn:
            raise AwsFailure("Instance ARN has not been verified")
        self.call("lightsail", "put-instance-public-ports", {"instanceName": NAME, "portInfos": [
            {"fromPort": 22, "toPort": 22, "protocol": "tcp", "cidrs": [self.args.operator_ip + "/32"], "ipv6Cidrs": []}
        ]})
        result = self.call("lightsail", "get-instance-port-states", {"instanceName": NAME})
        opened = [p for p in result.get("portStates", []) if p.get("state", "").lower() == "open"]
        if (len(opened) != 1 or opened[0].get("fromPort") != 22 or opened[0].get("toPort") != 22
                or opened[0].get("protocol") != "tcp"
                or opened[0].get("cidrs") != [self.args.operator_ip + "/32"]
                or opened[0].get("ipv6Cidrs") or opened[0].get("cidrListAliases")):
            raise AwsFailure("AWS firewall readback did not match only operator IPv4/32 on TCP22")
        emit({"event": "firewall_verified", "ports": result})
        self.firewall_verified = True

    def finish(self):
        try:
            self._finish()
        finally:
            if self.temp_env:
                self.temp_env.clear()
            self.private_values.clear()

    def _finish(self):
        # Reconcile uncertain create-user/create-key outcomes using a unique tag.
        # No other IAM identity or its access keys may be touched by cleanup.
        if self.bootstrap_attempted:
            try:
                user = self.call("iam", "get-user", {"UserName": self.user}, owner=True)["User"]
            except AwsFailure as error:
                if "NoSuchEntity" in str(error):
                    return
                raise
            tags = {tag["Key"]: tag["Value"] for tag in user.get("Tags", [])}
            if user.get("Path") != "/maintain-media/" or tags.get("DeploymentId") != self.nonce:
                raise AwsFailure("Cleanup refuses an IAM user without this session's ownership tag")
            errors = []
            deny_installed = False
            try:
                self.call("iam", "put-user-policy", {"UserName": self.user, "PolicyName": POLICY_NAME,
                          "PolicyDocument": json.dumps({"Version": "2012-10-17", "Statement": [{"Effect": "Deny", "Action": "*", "Resource": "*"}]})}, owner=True)
                deny_installed = True
            except AwsFailure as error:
                errors.append(str(error))
            keys_removed = False
            try:
                keys = self.call("iam", "list-access-keys", {"UserName": self.user}, owner=True)["AccessKeyMetadata"]
                for key in keys:
                    try:
                        self.call("iam", "delete-access-key", {"UserName": self.user, "AccessKeyId": key["AccessKeyId"]}, owner=True)
                    except AwsFailure as error:
                        errors.append(str(error))
                keys_removed = not self.call("iam", "list-access-keys", {"UserName": self.user}, owner=True)["AccessKeyMetadata"]
            except AwsFailure as error:
                errors.append(str(error))
            revoked = False
            if self.temp_env and deny_installed:
                for _ in range(10):
                    try:
                        self.call("lightsail", "get-bundles")
                    except AwsFailure as error:
                        if "AccessDenied" in str(error) or "UnrecognizedClient" in str(error):
                            revoked = True
                            break
                        errors.append(str(error))
                        break
                    time.sleep(3)
            if keys_removed and (revoked or not self.temp_env):
                try:
                    self.call("iam", "delete-user-policy", {"UserName": self.user, "PolicyName": POLICY_NAME}, owner=True)
                    self.call("iam", "delete-user", {"UserName": self.user}, owner=True)
                    self.created_user = False
                    emit({"event": "deployment_identity_removed", "revocation_probe_denied": revoked})
                except AwsFailure as error:
                    errors.append(str(error))
            else:
                errors.append("Revocation or access-key deletion not verified; retain deny policy")
            if errors:
                self.cleanup_failed = True
                emit({"cleanup_required": self.user, "errors": errors, "deny_policy_installed": deny_installed})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--aws", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--account", required=True)
    parser.add_argument("--public-key", required=True)
    parser.add_argument("--operator-ip", required=True)
    args = parser.parse_args()
    if not ipaddress.IPv4Address(args.operator_ip).is_global:
        raise SystemExit("Operator IP must be a public IPv4 address")
    if not re.fullmatch(r"\d{12}", args.account) or not args.public_key.endswith(".pub"):
        raise SystemExit("Invalid account ID or public key path")
    session = Session(args)
    try:
        session.start()
        for line in sys.stdin:
            command = line.strip()
            try:
                if command == "create":
                    session.create()
                elif command == "status":
                    emit({"event": "instance_status", "instance": session.status()})
                elif command == "finalize":
                    session.finalize()
                elif command == "ports":
                    session.ports()
                elif command == "host-keys":
                    emit({"event": "host_keys", "keys": session.call("lightsail", "get-instance-access-details",
                         {"instanceName": NAME, "protocol": "ssh"}, query="accessDetails.hostKeys")})
                elif command == "finish":
                    break
                else:
                    emit({"error": "Unknown operation"})
            except AwsFailure as error:
                emit({"error": str(error)})
    except AwsFailure as error:
        emit({"error": str(error)})
        return 1
    finally:
        try:
            session.finish()
        except (AwsFailure, subprocess.TimeoutExpired) as error:
            session.cleanup_failed = True
            emit({"cleanup_required": session.user, "error_type": type(error).__name__, "policy_expires": session.end})
    return 1 if session.cleanup_failed or (session.create_attempted and not session.firewall_verified) else 0


if __name__ == "__main__":
    raise SystemExit(main())
