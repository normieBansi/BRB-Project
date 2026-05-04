from trex_stl_lib.api import *


class STLLevel2Pressure(object):
    """Medium-rate mixed traffic for Suricata and policy pressure testing."""

    def get_streams(self, tunables, **kwargs):
        src_ip = kwargs.get("src", "192.168.60.10")
        dst_ip = kwargs.get("dst", "192.168.50.10")

        syn_pkt = Ether() / IP(src=src_ip, dst=dst_ip) / TCP(dport=80, flags="S")
        udp_pkt = Ether() / IP(src=src_ip, dst=dst_ip) / UDP(dport=123, sport=40000)
        http_probe = (
            Ether()
            / IP(src=src_ip, dst=dst_ip)
            / TCP(dport=80, sport=41000, flags="PA")
            / Raw(load=b"GET /?id=1' HTTP/1.1\\r\\nHost: lab\\r\\n\\r\\n")
        )

        return [
            STLStream(packet=STLPktBuilder(pkt=syn_pkt), mode=STLTXCont(pps=1200)),
            STLStream(packet=STLPktBuilder(pkt=udp_pkt), mode=STLTXCont(pps=900)),
            STLStream(packet=STLPktBuilder(pkt=http_probe), mode=STLTXCont(pps=350)),
        ]


def register():
    return STLLevel2Pressure()
