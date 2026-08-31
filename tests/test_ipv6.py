"""
Unit tests for AWS Dynamic IPv6 Subnet Rotator.
"""
from app.services.extractor.ipv6_rotator import IPv6Rotator


def test_ipv6_rotator_generation():
    test_subnet = "2600:1f18:6300:1200::/64"
    rotator = IPv6Rotator(subnet_str=test_subnet)

    ip1 = rotator.get_random_ipv6()
    ip2 = rotator.get_random_ipv6()

    assert ip1 is not None
    assert ip2 is not None
    assert ip1 != ip2  # Two random generation calls from 18 quintillion addresses will be distinct
    assert ip1.startswith("2600:1f18:6300:1200:")
    assert ip2.startswith("2600:1f18:6300:1200:")


def test_ipv6_ytdlp_args():
    test_subnet = "2600:1f18:6300:1200::/64"
    rotator = IPv6Rotator(subnet_str=test_subnet)
    args = rotator.get_ytdlp_source_address_args()

    assert len(args) == 2
    assert args[0] == "--source-address"
    assert args[1].startswith("2600:1f18:6300:1200:")
