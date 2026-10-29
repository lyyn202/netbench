"""Command-line interface for NetBench."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from netbench.metrics import extract_metrics, rate_to_bps, bps_to_rate


def _iperf_command(args: argparse.Namespace, offered_bps: int | None = None) -> list[str]:
    cmd = ["iperf3", "-c", args.target, "-J", "-t", str(args.duration)]
    if args.port:
        cmd += ["-p", str(args.port)]
    if args.bind:
        cmd += ["-B", args.bind]
    if args.mode == "udp":
        if offered_bps is None:
            raise ValueError("UDP mode requires an offered rate")
        cmd += ["-u", "-b", bps_to_rate(offered_bps), "-l", str(args.packet_size)]
    elif args.parallel > 1:
        cmd += ["-P", str(args.parallel)]
    if args.reverse:
        cmd += ["-R"]
    if args.json_interval:
        cmd += ["-i", str(args.json_interval)]
    return cmd


def _run_iperf(args: argparse.Namespace, offered_bps: int | None = None) -> dict[str, Any]:
    cmd = _iperf_command(args, offered_bps)
    print(f"\n[{dt.datetime.now().isoformat(timespec='seconds')}] Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=args.duration + 30, check=False
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("iperf3 timed out; check connectivity and server status.") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"iperf3 failed (exit {result.returncode}): {detail}")
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Could not parse iperf3 JSON output: {exc}") from exc
    if data.get("error"):
        raise RuntimeError(f"iperf3 reported: {data['error']}")
    return data


def _write_reports(rows: list[dict[str, Any]], prefix: str) -> tuple[Path, Path]:
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    base = Path(f"{prefix}-{stamp}")
    json_path, csv_path = base.with_suffix(".json"), base.with_suffix(".csv")
    json_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    fields = [
        "timestamp", "target", "mode", "offered_mbps", "sent_mbps",
        "received_mbps", "packet_size_bytes", "estimated_payload_pps",
        "packets_sent", "packets_lost", "loss_percent", "jitter_ms",
        "threshold_loss_percent", "passed", "duration_seconds",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return csv_path, json_path


def _serve(args: argparse.Namespace) -> int:
    cmd = ["iperf3", "-s"]
    if args.port:
        cmd += ["-p", str(args.port)]
    print(f"Starting iperf3 server: {' '.join(cmd)}")
    print("Press Ctrl+C to stop. Configure firewall rules for the isolated test network.")
    return subprocess.call(cmd)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="netbench",
        description="Benchmark bandwidth, UDP packet loss, jitter and estimated payload PPS using iperf3."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    server = sub.add_parser("serve", help="Start an iperf3 receiver/server")
    server.add_argument("--port", type=int, default=5201)
    server.set_defaults(handler=_serve)

    run = sub.add_parser("run", help="Run a benchmark to an iperf3 receiver")
    run.add_argument("--target", required=True, help="Receiver IP/hostname")
    run.add_argument("--port", type=int, default=5201)
    run.add_argument("--mode", choices=["udp", "tcp"], default="udp")
    run.add_argument("--duration", type=int, default=10)
    run.add_argument("--packet-size", type=int, default=1200, help="UDP payload bytes, not full Ethernet frame")
    run.add_argument("--start-rate", default="10M")
    run.add_argument("--max-rate", default="100M", help="Required maximum offered load safety cap")
    run.add_argument("--step-rate", default="10M")
    run.add_argument("--loss-threshold", type=float, default=0.1)
    run.add_argument("--max-latency-ms", type=float, default=None,
                     help="Optional jitter threshold in ms; jitter is not latency")
    run.add_argument("--parallel", type=int, default=1, help="Parallel TCP streams")
    run.add_argument("--reverse", action="store_true")
    run.add_argument("--bind", default=None, help="Optional local source IP")
    run.add_argument("--json-interval", type=int, default=0)
    run.add_argument("--report-prefix", default="netbench")
    run.add_argument("--pause", type=float, default=1.0)
    run.set_defaults(handler=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if shutil.which("iperf3") is None:
        print("Error: iperf3 not found. Install it (e.g. sudo apt install iperf3).", file=sys.stderr)
        return 2
    if args.command == "serve":
        return args.handler(args)
    if args.duration < 1:
        parser.error("--duration must be >= 1")
    if args.parallel < 1:
        parser.error("--parallel must be >= 1")
    if args.port < 1 or args.port > 65535:
        parser.error("--port must be between 1 and 65535")
    if args.mode == "tcp":
        data = _run_iperf(args)
        row = extract_metrics(data, args, None)
        rows = [row]
        if row["received_mbps"] is not None:
            print(f"TCP received: {row['received_mbps']:.2f} Mbps")
    else:
        if not 64 <= args.packet_size <= 65507:
            parser.error("--packet-size must be between 64 and 65507 bytes")
        try:
            start, maximum, step = (
                rate_to_bps(args.start_rate), rate_to_bps(args.max_rate),
                rate_to_bps(args.step_rate)
            )
        except (ValueError, OverflowError) as exc:
            parser.error(f"Invalid rate: {exc}")
        if start <= 0 or step <= 0 or maximum < start:
            parser.error("Rates must be positive and --max-rate must be >= --start-rate")
        if args.loss_threshold < 0:
            parser.error("--loss-threshold must be >= 0")
        if args.max_latency_ms is not None and args.max_latency_ms < 0:
            parser.error("--max-latency-ms must be >= 0")
        print("Safety reminder: test only equipment and links you own or are authorized to stress.")
        print(f"UDP ramp: {bps_to_rate(start)} to {bps_to_rate(maximum)}, step {bps_to_rate(step)}; "
              f"{args.duration}s/step; stop above {args.loss_threshold}% loss.")
        rows = []
        rate = start
        while True:
            data = _run_iperf(args, rate)
            row = extract_metrics(data, args, rate)
            rows.append(row)
            loss = row["loss_percent"]
            recv = row["received_mbps"]
            jitter = row["jitter_ms"]
            pps = row["estimated_payload_pps"]
            print(
                f"offered={row['offered_mbps']:.2f} Mbps | "
                f"received={recv if recv is not None else float('nan'):.2f} Mbps | "
                f"loss={loss if loss is not None else float('nan'):.4f}% | "
                f"jitter={jitter if jitter is not None else float('nan'):.3f} ms | "
                f"estimated payload PPS={pps if pps is not None else float('nan'):.0f}"
            )
            if row["passed"] is False:
                print("Threshold crossed; stopping the load ramp.")
                break
            if rate >= maximum:
                break
            time.sleep(max(0.0, args.pause))
            rate = min(rate + step, maximum)
    csv_path, json_path = _write_reports(rows, args.report_prefix)
    print(f"\nWrote CSV report:  {csv_path.resolve()}")
    print(f"Wrote JSON report: {json_path.resolve()}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user.", file=sys.stderr)
        raise SystemExit(130)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
