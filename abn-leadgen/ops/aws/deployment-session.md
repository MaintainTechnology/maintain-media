# Approved one-server AWS deployment session

The owner's server-credit approval is recorded in
`../acceptance/aws/deployment-approval.json`. Do not ask for the same approval
again. Authentication may need renewal independently of that approval.

`deploy_session.py` creates a disposable IAM identity through the explicitly
selected owner profile, then uses a restricted temporary session for Lightsail.
The owner profile is used only for account verification and IAM bootstrap/cleanup.
The controller verifies the expected account, active Free plan, positive credits
and the active US$44/month `large_3_2` bundle before admitting deployment.

The fixed request creates one `maintain-media-abn-engine` instance in Sydney
`ap-southeast-2a`, Ubuntu 24.04, 8GB RAM, 2vCPU and 160GB disk, IPv4 only, with no
add-ons. A named instance or other existing Sydney instance stops a fresh launch.
The controller does not upgrade plans, provision backups, create databases or
enable the lead engine. An AWS account or plan refusal must be reported; do not
work around it by upgrading the plan, increasing the bundle or creating another
instance.

## Credentials and bounds

An IAM bootstrap access key is generated into process memory solely to obtain
two-hour STS credentials. The bootstrap key is deleted immediately. A successful
Lightsail read after deletion verifies that the temporary session remains usable.
No AWS key, token or password is stored in the repository, command arguments or
tool output. The IAM user has no console password. Creation permissions expire
after 15 minutes and all initial permissions after two hours.

IAM cannot restrict Lightsail creation by bundle, instance name or quantity; the
fixed controller request and single-attempt guard enforce those limits. After
creation, IAM permissions are narrowed to the returned instance ARN, and AWS
network rules are replaced with only TCP22 from the operator's current IPv4 /32.
Readback must match that exact firewall before it is called verified.

Use a task-specific RSA public SSH key; keep the private counterpart in a
restricted local folder outside the checkout. On this Windows machine the
prepared key is under `%LOCALAPPDATA%\MaintainMedia\aws\keys\` and the verified
public fingerprint is `SHA256:HOlO8mkxP0JsGXDEbeNYAhOhDX4TgLGYYc7CgAsD/p0`.
Only the public key is uploaded. Confirm the current operator IPv4 before launch.

## Operator invocation

From `abn-leadgen`, after renewing the browser login when required:

```powershell
uv run --frozen python ops/aws/deploy_session.py --aws "C:\Users\dalig\AppData\Local\Programs\Amazon\AWSCLIV2\aws.exe" --profile maintain-media-deploy --account ACCOUNT_ID --public-key PUBLIC_KEY_PATH.pub --operator-ip CURRENT_PUBLIC_IPV4
```

Replace the account ID with the verified account ending `9168`; the AWS account
ID is an identifier, not a credential. This is an interactive process. Wait for
`session_ready`, then send one operation per line:

- `create`: one approved creation attempt, permission reduction and firewall.
- `status`: verify the same named instance's account, region, tags and hardware.
- `finalize`: reconcile that same attempt and finish permission/firewall steps
  after an uncertain result. Never create a replacement under another name.
- `ports`: reapply and verify only the operator SSH rule.
- `host-keys`: retrieve only public SSH host keys through the trusted AWS API.
  Use those to establish SSH host trust when available. AWS documents this field
  as optional. If it is empty, reconfirm the instance ARN and current IP, then
  make one read-only SSH connection with `StrictHostKeyChecking=accept-new`,
  saving the key in a dedicated persistent `known_hosts` file. Record its SHA256
  fingerprint and this trust-on-first-use limitation. All later connections must
  use `StrictHostKeyChecking=yes`; never erase a conflicting key automatically.
- `finish`: deny/revoke the temporary user's permissions, delete any owned
  bootstrap keys and remove the IAM user. Keep the provisioned server.

Always finish or close stdin normally so cleanup runs. The script reconciles
uncertain IAM user/key creation using a unique ownership tag. `cleanup_required`
or a nonzero exit requires verification and cleanup of that exact owned identity;
do not mistake an expired local process for credential revocation. Never read or
print cached AWS login files to repair authentication.

The host foundation in `README.md` is a separate, reviewed stage. Copy only its
non-secret scripts, verify their hashes, apply over the approved SSH connection
and retain the real verifier receipt and second-SSH-login evidence. Application
installation and the existing live release gates still follow that foundation.

## Local checks

```powershell
uv run --frozen pytest ops/aws/test_deploy_session.py ops/aws/test_host_bootstrap.py -q
uv run --frozen ruff check ops/aws
```

These tests mock AWS/OS calls. They cannot prove Free-plan provisioning
eligibility, IAM propagation, SSH connectivity or an installed Linux host.

References: [AWS optional host keys](https://docs.aws.amazon.com/lightsail/2016-11-28/api-reference/API_InstanceAccessDetails.html)
and [OpenSSH host-key checking](https://man.openbsd.org/ssh_config#StrictHostKeyChecking).
