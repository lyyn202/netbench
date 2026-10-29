# NetBench CLI

[![Tests](https://github.com/YOUR_GITHUB_USERNAME/netbench/actions/workflows/tests.yml/badge.svg)](https://github.com/YOUR_GITHUB_USERNAME/netbench/actions/workflows/tests.yml)

A small, standalone Python CLI that controls [`iperf3`](https://iperf.fr/) to benchmark a network path through a router, switch, or firewall. It supports TCP throughput tests and a stepped UDP offered-load test that records throughput, packet loss, jitter, and estimated payload packets per second (PPS).

> **Safety:** Run only on equipment and network paths you own or are explicitly authorized to test. Load testing can disrupt connectivity for other users. Begin with low rates and a conservative maximum.

## Features

- UDP offered-load ramp with explicit start, step, and maximum rate.
- Stop when packet loss crosses a configurable threshold.
- TCP throughput mode.
- Reverse-direction tests with `iperf3 -R`.
- CSV and JSON reports, including raw `iperf3` JSON for later analysis.
- No Python runtime dependencies.
- Unit tests and GitHub Actions workflow.

## How it works

```text
Linux sender ──> device under test ──> Linux receiver
  NetBench         router/switch       iperf3 server
```

The sender runs NetBench; the receiver runs `iperf3` in server mode. For credible hardware results, use separate machines with NICs and links that can sustain the target rate. The endpoints must not become the bottleneck.

## Requirements

- Linux (recommended) on sender and receiver
- Python 3.9 or newer on the sender
- `iperf3` installed on both machines
- Connectivity between sender and receiver through the device under test

On Debian/Ubuntu:

```bash
sudo apt update
sudo apt install python3 python3-pip iperf3
```

## Install from a Git checkout

```bash
git clone https://github.com/YOUR_GITHUB_USERNAME/netbench.git
cd netbench
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

Verify:

```bash
netbench --help
```

## Quick start

### 1. Start the receiver

On the Linux receiver:

```bash
iperf3 -s
```

Or run the included wrapper:

```bash
netbench serve
```

The default iperf3 port is TCP 5201 for control; allow the required test traffic through host firewalls on the isolated test network.

### 2. Start with a conservative UDP ramp

On the sender, replace `192.0.2.20` with the receiver's test-network IP:

```bash
netbench run \
  --target 192.0.2.20 \
  --mode udp \
  --start-rate 10M \
  --step-rate 10M \
  --max-rate 100M \
  --duration 10 \
  --packet-size 1200 \
  --loss-threshold 0.1
```

This tests 10, 20, 30, … up to 100 Mbps, stopping at the first measured UDP loss above 0.1%. This is a maximum offered-rate cap, not a claim that 100 Mbps is safe for your particular network.

### 3. TCP throughput test

```bash
netbench run --target 192.0.2.20 --mode tcp --duration 20
```

### 4. Reverse direction

```bash
netbench run --target 192.0.2.20 --mode udp --reverse \
  --start-rate 10M --step-rate 10M --max-rate 100M
```

## CLI options

Run `netbench run --help` for the complete list.

| Option | Default | Meaning |
|---|---:|---|
| `--target` | required | Receiver address |
| `--mode` | `udp` | `udp` or `tcp` |
| `--duration` | `10` | Seconds per load step |
| `--start-rate` | `10M` | Initial UDP offered rate |
| `--step-rate` | `10M` | UDP offered-rate increment |
| `--max-rate` | `100M` | Hard cap for UDP offered rate |
| `--packet-size` | `1200` | UDP payload bytes, not full Ethernet frame |
| `--loss-threshold` | `0.1` | Stop when measured loss exceeds this percent |
| `--max-latency-ms` | unset | Optional jitter threshold; jitter is not latency |
| `--parallel` | `1` | Parallel TCP streams in TCP mode |
| `--reverse` | off | Reverse traffic direction |
| `--port` | `5201` | iperf3 server port |
| `--bind` | unset | Local source IP |
| `--pause` | `1.0` | Pause between UDP steps |
| `--report-prefix` | `netbench` | Output file prefix |

Rates accept suffixes `K`, `M`, and `G`, for example `500K`, `100M`, `1G`. The report filenames include a timestamp.

## Reports and metrics

Each run writes a timestamped `.csv` and `.json` file in the current directory.

- **Offered Mbps:** requested UDP payload rate for the step.
- **Sent/received Mbps:** values reported by iperf3.
- **Loss percent / lost packets:** reported by iperf3's UDP receiver summary.
- **Jitter:** iperf3's UDP jitter estimate, in milliseconds.
- **Estimated payload PPS:** bitrate divided by UDP payload bytes × 8.

### Important measurement limitations

- The PPS estimate uses UDP payload bitrate and payload size. It excludes IP/UDP headers, Ethernet headers, VLAN tags, preamble, and inter-frame gap. It is **not exact wire-rate PPS**.
- `iperf3` JSON fields can vary by version. NetBench stores the raw JSON in the `.json` report so results can be checked.
- Jitter is not one-way latency. For latency benchmarking, add a dedicated RTT or timestamping method.
- TCP adapts its sending rate to congestion, so use UDP for fixed offered-load/loss tests and TCP for throughput.
- The first release ramps linearly and stops at the first threshold crossing; it does not yet binary-search the threshold or collect router SNMP/CPU/interface counters.
- High packet rates and 10/25/100 GbE testing may require dedicated traffic-generation tools and suitable NICs. Validate that the sender and receiver are not CPU-bound.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest
```

Or install the test dependency separately:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
```

## GitHub setup

1. Create an empty repository named `netbench` on GitHub.
2. Replace `YOUR_GITHUB_USERNAME` in the README badge and clone URL.
3. Commit and push this project:

```bash
git init
git add .
git commit -m "Initial NetBench CLI project"
git branch -M main
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/netbench.git
git push -u origin main
```

GitHub Actions runs the test suite automatically on pushes and pull requests.

## Roadmap

- [ ] Binary-search refinement near the loss threshold
- [ ] Machine-readable device/interface telemetry (SNMP, Linux counters)
- [ ] Latency measurements alongside jitter
- [ ] Multi-flow and bidirectional test plans
- [ ] Optional web dashboard and historical comparisons
- [ ] TRex/MoonGen backend for high-rate PPS tests

## License

MIT. See [LICENSE](LICENSE).
