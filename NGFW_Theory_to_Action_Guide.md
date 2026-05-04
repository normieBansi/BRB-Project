# NGFW Theory-to-Action Guide

**Navigation:** [OPNsense Checklist](OPNsense_Click_By_Click_Checklist.md) | [Ubuntu Checklist](Ubuntu_Checklist.md) | [Kali Checklist](Kali_Checklist.md) | [OPNsense Tests](OPNsense_Point_By_Point_Tests.md) | [TRex Guide](TRex_3_Level_Setup_Guide.md)

---

## 1. Purpose

This guide is theory-first. Each theory block links directly to checklist actions so you can reproduce the lab without guessing execution order.

How to use this file:

1. Read one theory block.
2. Execute the linked checklist actions.
3. Confirm with the linked verification tests.

---

## 2. Theory: Separation of Duties and Blast Radius

Principle:

1. The firewall should enforce traffic policy and detection.
2. The control plane should run orchestration, telemetry UI, and ML.
3. Traffic generation should stay isolated from control and target roles.

Action links:

1. [Set OPNsense baseline and admin hardening](OPNsense_Click_By_Click_Checklist.md#2-base-system-setup)
2. [Deploy Debian control plane components](Ubuntu_Checklist.md#7-deploy-the-debian-control-plane)
3. [Validate Kali container baseline networking](Kali_Checklist.md#1-container-startup)

Verification links:

1. [Run pre-checks for gateway and interface sanity](OPNsense_Point_By_Point_Tests.md#2-pre-checks)

---

## 3. Theory: Least Privilege Segmentation (L3/L4)

Principle:

1. Permit only the exact Kali-to-Ubuntu paths required for tests.
2. Block broad egress and cross-network pivot paths by default.

Action links:

1. [Create aliases first](OPNsense_Click_By_Click_Checklist.md#3-create-all-required-aliases-first)
2. [Implement OPT1 rule order](OPNsense_Click_By_Click_Checklist.md#4-opt1-rules-kali-side)
3. [Implement LAN rule order](OPNsense_Click_By_Click_Checklist.md#5-lan-rules-ubuntu-side)
4. [Run Kali connectivity baseline checks](Kali_Checklist.md#3-day-1-connectivity-baseline)

Verification links:

1. [Firewall policy tests](OPNsense_Point_By_Point_Tests.md#3-day-1-firewall-policy-tests)

---

## 4. Theory: DNS as a Security Control Plane

Principle:

1. Force clients to resolve through the firewall.
2. Block direct external DNS to prevent policy bypass and improve visibility.

Action links:

1. [Enable and validate Unbound DNS](OPNsense_Click_By_Click_Checklist.md#10-unbound-dns)
2. [Re-test DNS behavior from Kali and Ubuntu](OPNsense_Point_By_Point_Tests.md#4-day-1-dns-control-tests)

---

## 5. Theory: Detection Pipeline (IDS then IPS)

Principle:

1. Start Suricata in IDS mode to validate signatures safely.
2. Move to IPS only after known-good alert behavior is confirmed.

Action links:

1. [Configure Suricata interfaces, rules, and HOME_NET](OPNsense_Click_By_Click_Checklist.md#8-suricata-setup)
2. [Generate alert traffic from Kali](Kali_Checklist.md#4-day-1-suricata-ids-trigger-traffic)
3. [Stage IPS activation carefully](OPNsense_Click_By_Click_Checklist.md#95-enable-ips-only-after-ids-works)

Verification links:

1. [Suricata IDS tests](OPNsense_Point_By_Point_Tests.md#5-day-1-suricata-ids-tests)

---

## 6. Theory: Telemetry Quality and Signal-to-Noise

Principle:

1. High-fidelity telemetry requires filtering control-plane infrastructure chatter.
2. Operator actions must be auditable in one persistent log.

Action links:

1. [Deploy log receiver and SIEM stack](Ubuntu_Checklist.md#6-choose-and-deploy-siem)
2. [Start API with telemetry exclusions and action-log path](Ubuntu_Checklist.md#74-create-and-start-the-debian-control-api)
3. [Use manual action-log workflow for retention/clear](Ubuntu_Checklist.md#710-manual-dashboard-action-log-workflow)
4. [Validate live telemetry counters and excluded IP behavior](Ubuntu_Checklist.md#83-test-in-live-mode)

Verification links:

1. [Remote logging tests](OPNsense_Point_By_Point_Tests.md#7-day-2-remote-logging-tests)

---

## 7. Theory: Containment and Incident Response Loop

Principle:

1. Containment should be fast, reversible, and observable.
2. Ban/unban control must stay synchronized with firewall alias tables.

Action links:

1. [Configure OPNsense REST API integration](OPNsense_Click_By_Click_Checklist.md#135-configure-opnsense-rest-api-for-debian-control-api)
2. [Validate hook integration end-to-end](OPNsense_Click_By_Click_Checklist.md#136-validate-dashboard-hook-integration-end-to-end)
3. [Test ban, release, fade, and banned-drops metric from live traffic](Kali_Checklist.md#57-validate-updated-telemetry-and-ban-ux-from-live-traffic)
4. [Validate dashboard live containment behavior](Ubuntu_Checklist.md#83-test-in-live-mode)

Verification links:

1. [API control and REST integration tests](OPNsense_Point_By_Point_Tests.md#6-day-2-api-control-and-rest-integration-tests)

---

## 8. Theory: Safe Orchestration and Reproducibility

Principle:

1. Control endpoints should be deterministic and bounded.
2. Reproduction requires explicit env vars, startup method, and smoke checks.

Action links:

1. [Run API in background with fixed env propagation](Ubuntu_Checklist.md#75-run-the-api-in-the-background-without-losing-the-token)
2. [Exercise core control endpoints](Ubuntu_Checklist.md#77-new-control-endpoints-to-test)
3. [Run one-shot Debian smoke test](Ubuntu_Checklist.md#79-run-one-shot-debian-smoke-test)
4. [Run API-driven attack scenarios from Kali](Kali_Checklist.md#5-use-the-fastapi-control-api)

---

## 9. Theory: ML-Augmented NGFW Analytics

Principle:

1. Signature detection and ML scoring should complement each other.
2. Labeled run metadata must align with parsed firewall records.

Action links:

1. [Export and parse logs for training](Ubuntu_Checklist.md#10-collect-and-parse-training-data)
2. [Train model and generate predictions](Ubuntu_Checklist.md#11-train-isolation-forest)
3. [Validate ML output in dashboard](Ubuntu_Checklist.md#123-verify-ml-data-appears-in-dashboard)
4. [Capture labeled attack runs](Kali_Checklist.md#8-day-3-final-labeled-runs-for-ml-training-data)

---

## 10. Theory: Controlled Load and Stress Characterization

Principle:

1. Traffic load should scale in controlled levels to avoid false troubleshooting.
2. Stress tests must preserve attribution (source, destination, phase).

Action links:

1. [TRex setup and level design rationale](TRex_3_Level_Setup_Guide.md#4-three-traffic-levels)
2. [Run three levels sequentially](TRex_3_Level_Setup_Guide.md#5-run-the-3-levels-sequentially)
3. [Kali-side TRex workflow](Kali_Checklist.md#7-trex-on-debian-recommended-path)

Verification links:

1. [TRex validation checklist](TRex_3_Level_Setup_Guide.md#7-validation-checklist-after-each-level)

---

## 11. Theory: Minimal Exposure for External Access

Principle:

1. Publish only the dashboard/API entry point when needed.
2. Keep raw service ports private.

Action links:

1. [Optional OPNsense publishing controls](OPNsense_Click_By_Click_Checklist.md#14-day-2-optional-publishing-support)
2. [Dashboard hosting and tunnel migration flow](Ubuntu_Checklist.md#14-migration-deploy-dashboard-to-free-web-hosting)

Verification links:

1. [Optional exposure sanity test](OPNsense_Point_By_Point_Tests.md#8-day-2-optional-exposure-tests)

---

## 12. Reproduction Agenda (Fast Path)

Day 1 foundation:

1. [OPNsense policy, DNS, and Suricata baseline](OPNsense_Click_By_Click_Checklist.md#day-1---base-opnsense-policy-and-ids-baseline)
2. [Kali connectivity and trigger traffic](Kali_Checklist.md#day-1---setup-tools-and-ids-trigger-traffic)

Day 2 operations:

1. [Debian SIEM + API + dashboard deployment](Ubuntu_Checklist.md#day-2---siem-control-api-and-dashboard)
2. [REST hook and automation validation on OPNsense](OPNsense_Click_By_Click_Checklist.md#day-2---opnsense-support-for-logging-dashboard-and-controlled-access)
3. [API-driven run control and telemetry UX validation from Kali](Kali_Checklist.md#day-2---control-api-integration-and-labeled-attack-runs)

Day 3 analytics and stress:

1. [ML pipeline and final checks](Ubuntu_Checklist.md#day-3---ml-pipeline)
2. [TRex staged load runs](Kali_Checklist.md#day-3---trex-traffic-generation)
3. [Final OPNsense review tests](OPNsense_Point_By_Point_Tests.md#9-day-3-final-opnsense-review-tests)

---

## 13. Final Evidence Pack

Before closing a run, collect these proof points:

1. [OPNsense final pass criteria](OPNsense_Point_By_Point_Tests.md#10-final-pass-criteria)
2. [OPNsense minimum success checklist](OPNsense_Click_By_Click_Checklist.md#18-minimum-opnsense-success-checklist)
3. [Ubuntu minimum success checklist](Ubuntu_Checklist.md#15-ubuntu-minimum-success-checklist)
4. [Kali verification checklist](Kali_Checklist.md#9-verification-checklist-for-kali-side)
