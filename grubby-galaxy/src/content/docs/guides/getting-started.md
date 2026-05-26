---
title: Getting Started
description: Learn how to set up AutoPulse and run your first anomaly detection cycle.
---

Welcome to AutoPulse! This guide will walk you through setting up the project locally and running a virtual replay of vehicle data to detect potential anomalies.

## Prerequisites

Before you begin, ensure you have the following installed:

- **Python 3.10+**: For the core PdM analysis engine.
- **Node.js 20+**: For the Starlight documentation site.
- **nvm** (Optional but recommended): To manage Node versions.

## 1. Setup the Environment

Clone the repository and set up the Python virtual environment:

```bash
# Clone the repo
git clone https://github.com/ajason13/autopulse.git
cd autopulse

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows use `.venv\Scripts\activate`

# Install dependencies
pip install -r requirements.txt
```

## 2. Initialize the Documentation Site

AutoPulse uses Starlight for technical documentation. To run it locally:

```bash
cd grubby-galaxy
npm install
npm run dev
```

The docs will be available at `http://localhost:4321/autopulse/`.

## 3. Run Your First PdM Cycle

You can run the existing test suite to verify the anomaly detection logic:

```bash
# From the project root
export PYTHONPATH=$PYTHONPATH:.
pytest tests/test_us003_pdm_algorithms.py -v
```

## 4. Understanding the Output

When you run the `PdMProcessor`, it emits `PdMAlert` objects. These contain:

- **failure_probability**: A score from 0.0 to 1.0.
- **failure_type**: The identified failure mode (HDF, OSF, etc.).
- **is_anomaly**: A boolean flag (True if probability > 0.5).
- **window_summary**: A statistical snapshot of the 60-second sliding window.

Next, explore the [Engine Data Contract](../../specs/us-001-engine-data-contract/) to understand the underlying sensor data.
