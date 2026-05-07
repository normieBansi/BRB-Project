# Draft Project Report: Open-Source NGFW with Adaptive Detection

## 1. Introduction

This project studies how an open-source firewall setup can be extended toward next-generation firewall behavior using data-driven detection and feedback. The implementation uses OPNsense as inline firewall, Suricata for IDS/IPS, and a side analytics node for telemetry processing, anomaly scoring, and reporting.

In simple words, the project tries to close this gap:

1. normal rule/signature based open-source firewalling,
2. adaptive behavior-aware detection mostly available in commercial NGFW products.

The project is in network security domain, and focuses on practical deployment that can actually be reproduced in a humble lab.

### 1.1 Scope of Project

The scope includes architecture, implementation, and evaluation of a sidecar model with these parts:

1. stateful segmentation and policy enforcement with OPNsense,
2. IDS/IPS detection through Suricata,
3. log collection and visualization,
4. anomaly analytics pipeline using Isolation Forest,
5. controlled traffic generation for testing using scenario scripts (TRex archived for later use).

### 1.2 Scope of Project Impact

#### 1.2.1 Social Impact

1. Gives a usable cybersecurity demo platform for researchers and students.
2. Helps understand real monitoring and attack-defense correlation, not just theory.
3. Encourages safer network design habits like segmentation and least privilege.

#### 1.2.2 Economic Impact

1. Uses open-source stack and avoids commercial NGFW licensing.
2. Can be replicated by small colleges or labs with limited budgets.
3. Skills learned map to SOC and network security industry roles.

#### 1.2.3 Environmental Impact

1. Reuses existing hardware through virtualization instead of extra appliances.
2. Modular design allows only required components to run, reducing unnecessary overhead.
3. High-volume experiments still consume power, so workload profiling is required.

#### 1.2.4 Academic Impact

1. Connects literature to implementation.
2. Produces reusable artifacts: configs, scripts, dataset snapshots, and results.
3. Sets a base for future work on closed-loop response.

---

## 2. Problem Statement

Most open-source firewall deployments are strong in packet filtering and signature matching, but not adaptive by default. They depend on pre-defined rules and known signatures. That makes them weak against behavior-level anomalies, zero-day style events, and dynamic attack patterns.

Main practical issues are:

1. manual dependence for tuning and response,
2. delayed reaction to unknown threats,
3. disconnected pipeline between detection and enforcement,
4. difficulty in producing local environment-specific intelligence.

So the core project question is:

How to augment an open-source firewall stack with lightweight adaptive detection and telemetry-driven feedback, while keeping it transparent, low-cost, and implementable in an academic setup?

<image of current open-source firewall workflow describing where static rules/signatures stop being enough for adaptive threat handling>

---

## 3. Literature Review

This section summarizes the findings from the survey literature and how they informed this project design.

### 3.1 Firewall Evolution Summary

Literature tracks evolution from packet filters to proxy firewalls, then stateful inspection, UTM, and NGFW. NIST guidance and later NGFW surveys show that each phase added visibility and control depth.

Key timeline used in this report:

| Year | Milestone |
|---|---|
| 1988 | Morris Worm incident and CERT/CC formation |
| 1989 | Early packet filtering (`screend`) |
| 1991 | Proxy firewall deployment pattern |
| 1994 | Stateful inspection mainstreamed (FireWall-1 era) |
| 1998 | Snort released |
| 2004 | UTM market category formalized |
| 2009 | NGFW category formalized |
| 2015 | OPNsense fork introduced |
| 2020s | Adaptive detection research grows |

<image of firewall evolution flow showing packet filter -> proxy -> stateful -> UTM -> NGFW -> adaptive firewall>

### 3.2 NGFW Capability from Literature

Neupane et al., Liang and Kim, and Heino et al. emphasize that NGFW value is not only feature count, but integration quality: application context, DPI, threat intelligence, and prevention in one operational path.

| Component | Typical Layer Coverage | Function |
|---|---|---|
| Packet filtering | L3/L4 | ACL based allow/deny |
| Stateful engine | L4 | Session tracking |
| DPI | L4-L7 | Payload/protocol inspection |
| App identification | L7 | Application-aware control |
| IDS/IPS | L3-L7 | Threat detection and blocking |
| Threat intelligence | L3-L7 | IoC correlation |

