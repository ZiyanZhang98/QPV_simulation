"""Monte Carlo timing-error analysis for the three-verifier QPV protocol.

The analysis uses seconds internally and samples independent timing errors for
each verifier:

    e_i = b_i + epsilon_i^PTP + epsilon_i^ctrl

where every component is zero-mean Gaussian with the standard deviation set by
the selected parameter regime. Distances do not enter this analysis because
the deterministic propagation delays are already compensated by the ideal
release schedule; this module studies the residual synchronization mismatch.
"""

import argparse
import csv
import json
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from run_honest_prover import DEFAULT_RANDOM_SEED, get_ptp_parameter_regimes


DEFAULT_RESULTS_DIR = Path("results/ptp_timing_analysis")
VERIFIER_NAMES = ("v0", "v1", "v2")
PAIRWISE_INDICES = ((0, 1), (0, 2), (1, 2))


def sample_regime(regime, trials, rng):
    """Sample all release-time errors and derived metrics for one regime.

    Arrays use seconds. Shapes:
      - component and release errors: (trials, 3)
      - pairwise relative errors: (trials, 3), ordered 01, 02, 12
      - maximum mismatch: (trials,)
    """
    mu_b_s = regime.get("mu_b_s", 0.0)
    sigma_b_s = regime["sigma_b_s"]
    sigma_ptp_s = regime["sigma_ptp_s"]
    sigma_ctrl_s = regime["sigma_ctrl_s"]

    residual_offsets_s = rng.normal(mu_b_s, sigma_b_s, size=(trials, 3))
    ptp_jitter_s = rng.normal(0, sigma_ptp_s, size=(trials, 3))
    control_jitter_s = rng.normal(0, sigma_ctrl_s, size=(trials, 3))
    release_errors_s = residual_offsets_s + ptp_jitter_s + control_jitter_s

    pairwise_errors_s = np.column_stack([
        release_errors_s[:, i] - release_errors_s[:, j]
        for i, j in PAIRWISE_INDICES
    ])
    max_mismatch_s = np.ptp(release_errors_s, axis=1)

    return {
        "regime": dict(regime),
        "residual_offsets_s": residual_offsets_s,
        "ptp_jitter_s": ptp_jitter_s,
        "control_jitter_s": control_jitter_s,
        "release_errors_s": release_errors_s,
        "pairwise_errors_s": pairwise_errors_s,
        "max_mismatch_s": max_mismatch_s,
    }


def mismatch_summary(max_mismatch_s):
    """Return the requested summary statistics for maximum mismatch."""
    return {
        "mean_s": float(np.mean(max_mismatch_s)),
        "std_s": float(np.std(max_mismatch_s, ddof=1)),
        "median_s": float(np.median(max_mismatch_s)),
        "p95_s": float(np.percentile(max_mismatch_s, 95)),
        "p99_s": float(np.percentile(max_mismatch_s, 99)),
        "max_s": float(np.max(max_mismatch_s)),
    }


def acceptance_probabilities(max_mismatch_s, tolerances_s):
    """Compute P[max mismatch <= synchronization tolerance]."""
    sorted_mismatch = np.sort(max_mismatch_s)
    accepted_counts = np.searchsorted(sorted_mismatch, tolerances_s, side="right")
    return accepted_counts / sorted_mismatch.size


def _microseconds(values_s):
    return np.asarray(values_s) * 1e6


def _safe_name(name):
    return name.replace("/", "_").replace(" ", "_")


def save_histograms(samples_by_regime, output_dir):
    """Save one maximum-mismatch histogram for every parameter regime."""
    histogram_dir = output_dir / "histograms"
    histogram_dir.mkdir(parents=True, exist_ok=True)

    for name, samples in samples_by_regime.items():
        mismatch_us = _microseconds(samples["max_mismatch_s"])
        fig, ax = plt.subplots(figsize=(7, 4.5), dpi=180)
        ax.hist(mismatch_us, bins=80, density=True, color="#267D8C", alpha=0.85)
        ax.axvline(np.percentile(mismatch_us, 95), color="#B33A3A", linestyle="--", label="95th percentile")
        ax.axvline(np.percentile(mismatch_us, 99), color="#D38B24", linestyle=":", label="99th percentile")
        ax.set_title(name.replace("_", " "))
        ax.set_xlabel(r"Maximum verifier mismatch $\Delta t_{\max}$ ($\mu$s)")
        ax.set_ylabel("Probability density")
        ax.legend()
        fig.tight_layout()
        fig.savefig(histogram_dir / f"{_safe_name(name)}.png")
        plt.close(fig)


