# Local browser review — 8 September 2026

Actual Codex in-app browser, private loopback synthetic report only. Reviewed report from run `a9073203-fc30-4b02-81c4-8045ce43bb69`, HTML SHA256 `f8f3d791e7b86cd3227ddecb8b4c5d01f3b36e0ab6fdb8ac5522de0531a4f6aa`.

The first browser inspection found a real integration defect: `report_context` sampled generated_at before the individual gate checked_at. The renderer correctly rejected the apparently future decision, masking the permitted fixture. The build now samples generated_at after all row decisions. A real PostgreSQL-to-renderer regression in `tests/integration/test_operational_summary.py` verifies that the allowed fixture reaches the visible candidate label.

After the fix, the rendered report showed **Email: needs send-time checks**, the synthetic example.com endpoint, cautious QBCC wording, unknown source age, recorded outcome and no direct email/call action. The prior failed version showed a masked endpoint. No contact was sent.

At the required 360x800 viewport: document scroll width345px, viewport360px; no horizontal overflow. The heading, disclosure, CSV download and business card were legible. Tab focused the CSV link with a visible purple focus ring. The actual screenshot and accessibility tree were inspected in the task. This is a focused visual/keyboard check, not a complete WCAG audit. Temporary viewport override was reset.

The fixture API at 127.0.0.1:8766 returned HTTP200 for /health with mode fixture and outreach disabled; anonymous /v1/openapi.json returned401. Server was launched hidden with local Python, bound to loopback, and has no access log of contact requests.