### 3.3 IDS and Adaptive Detection Literature

Denning (1987) established anomaly-based IDS concepts. Khraisat et al. and Liao et al. discuss operational challenges like false positives and alert overload. Ahmad et al. and Dini et al. show there is still a gap between research models and production security operations.

### 3.4 Isolation Forest Motivation from Surveyed Papers

Liu et al. introduced Isolation Forest as an unsupervised anomaly method. Tao et al. validated it in network traffic settings, and Al Farizi et al. reported good efficiency across studies. For this project, that is useful because lab data labeling is not always complete.

### 3.5 Identified Gap in Open-Source Ecosystem

From the surveyed papers, the recurring gap is this: open-source firewall stacks are mature in static controls but weak in adaptive behavior-level learning and automatic policy feedback.

| System Class | Detection Style | Inline Prevention | Adaptability | Open-Source Availability |
|---|---|---|---|---|
| Stateless firewall | Rule only | Yes | Low | High |
| Stateful firewall | Rule + state | Yes | Low | High |
| IDS | Signature/anomaly alerting | No | Low | High |
| IPS | Signature/anomaly | Yes | Low | High |
| UTM | Multi-engine | Yes | Moderate | Partial |
| NGFW | Context + signature | Yes | Moderate | Limited |
| Adaptive sidecar firewall | Learned behavior + signatures | Yes | High | Underexplored |

---

## 4. Project Description

The project implements a sidecar-based adaptive firewall architecture.

### 4.1 System Overview

1. OPNsense is the inline enforcement point.
2. Suricata performs signature-driven IDS/IPS detection.
3. Firewall and IDS events are exported using syslog.
4. Analytics node processes logs into features.
5. Isolation Forest gives anomaly score trends.
6. Protocol/action context from parsed logs explains anomalous events.
7. Dashboard combines control-plane and data-plane visibility.

<image of sidecar architecture showing enforcement on firewall and analytics/inference on separate node>

### 4.2 Main Use Cases

1. Student cyber range and practical coursework.
2. Security monitoring training and triage exercises.
3. Comparative study: signature-only vs adaptive assisted detection.
4. Controlled segmentation validation under mixed traffic.

<table for use-case mapping describing stakeholder, objective, expected security outcome, and measurable indicator>

### 4.3 Importance of This Project

1. Shows that adaptive firewall behavior can be approximated with open tooling.
2. Makes NGFW-like experimentation possible in low-resource settings.
3. Produces a practical workflow that can be reused by later batches.

---

## 5. Requirements

### 5.1 Functional Requirements

1. Enforce segmented policy between red and blue networks.
2. Detect suspicious activity through Suricata rules.
3. Export logs to centralized analytics stack.
4. Extract and store network features for model training and scoring.
5. Generate anomaly and context outputs and present them in dashboard.
6. Support repeatable scenario-based traffic generation.

### 5.2 Non-Functional Requirements

1. Reproducibility of setup and experiments.
2. Reasonable processing latency for telemetry and scoring.
3. Reliability under concurrent scenario execution.
4. Controlled access to orchestration endpoints.
5. Maintainable modular architecture.

<table for non-functional requirement verification describing requirement, validation method, pass criteria, and current status>

### 5.3 Environment Requirements

| Item | Requirement |
|---|---|
| Host | Virtualization-capable system |
| Firewall VM | OPNsense with multiple interfaces |
| Analytics VM | Ubuntu with log + model stack |
| IDS/IPS | Suricata integration |
| Data stack | Syslog + SIEM/dashboard tooling |
| Modeling | Python stack (pandas, scikit-learn, joblib) |
| Traffic generation | scripted scenarios (+ optional archived TRex) |

---

## 6. Methodology

Method follows build-measure-improve cycle for network defense engineering.

### 6.1 Stage 1: Baseline Architecture and Policy

1. define trust boundaries and subnets,
2. configure explicit allow/deny policy,
3. validate route correctness and policy hit behavior.

### 6.2 Stage 2: Detection and Telemetry

1. enable Suricata and tune ruleset selection,
2. verify syslog forwarding and event integrity,
3. align timestamps for proper correlation.

### 6.3 Stage 3: Feature and Model Pipeline