def save_acceptance_plot(samples_by_regime, tolerances_s, output_dir):
    """Plot honest acceptance probability versus synchronization tolerance."""
    fig, ax = plt.subplots(figsize=(9, 5.5), dpi=180)
    for name, samples in samples_by_regime.items():
        probabilities = acceptance_probabilities(samples["max_mismatch_s"], tolerances_s)
        is_conservative = name.startswith("conservative_")
        ax.plot(
            _microseconds(tolerances_s),
            probabilities,
            label=name.replace("_", " "),
            linewidth=1.0 if is_conservative else 2.4,
            alpha=0.6 if is_conservative else 1.0,
        )

    ax.set_xlabel(r"Synchronization tolerance $\epsilon_{\mathrm{sync}}$ ($\mu$s)")
    ax.set_ylabel(r"Honest acceptance probability $P_{\mathrm{accept}}$")
    ax.set_ylim(-0.01, 1.01)
    ax.grid(alpha=0.25)
    ax.legend(fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(output_dir / "acceptance_probability_vs_tolerance.png")
    plt.close(fig)


def save_regime_violin_plot(samples_by_regime, output_dir, rng):
    """Compare ideal, realistic, and pooled conservative mismatch samples."""
    groups = {
        "Ideal hardware PTP": samples_by_regime["ideal_hardware_ptp"]["max_mismatch_s"],
        "Realistic control-plane PTP": samples_by_regime["realistic_control_plane_ptp"]["max_mismatch_s"],
        "Conservative software / non-RT OS": np.concatenate([
            values["max_mismatch_s"]
            for name, values in samples_by_regime.items()
            if name.startswith("conservative_")
        ]),
    }

    # Violin rendering does not need every Monte Carlo point. Downsampling keeps
    # plotting quick without changing the underlying saved statistics.
    plot_samples = []
    for values in groups.values():
        sample_size = min(values.size, 30_000)
        indices = rng.choice(values.size, size=sample_size, replace=False)
        plot_samples.append(_microseconds(values[indices]))

    fig, ax = plt.subplots(figsize=(9, 5.5), dpi=180)
    parts = ax.violinplot(plot_samples, showmeans=True, showmedians=True, showextrema=False)
    for body in parts["bodies"]:
        body.set_facecolor("#267D8C")
        body.set_edgecolor("#173E49")
        body.set_alpha(0.75)
    ax.set_xticks(range(1, 4), groups.keys(), rotation=12, ha="right")
    ax.set_ylabel(r"Maximum verifier mismatch $\Delta t_{\max}$ ($\mu$s)")
    ax.set_title("Three-regime timing mismatch comparison")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_dir / "three_regime_violin_plot.png")
    plt.close(fig)


def save_conservative_heatmaps(samples_by_regime, output_dir):
    """Save conservative-grid heatmaps for p95 and the 99% acceptance tolerance."""
    ptp_values_us = (10, 20, 50)
    ctrl_values_us = (2, 5, 10)
    p95_grid_us = np.zeros((len(ptp_values_us), len(ctrl_values_us)))
    p99_grid_us = np.zeros_like(p95_grid_us)

    for row, sigma_ptp_us in enumerate(ptp_values_us):
        for column, sigma_ctrl_us in enumerate(ctrl_values_us):
            name = f"conservative_ptp_{sigma_ptp_us}us_ctrl_{sigma_ctrl_us}us"
            mismatch_us = _microseconds(samples_by_regime[name]["max_mismatch_s"])
            p95_grid_us[row, column] = np.percentile(mismatch_us, 95)
            # The minimum tolerance for 99% honest acceptance is the p99 value.
            p99_grid_us[row, column] = np.percentile(mismatch_us, 99)

    for filename, title, grid in (
        ("conservative_p95_heatmap.png", r"95th percentile of $\Delta t_{\max}$", p95_grid_us),
        ("conservative_99pct_tolerance_heatmap.png", r"Minimum $\epsilon_{\mathrm{sync}}$ for 99% acceptance", p99_grid_us),
    ):
        fig, ax = plt.subplots(figsize=(6.5, 5), dpi=180)
        image = ax.imshow(grid, cmap="viridis", aspect="auto")
        ax.set_xticks(range(len(ctrl_values_us)), [str(value) for value in ctrl_values_us])
        ax.set_yticks(range(len(ptp_values_us)), [str(value) for value in ptp_values_us])
        ax.set_xlabel(r"$\sigma_{\mathrm{ctrl}}$ ($\mu$s)")
        ax.set_ylabel(r"$\sigma_{\mathrm{PTP}}$ ($\mu$s)")
        ax.set_title(title)
        for row in range(grid.shape[0]):
            for column in range(grid.shape[1]):
                ax.text(column, row, f"{grid[row, column]:.1f}", ha="center", va="center", color="white")
        colorbar = fig.colorbar(image, ax=ax)
        colorbar.set_label(r"Time ($\mu$s)")
        fig.tight_layout()
        fig.savefig(output_dir / filename)
        plt.close(fig)

    return p95_grid_us, p99_grid_us


