from trex_stl_lib.api import *


class STLLevel1Baseline(object):
    """Low-rate baseline traffic for wiring and logging validation."""

    def get_streams(self, tunables, **kwargs):
        src_ip = kwargs.get("src", "192.168.60.10")
        dst_ip = kwargs.get("dst", "192.168.50.10")

        syn_pkt = Ether() / IP(src=src_ip, dst=dst_ip) / TCP(dport=80, flags="S")
        dns_pkt = Ether() / IP(src=src_ip, dst=dst_ip) / UDP(dport=53, sport=5353)
        icmp_pkt = Ether() / IP(src=src_ip, dst=dst_ip) / ICMP(type=8)

        return [
            STLStream(packet=STLPktBuilder(pkt=syn_pkt), mode=STLTXCont(pps=120)),
            STLStream(packet=STLPktBuilder(pkt=dns_pkt), mode=STLTXCont(pps=60)),
            STLStream(packet=STLPktBuilder(pkt=icmp_pkt), mode=STLTXCont(pps=30)),
        ]


def register():
    return STLLevel1Baseline()
