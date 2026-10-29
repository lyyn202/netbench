from types import SimpleNamespace

import pytest

from netbench.metrics import bps_to_rate, extract_metrics, rate_to_bps


@pytest.mark.parametrize(
    ("value", "expected"),
    [("10M", 10_000_000), ("1G", 1_000_000_000), ("500K", 500_000), ("1234", 1234)],
)
def test_rate_to_bps(value, expected):
    assert rate_to_bps(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [(1_000_000_000, "1G"), (100_000_000, "100M"), (10_000, "10K"), (999, "999")],
)
def test_bps_to_rate(value, expected):
    assert bps_to_rate(value) == expected


def test_extract_udp_metrics():
    args = SimpleNamespace(
        mode="udp", packet_size=1000, target="192.0.2.2",
        loss_threshold=0.1, max_latency_ms=None, duration=10,
    )
    data = {"end": {"sum": {
        "bits_per_second": 8_000_000,
        "packets": 1000,
        "lost_packets": 2,
        "lost_percent": 0.2,
        "jitter_ms": 0.4,
    }}}
    row = extract_metrics(data, args, 8_000_000)
    assert row["offered_mbps"] == 8
    assert row["received_mbps"] == 8
    assert row["estimated_payload_pps"] == 1000
    assert row["loss_percent"] == 0.2
    assert row["passed"] is False


def test_extract_tcp_metrics():
    args = SimpleNamespace(
        mode="tcp", packet_size=1200, target="192.0.2.2",
        loss_threshold=0.1, max_latency_ms=None, duration=10,
    )
    data = {"end": {
        "sum_sent": {"bits_per_second": 90_000_000},
        "sum_received": {"bits_per_second": 88_000_000},
    }}
    row = extract_metrics(data, args, None)
    assert row["sent_mbps"] == 90
    assert row["received_mbps"] == 88
    assert row["estimated_payload_pps"] is None
    assert row["passed"] is None