1. transform firewall/IDS events into flow-level statistical features,
2. train Isolation Forest baseline on mostly normal traffic,
3. generate anomaly-only inference outputs,
4. integrate outputs into dashboard stream.

### 6.4 Stage 4: Operational Validation

1. run scenario-based tests,
2. execute optional TRex stress profiles only when re-enabled,
3. compare visibility and detection quality across modes.

<image of methodology pipeline describing stage-wise flow from policy setup to telemetry, model scoring, and validation feedback>

---

## 7. Experimentation

### 7.1 Experiment Setup

1. segmented test network through OPNsense,
2. Suricata active on relevant interfaces,
3. centralized telemetry and dashboard,
4. model scoring pipeline attached to processed logs,
5. traffic from scripted tests and optional TRex profiles.

### 7.2 Experiment Categories

#### 7.2.1 Policy Behavior Tests

1. allowed flow confirmation,
2. denied flow confirmation,
3. restricted egress confirmation.

#### 7.2.2 Detection Tests

1. known-signature scenarios,
2. mixed traffic with overlapping patterns,
3. event correlation between firewall and IDS streams.

#### 7.2.3 Model Tests

1. anomaly score distribution under normal traffic,
2. anomaly spikes under suspicious traffic,
3. protocol/action context quality for anomalous events.

#### 7.2.4 Load Tests

1. low to high TRex profile ramp,
2. pipeline lag observation,
3. packet drop and resource usage capture.

<image of traffic load progression describing expected detector behavior from low, medium, and high profile intensity>

### 7.3 Observation Metrics

| Metric Group | Metrics |
|---|---|
| Detection | event count, protocol mix, event-source mix, signature diversity |
| Model | anomaly score spread, anomaly ratio, anomaly drift over time |
| System | CPU, RAM, ingestion delay, packet drop |
| Operations | run repeatability, scenario-to-alert correlation |

<table for scenario-wise observations describing scenario ID, expected signal, observed signal, notes>

---

## 8. Results

This section is currently a working draft projection and will be updated with final measured values.

### 8.1 Expected Outcome Summary

1. clear policy enforcement between segmented zones,
2. improved visibility through unified telemetry,
3. anomaly layer helps spot suspicious behavior beyond direct signatures,
4. protocol/action context helps triage anomalous events faster.

### 8.2 Reporting Template for Final Numbers

| Area | Metric | Value |
|---|---|---|
| Signature detection | Total events | [ ] |
| Signature detection | Distinct signatures | [ ] |
| Signature detection | Top protocol concentration | [ ] |
| Anomaly model | Anomaly ratio | [ ] |
| Anomaly model | Estimated false positives | [ ] |
| Context telemetry | Top event source share | [ ] |
| Context telemetry | Anomaly-score threshold hit rate | [ ] |
| Performance | Avg ingest delay | [ ] |
| Performance | Peak analytics CPU | [ ] |
| Performance | Packet drop at stress | [ ] |

### 8.3 Discussion

From the literature and current implementation trend, some observations are expected:

1. signature-based engines stay strong for known threats,
2. anomaly scoring can surface unknown or less-obvious activity,
3. anomaly quality is strongly tied to feature quality and baseline diversity,
4. sidecar pattern keeps enforcement stable while analytics evolves.

<table for discussion evidence describing each observation, supporting metric, expected trend, and interpretation>

### 8.4 Current Limitations

1. testbed traffic is smaller than enterprise traffic,
2. model behavior depends on feature quality and class balance,
3. encrypted traffic depth remains a challenge,
4. full auto-blocking needs strict guardrails to avoid wrong blocks.

<table for limitation and mitigation describing limitation, impact level, mitigation plan, and future verification approach>

### 8.5 Projection and Future Direction

1. include richer protocol metadata,
2. use dynamic thresholding by time and traffic profile,
3. evaluate long-window drift behavior,
4. build safer response-policy layer with review controls.

---

## 9. Deliverables

### 9.1 Technical Deliverables

1. configured OPNsense segmentation and firewall policy,
2. Suricata-based IDS/IPS setup,
3. centralized logging and dashboard views,
4. anomaly analytics scripts/artifacts,
5. scenario and TRex traffic profiles,
6. experiment logs and observations.

<table for deliverable tracking describing deliverable name, completion evidence, reviewer remarks, and sign-off status>

### 9.2 Documentation Deliverables

