"""Parsing and metric extraction helpers."""
from __future__ import annotations

from typing import Any


def rate_to_bps(value: str) -> int:
    """Parse 100K, 10M, 1G, or a plain number in bits per second."""
    text = value.strip().upper()
    multipliers = {"K": 1_000, "M": 1_000_000, "G": 1_000_000_000}
    if text and text[-1] in multipliers:
        return int(float(text[:-1]) * multipliers[text[-1]])
    return int(float(text))


def bps_to_rate(bps: int) -> str:
    """Format bit rate using iperf3-friendly suffixes where possible."""
    for suffix, factor in (("G", 1_000_000_000), ("M", 1_000_000), ("K", 1_000)):
        if bps >= factor and bps % factor == 0:
            return f"{bps // factor}{suffix}"
    return str(bps)


def extract_metrics(
    data: dict[str, Any],
    args: Any,
    offered_bps: int | None,
) -> dict[str, Any]:
    """Extract stable report fields from iperf3 JSON, retaining raw data elsewhere."""
    end = data.get("end", {})
    sent = end.get("sum_sent") or {}
    received = end.get("sum_received") or {}
    common = end.get("sum") or {}
    udp = args.mode == "udp"

    sent_bps = sent.get("bits_per_second")
    recv_bps = received.get("bits_per_second")
    packets = sent.get("packets")
    lost_packets = received.get("lost_packets")
    lost_percent = received.get("lost_percent")
    jitter_ms = received.get("jitter_ms")

    if udp:
        # iperf3 versions may expose UDP summary fields under end.sum.
        packets = packets if packets is not None else common.get("packets")
        lost_packets = lost_packets if lost_packets is not None else common.get("lost_packets")
        lost_percent = lost_percent if lost_percent is not None else common.get("lost_percent")
        jitter_ms = jitter_ms if jitter_ms is not None else common.get("jitter_ms")
        sent_bps = sent_bps if sent_bps is not None else common.get("bits_per_second")
        recv_bps = recv_bps if recv_bps is not None else common.get("bits_per_second")

    if lost_percent is None and packets and lost_packets is not None:
        lost_percent = float(lost_packets) / float(packets) * 100.0 if packets else 0.0

    payload_pps = None
    if udp and sent_bps is not None and args.packet_size > 0:
        payload_pps = float(sent_bps) / (args.packet_size * 8)

    loss_value = float(lost_percent) if lost_percent is not None else None
    passed = None
    if udp:
        passed = loss_value is not None and loss_value <= args.loss_threshold
        if args.max_latency_ms is not None and jitter_ms is not None:
            passed = passed and float(jitter_ms) <= args.max_latency_ms

    return {
        "timestamp": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat(timespec="seconds"),
        "target": args.target,
        "mode": args.mode,
        "offered_mbps": offered_bps / 1_000_000 if offered_bps is not None else None,
        "sent_mbps": float(sent_bps) / 1_000_000 if sent_bps is not None else None,
        "received_mbps": float(recv_bps) / 1_000_000 if recv_bps is not None else None,
        "packet_size_bytes": args.packet_size if udp else None,
        "estimated_payload_pps": payload_pps,
        "packets_sent": packets,
        "packets_lost": lost_packets,
        "loss_percent": loss_value,
        "jitter_ms": float(jitter_ms) if jitter_ms is not None else None,
        "threshold_loss_percent": args.loss_threshold if udp else None,
        "passed": passed,
        "duration_seconds": args.duration,
        "raw_iperf3": data,
    }
