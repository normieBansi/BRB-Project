from trex_stl_lib.api import *


class STLLevel3Surge(object):
    """Short high-rate burst traffic for stress validation."""

    def get_streams(self, tunables, **kwargs):
        src_ip = kwargs.get("src", "192.168.60.10")
        dst_ip = kwargs.get("dst", "192.168.50.10")

        syn_pkt = Ether() / IP(src=src_ip, dst=dst_ip) / TCP(dport=80, flags="S")
        udp_pkt = Ether() / IP(src=src_ip, dst=dst_ip) / UDP(dport=53, sport=53000)
        icmp_pkt = Ether() / IP(src=src_ip, dst=dst_ip) / ICMP(type=8)

        return [
            STLStream(
                packet=STLPktBuilder(pkt=syn_pkt),
                mode=STLTXSingleBurst(total_pkts=12000, pps=8000),
            ),
            STLStream(
                packet=STLPktBuilder(pkt=udp_pkt),
                mode=STLTXSingleBurst(total_pkts=10000, pps=7000),
            ),
            STLStream(
                packet=STLPktBuilder(pkt=icmp_pkt),
                mode=STLTXSingleBurst(total_pkts=8000, pps=6000),
            ),
        ]


def register():
    return STLLevel3Surge()
