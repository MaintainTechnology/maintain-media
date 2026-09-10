"""Open only web TLS/redirect ports on the already-approved Sydney engine.

Reuses the reviewed short-lived IAM bootstrap/cleanup. Never creates a server,
changes a bundle, purchases add-ons, or uses the owner identity for deployment.
"""
import argparse
import ipaddress

from deploy_session import NAME, REGION, AwsFailure, Session, emit

ACCOUNT = "052530979168"
INSTANCE_ARN = "arn:aws:lightsail:ap-southeast-2:052530979168:Instance/2ae0d8ef-49c6-4295-80ef-8fa9ce0235b6"
INSTANCE_IP = "3.104.119.142"
DEPLOYMENT = "983c39eb-aaf2-4fb5-81af-d39d29de9568"


class HttpsSession(Session):
    def policy(self, create=False):
        condition = {"StringEquals": {"aws:RequestedRegion": REGION},
                     "DateLessThan": {"aws:CurrentTime": self.end}}
        return {"Version": "2012-10-17", "Statement": [
            {"Effect": "Allow", "Action": ["lightsail:GetBundles", "lightsail:GetInstance",
                                            "lightsail:GetInstancePortStates"],
             "Resource": "*", "Condition": condition},
            {"Effect": "Allow", "Action": "lightsail:PutInstancePublicPorts",
             "Resource": INSTANCE_ARN, "Condition": condition},
        ]}

    def verify_instance(self):
        instance = self.call("lightsail", "get-instance", {"instanceName": NAME})["instance"]
        tags = {tag["key"]: tag["value"] for tag in instance.get("tags", [])}
        if (instance.get("arn") != INSTANCE_ARN or instance.get("publicIpAddress") != INSTANCE_IP
                or instance.get("state", {}).get("name") != "running"
                or instance.get("bundleId") != "large_3_2"
                or instance.get("location", {}).get("regionName") != REGION
                or tags.get("DeploymentId") != DEPLOYMENT
                or tags.get("Project") != "abn-lead-gen"):
            raise AwsFailure("Approved running instance identity changed")

    def desired_ports(self):
        return [{"fromPort": port, "toPort": port, "protocol": "tcp", "cidrs": cidrs,
                 "ipv6Cidrs": []} for port, cidrs in [
            (22, [self.args.operator_ip + "/32"]), (80, ["0.0.0.0/0"]), (443, ["0.0.0.0/0"]),
        ]]

    def current_ports(self):
        rows = self.call("lightsail", "get-instance-port-states", {"instanceName": NAME})["portStates"]
        if any(row.get("cidrListAliases") or row.get("state") != "open" for row in rows):
            raise AwsFailure("Unexpected firewall alias or state")
        return [{key: row.get(key, [] if key in {"cidrs", "ipv6Cidrs"} else None)
                 for key in ("fromPort", "toPort", "protocol", "cidrs", "ipv6Cidrs")} for row in rows]

    def apply(self):
        self.verify_instance()
        expected = sorted(self.desired_ports(), key=lambda row: row["fromPort"])
        current = sorted(self.current_ports(), key=lambda row: row["fromPort"])
        if current not in (expected, expected[:1]):
            raise AwsFailure("Unexpected existing firewall; no replacement performed")
        if current != expected:
            self.call("lightsail", "put-instance-public-ports", {"instanceName": NAME, "portInfos": expected})
        if sorted(self.current_ports(), key=lambda row: row["fromPort"]) != expected:
            raise AwsFailure("HTTPS firewall readback mismatch")
        emit({"event": "engine_https_firewall_verified", "instance": NAME,
              "ipv4_web_ports": [80, 443], "ssh_cidr": self.args.operator_ip + "/32",
              "ipv6_enabled": False, "database_public": False, "new_paid_resources": False})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aws", required=True)
    parser.add_argument("--profile", default="maintain-media-deploy")
    parser.add_argument("--operator-ip", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    args.account = ACCOUNT
    if not ipaddress.IPv4Address(args.operator_ip).is_global:
        raise ValueError("Public operator IPv4 required")
    if not args.apply:
        emit({"status": "review_only", "instance_arn": INSTANCE_ARN, "public_ports": [80, 443]})
        return 0
    session = HttpsSession(args)
    failed = False
    try:
        session.start()
        session.apply()
    except AwsFailure as error:
        failed = True
        emit({"status": "blocked", "reason": str(error)})
    finally:
        session.finish()
    return int(failed or session.cleanup_failed)


if __name__ == "__main__":
    raise SystemExit(main())
