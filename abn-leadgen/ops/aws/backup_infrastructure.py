"""Exact one-bucket backup plan; default entry point performs no provider operations."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

ACCOUNT = "052530979168"
REGION = "ap-southeast-2"
DEPLOYMENT = "983c39eb-aaf2-4fb5-81af-d39d29de9568"
BUCKET = "maintain-media-abn-backup-052530979168-983c39eb"
PREFIX = f"abn-backup/{DEPLOYMENT}/"
USER = "abn-backup-publisher-983c39eb"
USER_PATH = "/maintain-media/backup/"
USER_ARN = f"arn:aws:iam::{ACCOUNT}:user{USER_PATH}{USER}"
BUCKET_ARN = f"arn:aws:s3:::{BUCKET}"
OBJECT_ARN = BUCKET_ARN + "/" + PREFIX + "*"
MAXIMUM_BYTES = 100_000_000_000
TAGS = {"Project": "abn-lead-gen", "Purpose": "private-backup", "DeploymentId": DEPLOYMENT}
BUCKET_READ = ["s3:GetBucketLocation", "s3:GetBucketPublicAccessBlock", "s3:GetBucketPolicyStatus",
               "s3:GetBucketVersioning", "s3:GetLifecycleConfiguration"]


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def publisher_policy():
    conditions = {"StringEquals": {"aws:RequestedRegion": REGION}, "Bool": {"aws:SecureTransport": "true"}}
    return {"Version": "2012-10-17", "Statement": [
        {"Sid": "VerifyOnlyApprovedBucket", "Effect": "Allow", "Action": BUCKET_READ,
         "Resource": BUCKET_ARN, "Condition": conditions},
        {"Sid": "ListOnlyDeploymentPrefix", "Effect": "Allow", "Action": "s3:ListBucket", "Resource": BUCKET_ARN,
         "Condition": {**conditions, "StringLike": {"s3:prefix": [PREFIX, PREFIX + "*"]}}},
        {"Sid": "OnlyEncryptedBackupObjects", "Effect": "Allow", "Action": ["s3:GetObject", "s3:DeleteObject"],
         "Resource": OBJECT_ARN, "Condition": conditions},
        {"Sid": "CreateOnlyEncryptedObjects", "Effect": "Allow", "Action": "s3:PutObject", "Resource": OBJECT_ARN,
         "Condition": {**conditions, "StringEquals": {"aws:RequestedRegion": REGION,
             "s3:x-amz-server-side-encryption": "AES256", "s3:if-none-match": "*"}}},
    ]}


def bootstrap_policy(expires_at: datetime):
    now = datetime.now(UTC)
    if expires_at.tzinfo is None or not now < expires_at <= now + timedelta(minutes=30):
        raise ValueError("BACKUP_BOOTSTRAP_MAXIMUM_THIRTY_MINUTES")
    condition = {"StringEquals": {"aws:RequestedRegion": REGION},
                 "DateLessThan": {"aws:CurrentTime": expires_at.isoformat()},
                 "Bool": {"aws:SecureTransport": "true"}}
    return {"Version": "2012-10-17", "Statement": [
        {"Sid": "CreateOneSydneyBucket", "Effect": "Allow", "Action": "s3:CreateBucket", "Resource": BUCKET_ARN,
         "Condition": {**condition, "StringEquals": {"aws:RequestedRegion": REGION, "s3:LocationConstraint": REGION}}},
        {"Sid": "ConfigureOnlyThatBucket", "Effect": "Allow", "Resource": BUCKET_ARN, "Condition": condition,
         "Action": BUCKET_READ + ["s3:ListBucket", "s3:GetBucketTagging", "s3:GetBucketPolicy", "s3:GetEncryptionConfiguration",
             "s3:GetBucketOwnershipControls", "s3:PutBucketPublicAccessBlock", "s3:PutBucketOwnershipControls",
             "s3:PutEncryptionConfiguration", "s3:PutBucketPolicy", "s3:PutLifecycleConfiguration", "s3:PutBucketTagging"]},
    ]}


def bucket_configuration():
    return {
        "create": {"Bucket": BUCKET, "CreateBucketConfiguration": {"LocationConstraint": REGION},
                   "ObjectOwnership": "BucketOwnerEnforced"},
        "public_access_block": {"BlockPublicAcls": True, "IgnorePublicAcls": True,
                                "BlockPublicPolicy": True, "RestrictPublicBuckets": True},
        "ownership_controls": {"Rules": [{"ObjectOwnership": "BucketOwnerEnforced"}]},
        "encryption": {"Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]},
        "lifecycle": {"Rules": [{"ID": "abr-owned-backup-expiry-34-days", "Status": "Enabled",
            "Filter": {"Prefix": PREFIX}, "Expiration": {"Days": 34}}]},
        "tagging": {"TagSet": [{"Key": key, "Value": value} for key, value in TAGS.items()]},
        "bucket_policy": {"Version": "2012-10-17", "Statement": [{"Sid": "DenyInsecureTransport", "Effect": "Deny",
            "Principal": "*", "Action": "s3:*", "Resource": [BUCKET_ARN, BUCKET_ARN + "/*"],
            "Condition": {"Bool": {"aws:SecureTransport": "false", "aws:PrincipalIsAWSService": "false"}}}]},
        "versioning": "never_enabled; no PutBucketVersioning operation permitted",
    }


def plan():
    return {"schema": "abr-one-sydney-backup-infrastructure-v1", "account_id": ACCOUNT, "region": REGION,
        "deployment_id": DEPLOYMENT, "instance_arn": f"arn:aws:lightsail:{REGION}:{ACCOUNT}:Instance/2ae0d8ef-49c6-4295-80ef-8fa9ce0235b6",
        "bucket": BUCKET, "prefix": PREFIX, "maximum_bytes": MAXIMUM_BYTES, "monthly_budget_usd": 5,
        "expected_storage_at_cap_usd": 2.50, "single_object_maximum_bytes": 4 * 1024**3,
        "schedule_proposal_not_installed": {"backup_seconds": 86400, "ledger_seconds": 240,
            "ledger_after_restriction_commit": True, "expiry_seconds": 43200},
        "additional_servers": 0, "paid_private_ca": False, "replication": False, "public_access": False,
        "status": "budget_approval_required", "runtime_capabilities_enabled": [], "release_approvals_created": False,
        "publisher": {"user_name": USER, "path": USER_PATH, "arn": USER_ARN, "console_password": False,
                      "active_keys_maximum": 1, "tags": TAGS, "policy": publisher_policy()},
        "bucket_configuration": bucket_configuration(), "bootstrap_maximum_minutes": 30,
        "bootstrap_owner_use": "STS identity verification and IAM creation/revocation only; S3 uses temporary limited credentials",
        "secret_custody": "new current-user DPAPI escrow; only scoped IAM credential/public recipient delivered via pinned SSH stdin",
        "host_directory": "/etc/abr-engine/backup", "backup_private_key_on_host": False,
        "activation": "not installed or enabled by planning; collection/retention/backup gates remain unchanged",
        "cost_limit_type": "application storage cap and operator cost review; AWS billing has no automatic hard stop"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    document = plan()
    content = canonical(document)
    if args.output:
        if not args.output.is_absolute() or not args.output.parent.is_dir() or args.output.parent.resolve() != args.output.parent:
            raise SystemExit("Absolute existing ordinary output directory required")
        with args.output.open("xb") as stream:
            stream.write(content)
    print(json.dumps({"status": "review_only", "provider_operations": 0, "bucket": BUCKET,
                      "monthly_budget_usd": 5, "plan_sha256": hashlib.sha256(content).hexdigest()}))


if __name__ == "__main__":
    main()
