Your assumption is incorrect:

* **TCP SYN flood → L4**
* **SSH brute force → L7 (application/auth layer)**
* **Nikto, sqlmap → L7 (HTTP/application attacks)**

You already have **mixed L4 + L7**, not only L3/L4.

---

## Additional attacks to extend coverage (L3 → L7)

### L3 / Network layer

![Image](https://images.openai.com/static-rsc-4/qpJ9zTuVrvci_q2rmYgJF9AnUnB6WkKTBNBPk5Xvf55yliOopOzhz5HS1w_P9WMN5amQu7BLOK5RVS9S0TbvlrJOSgdx1c35D4hoshQ8zu2V23AZMjt3Th8xlEAAD_YNdNrJn5nmZFzDdhAQwF0zTDhFSGro0ItAokze5-kkGmKgng0xLuFMM8Sal3uOTu2r?purpose=fullsize)

![Image](https://images.openai.com/static-rsc-4/TiU1zhqo7TTFX9K6q-Jj7uWmyzJOMgNRGtHJEy6BJqBcRxH8EtiztZK5H-GT6aNc0Jae--a-vBVMGXqVayNtRMihsIrZoYTJ9PBnapQc3lvvJz-mT1MtaoGy46Jf0z1-aFyE5OZjaJvd-xr0mDSBZvFkF-d7_MMo3lIx-5xRN1ah_1wiYc78-Oweo96-4ZgX?purpose=fullsize)

![Image](https://images.openai.com/static-rsc-4/7EwYZyO7l7Syjx1q-9s3Q8BHSKZZCzHzLfngVfhSNYm3LlLG1K1hsMRNWzgFUI5GXu256OZNolL8UTEbT2VSdqyJSxRNOJkFFcsURY5LsY7QOwfUYCoGXP1tcbZGll_y--2dBlR6Bh4X03DPy6sRMM6-TvZ3JtizCnM-KY_Co2ddq7bz04yVvsPToZZUfsCi?purpose=fullsize)

* ICMP flood (`hping3 --icmp`)
* Smurf / amplification (broadcast ICMP)
* IP spoofing (`hping3 --spoof`)
* Fragmentation / evasion (overlapping fragments)

---

### L4 / Transport layer

![Image](https://images.openai.com/static-rsc-4/gm8HyuyyC-96ujVU8DaQxgKKeHdaktGkC6OeQg6OvZQbxXXNRrtwQTNEzdODz9XCma6LEx4PBSBNXLz4s_j_jl27fdDQbWecnMF2U2ESOl_lPjE4HBNnvX2ik9TABsN_-l65-B4MifuSDzARQsDlwqFNMuAWVdc6CJ6pDsZQuP_WKjT556xX2i2E9LfI75BK?purpose=fullsize)

![Image](https://images.openai.com/static-rsc-4/b-_t7zhHuxKy9bNo_iM9dEoS41SUgnA4GEg7poIyMI2_k9JE9N5VqIAgv-MpIXRrFA7O4FffeYozE8GnrDgfN9nLNXR0kFnzJoqjhaDl2CSvbPsP6sMZmZ04h6OY_cLFnU6YZmbYMlaYZpzV3Fg6-EAmNFykFGkZW405N_NP2sH7sZDHv2GUhiiGPmR3yBEj?purpose=fullsize)

![Image](https://images.openai.com/static-rsc-4/P10bLnCS_xIxYLKH8fFWt4u6NWv53Frxy9IFU5EbOJHt3YLi-WFPeTxHku-fd_ok8lG1-oPdZfqorb5a2gCuXZm2G8CwGzTiq9wx3CVWHfeoDcWumvPkCqX3egxsDocw8pIQ97dS91p3kUfXz7UkZIus1rh6DNzpk-hhMpmmfygP1qPQU7YbmRfIVNLOGys1?purpose=fullsize)

![Image](https://images.openai.com/static-rsc-4/iPHlpqBLiEsWgy9kV86yp6mWMRIl7Nj3U9ux0P-YauG-Yrmt7Zhhrp_TfRtL2ApMEAoPiXlxvWGz5e_SorNY80N1pzxhlSGeY-9z2fykAM9d4sfDiJuBMjAWojlGKT-hSdN8_2-irh9LtfXUbFLaRd3mtGkUPmHRLVjj_pq4JP_kGtlvKaDzxYqbFkbY0NNc?purpose=fullsize)

![Image](https://images.openai.com/static-rsc-4/1LUs8YtvyqR5ez0gD9pxvIv8gdRLQzhWbpX5FmUYpuPMWFKBS57sQIKYJmGLWLnaI_hlrceWDDEWhR6yNhH4qU-YkWMJ81_HwMMp0K90xrdvx64SEP0gzF87gdyIWNG8kiMWmskhiWDQiFYN9GH-LLnSHCUKZNplz-QVGJys1S8CkMx6_mgrjjqu54zLnhQX?purpose=fullsize)

![Image](https://images.openai.com/static-rsc-4/pyeqx8ES07-UzjmDjmwEDdj8kov2Edr3VIaV5C2vgZBlPMcnSdPzjK_9NlXe8anivtZ2xUebSCPUNHPpq1VDD0rqLQvj7hA315WHYUOvFZ0ou4MpL6-Eh7LNZHyEQZqgBFTn_wyDE7Q8iU8UaEbw6i_HM7D0-DSXnsrHY3-8ZN8gKXpORLNbbdAIgts58Q7M?purpose=fullsize)

* UDP flood (`hping3 --udp`)
* TCP RST injection
* FIN/NULL/XMAS scans (Nmap)
* Connection exhaustion (precursor to Slowloris)

---

### L5–L6 / Session & presentation

![Image](https://images.openai.com/static-rsc-4/xS8pRqUSnevRsMsPerjlOUkUrF07mua5_81yObOLHr4nwScGh4I8ShmSKT9g2sP39X8kdQ52ZcQdSHe1HTXvw6OxkGDkcWZKsS-SzQlD5onGux2hJwhzumMHNGTbmvd8SZ_nyH6t8i11K9uSyJwEaNfNuEEDn10LjqjT0UqO0yrjXmiAJbaEcHxx6C9TJBIj?purpose=fullsize)

![Image](https://images.openai.com/static-rsc-4/mSuHMvGhq2OAZWQS-IbS592D3URqLpG41ZWTCvO86RaQ-x0I-HCSqiecUtItwbjaX2a2IRE76g2CSvjM8WAG2PLSVkfHID5yy58dK3wrftO2XYCG_cuaerqqyLlkEsg80-AC4L75K8PmeT8q09gvEJIe6LgaC8iL4jvzTg9TCcXt_l4c_UICKmEY_yrSPX0_?purpose=fullsize)

![Image](https://images.openai.com/static-rsc-4/zQwqyHH74u5TG6Rn-BjjSpXoVw_wCly926v_0HG3evLm5vtfI10kkIcsxz2tdurbAN7ph109_DHBM85dYTXiVYdMspVUTf5U3YyjaypRt85KUu0QFe9StMKglXJ87iqXOvANNiPUhItQUie8vouxgprLeeIJzdUnUMJxdehAXqakLqwMJ0FUJViBRvLJy-PU?purpose=fullsize)

![Image](https://images.openai.com/static-rsc-4/VevZy7EUaWiOe26D-svGAfKiRtSMwVuv7B3nKf2s8zocvYf7MQ9bBoSuxOTxi_WOT4oPJy3FPSGItw7_OszKilyXwPMKK7V2q1IgV-rXaHlgq9nheFyN3fNxh-VL2PfDySSeVl3iN6ehnY8GpGtCghhu2oYkJLHFVpElHgt2R3N0M4oCd4fJTQgScwwtiGNO?purpose=fullsize)

![Image](https://images.openai.com/static-rsc-4/a4VEgH1qXjZk31Gz-CQJQSu0Qbw1I-9UdglF8u0lI2OeFR3bU_PBQvPV4GscqfTKH51b0p6ly10QMfRIKHX2t9GaShMjrZqg3NS67HIqGkUKJshXxhNpiFMA-irN2hxoCZ_SArufJx4pUMtWmJ6QJ3DcW9ng2xmgU3frLOfW9G5aHlrxWWxUW41BuXG9nXw5?purpose=fullsize)

* TLS renegotiation abuse
* SSL stripping (MITM)
* Session hijacking (cookie replay)
* ARP spoofing (gateway impersonation)

---

### L7 / Application layer (critical for blue team realism)

![Image](https://images.openai.com/static-rsc-4/g0G6zla59zm7834jT_SH7wxP1rfAka5PSsuEJryKs96QHGXy2-zXwD05TXXiQ3T0RhmdYML86F77yn-SLnpXVP_bC9yywtK1DjFOdsmsxDHirt9nuAivzk9XQpTvQV1YC9Cxqd3KPU8b-WvqWJbWJuGjUeyD6BEeGNRuAV7MTzmiawDeXe2Hillma1DolmHB?purpose=fullsize)

![Image](https://images.openai.com/static-rsc-4/4HwIl30vj-dMbVbijWU-BMEgY3AX5B_R4FfY47iTQRXgqMIF1FyYbw7ol6e3nl3D3R7qi0XrahN_Ssdap57GN6PILri7xui-jh9JIUdE0YZGNT6HwVcTRlJSA3lhLa1NF361nyu3HmAwVTfL2D_TjAibKUp0nyDRnME0FIMWHMv0MSFReHl0PSNtz-uIffdL?purpose=fullsize)

![Image](https://images.openai.com/static-rsc-4/Vjh0ZFuxGFw8A7kDk7HFKh3fHStbrv8Z_QDF9ryuB6SSpeWo8OhhUZcEbojhMbeHhnSVsnbhpyCTa3p-YcHGBHj0s5REeNichWmdmKfTDrjBIJzaIE2LDMFSwjnlUb-FlOezRHyr11A9rYVXWvYoJz2jq5OLfotrGatMmsgQQjv81-1BZwhKBnwnsLMRXeCc?purpose=fullsize)

![Image](https://images.openai.com/static-rsc-4/O0lltD9DakpYxZj_fZBifnzxhaHcoxVQRCBfCwJhI7rUwACCI4R5i7X4_Mc6lRu7005l55UHqsaFJhu6idXHXiU2eP7dpo2gRQRS5471fEy1nievBE9SSuqQk2JkmaIDhyRdkCNp23xowpggdLpM1pP3RwiTSEp4h3f-l98o4NAqlxBzBodBEFKoIOXvc4Ap?purpose=fullsize)

* XSS (use OWASP ZAP)
* CSRF simulation
* Directory brute force (`gobuster`, `ffuf`)
* File upload → webshell
* API fuzzing (JSON payload abuse)
* Credential stuffing (HTTP login loops)
* Slow HTTP attacks (Slowloris)

---

## Tools to expand lab

* Metasploit → multi-layer exploitation
* OWASP ZAP → L7 testing
* Burp Suite → manual + automated attacks
* Nmap → advanced scans/evasion
* Slowloris → L7 DoS

---

## Key gap in your setup

* Missing **stateful evasion + encrypted traffic inspection**
* No **user-behavior attacks (session/auth abuse)**
* Limited **API / modern web attack surface**

---

## Minimal realistic upgrade set

* Add: XSS, CSRF, file upload, API fuzzing
* Add: UDP flood + fragmentation
* Add: MITM (ARP spoof + SSL strip)
* Add: Slow HTTP DoS

---

## Sources

* OWASP Top 10: [https://owasp.org/www-project-top-ten/](https://owasp.org/www-project-top-ten/)
* NIST SP 800-115 (technical guide to security testing)
* RFC 4987 (TCP SYN flooding defenses)
* ENISA Threat Landscape reports

---

