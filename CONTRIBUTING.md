# Contributing

Thanks for helping improve NetBench.

## Before opening an issue

- Include the Linux distribution, Python version, and `iperf3 --version`.
- Share the exact command used and sanitized error output.
- Do not attach credentials, public IPs, or sensitive network topology details.

## Development workflow

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m pip install -r requirements-dev.txt
python -m pytest
```

Keep the core runtime dependency-free where practical. Add tests for parsing and metric extraction changes. Never make tests send traffic to a real network; use fixtures/mocked subprocess output.
