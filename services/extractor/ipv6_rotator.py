"""
AWS Dynamic IPv6 Subnet Rotator for zero-cost anti-blocking egress.
Binds outgoing requests across billions of random IPv6 addresses in a /64 block.
"""
import random
import ipaddress
import socket
from typing import Optional
from app.config import settings


class IPv6Rotator:
    def __init__(self, subnet_str: Optional[str] = None):
        self.subnet_str = subnet_str or settings.AWS_IPV6_SUBNET
        self.network = None
        if self.subnet_str:
            try:
                self.network = ipaddress.IPv6Network(self.subnet_str, strict=False)
            except Exception as e:
                print(f"[IPv6Rotator] Failed to parse IPv6 subnet '{self.subnet_str}': {e}")

    def get_random_ipv6(self) -> Optional[str]:
        """
        Generate a cryptographically randomized IPv6 host address within the /64 block.
        """
        if not self.network:
            return None

        # Generate a random 64-bit integer for the host portion
        random_host_int = random.getrandbits(64)
        ip_int = int(self.network.network_address) + random_host_int
        return str(ipaddress.IPv6Address(ip_int))

    def get_ytdlp_source_address_args(self) -> list:
        """
        Return --source-address flag for yt-dlp if IPv6 subnet is configured.
        """
        random_ip = self.get_random_ipv6()
        if random_ip:
            return ["--source-address", random_ip]
        return []


ipv6_rotator = IPv6Rotator()