def save_summary_csv(samples_by_regime, output_dir):
    """Save parameter values and maximum-mismatch summary statistics."""
    rows = []
    for name, samples in samples_by_regime.items():
        summary = mismatch_summary(samples["max_mismatch_s"])
        regime = samples["regime"]
        rows.append({
            "regime": name,
            "mu_b_s": regime.get("mu_b_s", 0.0),
            "sigma_b_s": regime["sigma_b_s"],
            "sigma_ptp_s": regime["sigma_ptp_s"],
            "sigma_ctrl_s": regime["sigma_ctrl_s"],
            **summary,
        })

    fieldnames = list(rows[0].keys())
    with (output_dir / "summary_statistics.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return rows


def save_release_pairwise_summary_csv(samples_by_regime, output_dir):
    """Save compact statistics for release errors and pairwise differences."""
    rows = []
    for name, samples in samples_by_regime.items():
        for column, verifier in enumerate(VERIFIER_NAMES):
            values = samples["release_errors_s"][:, column]
            rows.append({
                "regime": name,
                "metric": f"release_error_{verifier}",
                "mean_s": float(np.mean(values)),
                "std_s": float(np.std(values, ddof=1)),
                "median_s": float(np.median(values)),
                "p05_s": float(np.percentile(values, 5)),
                "p95_s": float(np.percentile(values, 95)),
            })
        for column, (i, j) in enumerate(PAIRWISE_INDICES):
            values = samples["pairwise_errors_s"][:, column]
            rows.append({
                "regime": name,
                "metric": f"delta_t_{i}{j}",
                "mean_s": float(np.mean(values)),
                "std_s": float(np.std(values, ddof=1)),
                "median_s": float(np.median(values)),
                "p05_s": float(np.percentile(values, 5)),
                "p95_s": float(np.percentile(values, 95)),
            })

    fieldnames = list(rows[0].keys())
    with (output_dir / "release_pairwise_summary.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return rows


def save_raw_metrics(samples_by_regime, output_dir):
    """Save release, pairwise, and maximum mismatch arrays in compressed form."""
    raw_dir = output_dir / "raw_metrics"
    raw_dir.mkdir(parents=True, exist_ok=True)
    for name, samples in samples_by_regime.items():
        np.savez_compressed(
            raw_dir / f"{_safe_name(name)}.npz",
            release_errors_s=samples["release_errors_s"],
            pairwise_errors_s=samples["pairwise_errors_s"],
            max_mismatch_s=samples["max_mismatch_s"],
            residual_offsets_s=samples["residual_offsets_s"],
            ptp_jitter_s=samples["ptp_jitter_s"],
            control_jitter_s=samples["control_jitter_s"],
        )


def run_timing_analysis(trials=100_000, random_seed=DEFAULT_RANDOM_SEED,
                        results_dir=DEFAULT_RESULTS_DIR, tolerance_points=300):
    """Run all requested Monte Carlo analyses and save metrics and plots."""
    if trials <= 0:
        raise ValueError("trials must be positive")
    results_dir = Path(results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)

    master_rng = np.random.default_rng(random_seed)
    samples_by_regime = {}
    for regime in get_ptp_parameter_regimes():
        regime_seed = int(master_rng.integers(0, np.iinfo(np.uint32).max))
        samples_by_regime[regime["name"]] = sample_regime(
            regime,
            trials,
            np.random.default_rng(regime_seed),
        )

    global_p99_s = max(np.percentile(samples["max_mismatch_s"], 99.9) for samples in samples_by_regime.values())
    tolerances_s = np.linspace(0, global_p99_s * 1.1, tolerance_points)

    summary_rows = save_summary_csv(samples_by_regime, results_dir)
    release_pairwise_rows = save_release_pairwise_summary_csv(samples_by_regime, results_dir)
    save_raw_metrics(samples_by_regime, results_dir)
    save_histograms(samples_by_regime, results_dir)
    save_acceptance_plot(samples_by_regime, tolerances_s, results_dir)
    save_regime_violin_plot(samples_by_regime, results_dir, master_rng)
    p95_grid_us, p99_grid_us = save_conservative_heatmaps(samples_by_regime, results_dir)

    acceptance_table = {"tolerance_s": tolerances_s}
    for name, samples in samples_by_regime.items():
        acceptance_table[name] = acceptance_probabilities(samples["max_mismatch_s"], tolerances_s)
    np.savez_compressed(results_dir / "acceptance_curves.npz", **acceptance_table)

    metadata = {
        "units": {"time": "s", "distance": "km"},
        "trials_per_regime": trials,
        "random_seed": random_seed,
        "regime_count": len(samples_by_regime),
        "pairwise_error_columns": ["e_v0_minus_e_v1", "e_v0_minus_e_v2", "e_v1_minus_e_v2"],
        "conservative_p95_grid_us": p95_grid_us.tolist(),
        "conservative_p99_grid_us": p99_grid_us.tolist(),
        "summary_statistics": summary_rows,
        "release_pairwise_summary": release_pairwise_rows,
    }
    with (results_dir / "analysis_metadata.json").open("w") as handle:
        json.dump(metadata, handle, indent=2)

    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=100_000, help="Monte Carlo trials per regime")
    parser.add_argument("--seed", type=int, default=DEFAULT_RANDOM_SEED, help="Fixed random seed")
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    args = parser.parse_args()

    metadata = run_timing_analysis(
        trials=args.trials,
        random_seed=args.seed,
        results_dir=args.results_dir,
    )
    print(f"Saved {metadata['regime_count']} regimes to {args.results_dir}")


if __name__ == "__main__":
    main()
