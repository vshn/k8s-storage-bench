#!/usr/bin/env python3.8

import json
import sys

from datetime import datetime

from graphs import render_results

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ["-h", "--help"]:
        print(f"Usage: {sys.argv[0]} <results-file> [<results-file> [...]]\n")
        print(
            "This command can be used to plot the benchmark results provided in the\n"
            + "<results-file> arguments. The command expects that the results are in\n"
            + "the JSON format emitted by the bundled `bench.py` script."
        )
        sys.exit(1)

    results = []
    for fname in sys.argv[1:]:
        try:
            with open(fname) as resf:
                results.extend(json.load(resf))
        except Exception as e:
            print(f"Unable to load data from {fname}: {e}")

    timestamp = datetime.now().strftime("%Y_%m_%d_%H%M%S")

    render_results(results, filename=f"results_{timestamp}.pdf")