1. architecture write-up,
2. setup and configuration notes,
3. methodology and metric definitions,
4. complete project report.

### 9.3 Academic Deliverables

1. literature-based problem framing,
2. comparative network defense analysis,
3. conclusions and future work proposal.

---

## 10. References

1. Denning, D. E. (1987). An Intrusion-Detection Model. IEEE Transactions on Software Engineering, SE-13(2), 222-232. https://doi.org/10.1109/TSE.1987.232894
2. Neupane, K., Haddad, R., and Chen, L. (2018). Next Generation Firewall for Network Security: A Survey. Proc. IEEE SoutheastCon, 1-6. https://doi.org/10.1109/SECON.2018.8478973
3. Liang, J., and Kim, Y. (2022). Evolution of Firewalls: Toward Securer Network Using Next Generation Firewall. Proc. IEEE CCWC, 752-759. https://doi.org/10.1109/CCWC54503.2022.9720435
4. Heino, J., Hakkala, A., and Virtanen, S. (2022). Study of Methods for Endpoint Aware Inspection in a Next Generation Firewall. Cybersecurity, 5(1), 1-19. https://doi.org/10.1186/s42400-022-00127-8
5. Scarfone, K., and Hoffman, P. (2009). Guidelines on Firewalls and Firewall Policy (NIST SP 800-41 Rev. 1). National Institute of Standards and Technology. https://doi.org/10.6028/NIST.SP.800-41r1
6. Ingham, K., and Forrest, S. (2002). A History and Survey of Network Firewalls. University of New Mexico, TR-2002-12.
7. Cheswick, W. R., and Bellovin, S. M. (1994). Firewalls and Internet Security: Repelling the Wily Hacker. Addison-Wesley.
8. Roesch, M. (1999). Snort - Lightweight Intrusion Detection for Networks. Proc. USENIX LISA.
9. Paxson, V. (1999). Bro: A System for Detecting Network Intruders in Real-Time. Computer Networks, 31(23-24), 2435-2463. https://doi.org/10.1016/S1389-1286(99)00112-7
10. Khraisat, A., Gondal, I., Vamplew, P., and Kamruzzaman, J. (2019). Survey of Intrusion Detection Systems: Techniques, Datasets and Challenges. Cybersecurity, 2(1), 1-22. https://doi.org/10.1186/s42400-019-0038-7
11. Liao, H.-J., Lin, C.-H. R., Lin, Y.-C., and Tung, K.-Y. (2013). Intrusion Detection System: A Comprehensive Review. Journal of Network and Computer Applications, 36(1), 16-24. https://doi.org/10.1016/j.jnca.2012.09.004
12. Ahmad, Z., Shahid Khan, A., Wai Shiang, C., Abdullah, J., and Ahmad, F. (2021). Network Intrusion Detection System: A Systematic Study of Machine Learning and Deep Learning Approaches. Transactions on Emerging Telecommunications Technologies, 32(1), e4150. https://doi.org/10.1002/ett.4150
13. Liu, H., and Lang, B. (2019). Machine Learning and Deep Learning Methods for Intrusion Detection Systems: A Survey. Applied Sciences, 9(20), 4396. https://doi.org/10.3390/app9204396
14. Dini, P., Elhanashi, A., Begni, A., Saponara, S., Zheng, Q., and Gasri, D. (2023). Overview on Intrusion Detection Systems Design Exploiting Machine Learning for Networking Cybersecurity. Applied Sciences, 13(13), 7507. https://doi.org/10.3390/app13137507
15. Chandola, V., Banerjee, A., and Kumar, V. (2009). Anomaly Detection: A Survey. ACM Computing Surveys, 41(3), 1-58. https://doi.org/10.1145/1541880.1541882
16. Liu, F. T., Ting, K. M., and Zhou, Z.-H. (2008). Isolation Forest. Proc. IEEE ICDM, 413-422. https://doi.org/10.1109/ICDM.2008.17
17. Tao, X., Peng, Y., Zhao, F., Zhao, P., and Wang, Y. (2018). A Parallel Algorithm for Network Traffic Anomaly Detection Based on Isolation Forest. International Journal of Distributed Sensor Networks, 14(11). https://doi.org/10.1177/1550147718814471
18. Al Farizi, W. S., Hidayah, I., and Rizal, M. N. (2021). Isolation Forest Based Anomaly Detection: A Systematic Literature Review. Proc. IEEE ICITACEE. https://doi.org/10.1109/ICITACEE53184.2021.9617498
19. Cheng, Z., Zou, C., and Dong, J. (2019). Outlier Detection Using Isolation Forest and Local Outlier Factor. Proc. ACM CARMA, 161-168. https://doi.org/10.1145/3338840.3355641
20. Song, W., Beshley, M., Przystupa, K., Beshley, H., Kochan, O., Pryslupskyi, A., Pieniak, D., and Su, J. (2020). A Software Deep Packet Inspection System for Network Traffic Analysis and Anomaly Detection. Sensors, 20(6), 1637. https://doi.org/10.3390/s20061637
21. Sultana, N., Chilamkurti, N., Peng, W., and Alhadad, R. (2019). Survey on SDN Based Network Intrusion Detection System Using Machine Learning Approaches. Peer-to-Peer Networking and Applications, 12(2), 493-501. https://doi.org/10.1007/s12083-017-0630-0
22. Vartouni, A. M., Kaki, S. S., and Teshnehlab, M. (2019). Leveraging Deep Neural Networks for Anomaly-Based Web Application Firewall. IET Information Security, 13(4), 352-361. https://doi.org/10.1049/iet-ifs.2018.5404
23. Zhang, C., Jia, D., Wang, L., Wang, W., Liu, F., and Yang, A. (2022). Comparative Research on Network Intrusion Detection Methods Based on Machine Learning. Computers and Security, 121, 102861. https://doi.org/10.1016/j.cose.2022.102861
24. Da Costa, K. A. P., Papa, J. P., Lisboa, C. O., Munoz, R., and de Albuquerque, V. H. C. (2019). Internet of Things: A Survey on Machine Learning-Based Intrusion Detection Approaches. Computer Networks, 151, 147-157. https://doi.org/10.1016/j.comnet.2019.01.023
25. Kiratsata, H. J., Raval, D. P., and Viras, P. K. (2022). Behaviour Analysis of Open-Source Firewalls Under Security Crisis. Proc. IEEE ICDCECE. https://doi.org/10.1109/ICDCECE53908.2022.9767176
26. Che, C. K. N. S. A., and Rafee, K. M. (2023). Towards Secure Local Area Network (LAN) Using OPNsense Firewall. Malaysian Journal of Computing and Applied Mathematics.
27. Olivera-Ruiz, G., and Solsol-Isminio, J. (2024). Next-Generation Firewall Open-Source and LAN Performance. Proc. IEEE LACCCEI. https://doi.org/10.1109/LACCCEI62174.2024.10767614
28. Mohile, A. (2023). Next-Generation Firewalls: A Performance-Driven Approach to Contextual Threat Prevention. International Journal of Computer Technology and Electronics Communication.
29. Lamdakkar, O., Ameur, I., Eleyatt, M. M., and Carlier, F. (2024). Toward a Modern Secure Network Based on Next-Generation Firewalls: Recommendations and Best Practices. Procedia Computer Science. https://doi.org/10.1016/j.procs.2024.09.242
30. Singh, L., and Singh, R. (2024). Comparative Analysis of Traditional Firewalls and Next-Generation Firewalls: A Review. In Latest Trends in Engineering and Technology. Taylor and Francis. https://doi.org/10.1201/9781032665443-3
31. George, A. S., and George, A. S. H. (2021). A Brief Study on the Evolution of Next Generation Firewall and Web Application Firewall. International Journal of Advanced Research in Computer and Communication Engineering, 10(5).
32. Mukkamala, P. P., and Rajendran, S. (2020). A Survey on the Different Firewall Technologies. International Journal of Engineering Applied Sciences and Technology, 5(1).
33. He, K., Kim, D. D., and Asghar, M. R. (2023). Adversarial Machine Learning for Network Intrusion Detection Systems: A Comprehensive Survey. IEEE Communications Surveys and Tutorials, 25(1), 538-566. https://doi.org/10.1109/COMST.2022.3233132
34. Psychogyios, K., Boubendir, A., et al. (2024). A Survey of DDoS Attack and Defence: Architectures, Taxonomy and Mitigation. Future Internet, 16(3), 73. https://doi.org/10.3390/fi16030073
