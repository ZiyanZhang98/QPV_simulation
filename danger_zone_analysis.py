"""Distribution-grounded QPV danger-zone and unsynchronization analysis.

All internal units are SI:
  - timing: seconds
  - coordinates and distances: meters
  - area: square meters

For a candidate point x, the relative timing residual for verifier i is

    tau_i(x) = (||x - v_i|| - ||p - v_i||) / signal_speed.

The grid point belongs to the danger zone for mismatch delta_t when

    max_i tau_i(x) - min_i tau_i(x) <= delta_t.

The threshold field is precomputed once. Area evaluation for many Monte Carlo
samples then uses a sorted threshold array instead of recomputing the grid.
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
from timing_analysis import mismatch_summary, sample_regime


LIGHT_SPEED_M_S = 299_792_458.0
DEFAULT_REFRACTIVE_INDEX = 1.468
DEFAULT_RESULTS_DIR = Path("results/danger_zone_analysis")
DEFAULT_VERIFIERS_M = np.array([[0.0, 0.0], [15_000.0, 0.0], [6_000.0, 10_000.0]])
DEFAULT_PROVER_M = np.array([7_000.0, 4_000.0])
DEFAULT_UNSYNC_RATES_S_PER_S = np.array([0, 1e-9, 5e-9, 10e-9, 50e-9, 100e-9, 500e-9, 1e-6])


def summary_statistics(values):
    """Return requested descriptive statistics for a one-dimensional array."""
    values = np.asarray(values, dtype=float)
    return {
        "mean": float(np.mean(values)),
        "std": float(np.std(values, ddof=1)),
        "median": float(np.median(values)),
        "p90": float(np.percentile(values, 90)),
        "p95": float(np.percentile(values, 95)),
        "p99": float(np.percentile(values, 99)),
        "max": float(np.max(values)),
    }


def build_geometry_cache(verifiers_m=DEFAULT_VERIFIERS_M, prover_m=DEFAULT_PROVER_M,
                         refractive_index=DEFAULT_REFRACTIVE_INDEX, grid_size=401,
                         margin_m=3_000.0):
    """Precompute the danger-zone mismatch threshold at every grid point."""
    verifiers_m = np.asarray(verifiers_m, dtype=float)
    prover_m = np.asarray(prover_m, dtype=float)
    if verifiers_m.shape != (3, 2):
        raise ValueError("verifiers_m must have shape (3, 2)")
    if prover_m.shape != (2,):
        raise ValueError("prover_m must have shape (2,)")
    if refractive_index <= 0 or grid_size < 2 or margin_m < 0:
        raise ValueError("invalid geometry/grid configuration")

    minimum = np.minimum(verifiers_m.min(axis=0), prover_m) - margin_m
    maximum = np.maximum(verifiers_m.max(axis=0), prover_m) + margin_m
    x_m = np.linspace(minimum[0], maximum[0], grid_size)
    y_m = np.linspace(minimum[1], maximum[1], grid_size)
    grid_x_m, grid_y_m = np.meshgrid(x_m, y_m)
    points_m = np.stack((grid_x_m, grid_y_m), axis=-1)

    signal_speed_m_s = LIGHT_SPEED_M_S / refractive_index
    candidate_distances_m = np.linalg.norm(points_m[:, :, None, :] - verifiers_m[None, None, :, :], axis=-1)
    honest_distances_m = np.linalg.norm(prover_m[None, :] - verifiers_m, axis=1)
    relative_times_s = (candidate_distances_m - honest_distances_m[None, None, :]) / signal_speed_m_s
    threshold_field_s = np.ptp(relative_times_s, axis=2)

    cell_area_m2 = (x_m[1] - x_m[0]) * (y_m[1] - y_m[0])
    sorted_thresholds_s = np.sort(threshold_field_s.ravel())
    return {
        "units": {"time": "s", "distance": "m", "area": "m^2"},
        "verifiers_m": verifiers_m,
        "prover_m": prover_m,
        "refractive_index": refractive_index,
        "signal_speed_m_s": signal_speed_m_s,
        "x_m": x_m,
        "y_m": y_m,
        "grid_x_m": grid_x_m,
        "grid_y_m": grid_y_m,
        "threshold_field_s": threshold_field_s,
        "sorted_thresholds_s": sorted_thresholds_s,
        "cell_area_m2": cell_area_m2,
    }


def danger_area_m2(delta_t_s, geometry):
    """Evaluate danger-zone area for scalar or array timing mismatch."""
    delta_t_s = np.asarray(delta_t_s, dtype=float)
    counts = np.searchsorted(geometry["sorted_thresholds_s"], delta_t_s, side="right")
    areas = counts * geometry["cell_area_m2"]
    return float(areas) if areas.ndim == 0 else areas


def safe_resynchronization_interval_s(delta_t_0_s, unsync_rate_s_per_s, delta_t_safe_s):
    """Compute the timing-based maximum safe interval with edge-case handling."""
    if delta_t_0_s > delta_t_safe_s:
        return 0.0
    if unsync_rate_s_per_s == 0:
        return float("inf")
    return max(0.0, (delta_t_safe_s - delta_t_0_s) / unsync_rate_s_per_s)


def _safe_name(name):
    return name.replace("/", "_").replace(" ", "_")


def _format_unsync_rate(rate_s_per_s):
    """Return a readable label while preserving the seconds/second model."""
    if rate_s_per_s == 0:
        return "0 ns/s"
    if rate_s_per_s >= 1e-6:
        return f"{rate_s_per_s * 1e6:g} us/s"
    return f"{rate_s_per_s * 1e9:g} ns/s"


def _save_contour(ax, geometry, delta_t_s, title):
    mask = geometry["threshold_field_s"] <= delta_t_s
    ax.contourf(geometry["grid_x_m"], geometry["grid_y_m"], mask.astype(float), levels=[-0.1, 0.5, 1.1],
                colors=["#F4F5F3", "#D55E4A"], alpha=0.85)
    verifiers = geometry["verifiers_m"]
    prover = geometry["prover_m"]
    ax.scatter(verifiers[:, 0], verifiers[:, 1], marker="^", s=45, color="#267D8C", label="Verifiers")
    ax.scatter(prover[0], prover[1], marker="x", s=55, color="black", label="Honest prover")
    ax.set_title(title)
    ax.set_aspect("equal")
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")


def save_stage_a_plots(regime_results, geometry, output_dir):
    """Generate Stage A distribution, area, relationship, and percentile contours."""
    stage_dir = output_dir / "stage_a"
    contour_dir = stage_dir / "percentile_contours"
    stage_dir.mkdir(parents=True, exist_ok=True)
    contour_dir.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(9, 5.5), dpi=180)
    for name, result in regime_results.items():
        ax.hist(result["delta_t_sync_s"] * 1e6, bins=90, density=True, histtype="step", linewidth=1.2,
                label=name.replace("_", " "))
    ax.set_xlabel(r"$\delta t_{\mathrm{sync}}$ ($\mu$s)")
    ax.set_ylabel("Probability density")
    ax.legend(fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(stage_dir / "A1_delta_t_sync_histograms.png")
    plt.close(fig)

    # A2 compares all concrete regimes; symmetric-log area scale makes small
    # hardware-PTP zones visible next to conservative software regimes.
    names = list(regime_results)
    area_samples_km2 = [regime_results[name]["danger_area_m2"] / 1e6 for name in names]
    fig, ax = plt.subplots(figsize=(12, 6), dpi=180)
    ax.boxplot(area_samples_km2, showfliers=False)
    ax.set_xticks(range(1, len(names) + 1), [name.replace("_", " ") for name in names], rotation=60, ha="right")
    ax.set_ylabel(r"Danger-zone area (km$^2$)")
    ax.set_yscale("symlog", linthresh=geometry["cell_area_m2"] / 1e6)
    fig.tight_layout()
    fig.savefig(stage_dir / "A2_danger_area_boxplot.png")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5.5), dpi=180)
    delta_grid_s = np.linspace(0, max(np.percentile(result["delta_t_sync_s"], 99.9) for result in regime_results.values()), 500)
    ax.plot(delta_grid_s * 1e6, danger_area_m2(delta_grid_s, geometry) / 1e6, color="#267D8C", linewidth=2.2)
    ax.set_xlabel(r"$\delta t_{\mathrm{sync}}$ ($\mu$s)")
    ax.set_ylabel(r"Danger-zone area (km$^2$)")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(stage_dir / "A3_mismatch_to_danger_area.png")
    plt.close(fig)

    for name, result in regime_results.items():
        percentiles_s = np.percentile(result["delta_t_sync_s"], [50, 95, 99])
        fig, axes = plt.subplots(1, 3, figsize=(15, 4.5), dpi=180, sharex=True, sharey=True)
        for ax, percentile, value_s in zip(axes, (50, 95, 99), percentiles_s):
            _save_contour(ax, geometry, value_s, f"P{percentile}: {value_s * 1e6:.2f} us")
        axes[0].legend(fontsize=8, loc="upper left")
        fig.suptitle(name.replace("_", " "))
        fig.tight_layout()
        fig.savefig(contour_dir / f"{_safe_name(name)}_P50_P95_P99.png")
        plt.close(fig)


def save_stage_b_plots(stage_b_results, geometry, output_dir, snapshot_times_s):
    """Generate Stage B timing, area-evolution, and danger-zone snapshot plots."""
    stage_dir = output_dir / "stage_b"
    snapshot_dir = stage_dir / "snapshots"
    stage_dir.mkdir(parents=True, exist_ok=True)
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    for name, result in stage_b_results.items():
        time_s = result["time_s"]
        fig, ax = plt.subplots(figsize=(8.5, 5.2), dpi=180)
        for rate_label, values in result["rates"].items():
            ax.plot(time_s, values["delta_t_sync_s"] * 1e6, label=rate_label)
        ax.axhline(result["delta_t_safe_s"] * 1e6, color="#B33A3A", linestyle="--", label="Safety threshold")
        ax.set_xlabel("Elapsed time since synchronization (s)")
        ax.set_ylabel(r"$\delta t_{\mathrm{sync}}(t)$ ($\mu$s)")
        ax.legend(fontsize=7, ncol=2)
        ax.grid(alpha=0.25)
        fig.tight_layout()
        fig.savefig(stage_dir / f"B1_{_safe_name(name)}_mismatch_vs_time.png")
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(8.5, 5.2), dpi=180)
        for rate_label, values in result["rates"].items():
            ax.plot(time_s, values["danger_area_m2"] / 1e6, label=rate_label)
        ax.set_xlabel("Elapsed time since synchronization (s)")
        ax.set_ylabel(r"Danger-zone area (km$^2$)")
        ax.legend(fontsize=7, ncol=2)
        ax.grid(alpha=0.25)
        fig.tight_layout()
        fig.savefig(stage_dir / f"B2_{_safe_name(name)}_area_vs_time.png")
        plt.close(fig)

        # Use the largest default unsync rate for snapshots so expansion is
        # clearly visible; delta_t_0 remains distribution-derived.
        largest_rate = max(values["unsync_rate_s_per_s"] for values in result["rates"].values())
        fig, axes = plt.subplots(1, len(snapshot_times_s), figsize=(5 * len(snapshot_times_s), 4.5), dpi=180,
                                 sharex=True, sharey=True)
        for ax, snapshot_time_s in zip(np.atleast_1d(axes), snapshot_times_s):
            delta_t_s = result["delta_t_0_s"] + largest_rate * snapshot_time_s
            _save_contour(ax, geometry, delta_t_s, f"t={snapshot_time_s:g} s")
        np.atleast_1d(axes)[0].legend(fontsize=8, loc="upper left")
        fig.suptitle(f"{name.replace('_', ' ')}; r={_format_unsync_rate(largest_rate)}")
        fig.tight_layout()
        fig.savefig(snapshot_dir / f"B3_{_safe_name(name)}_snapshots.png")
        plt.close(fig)


def run_danger_zone_analysis(trials=100_000, random_seed=DEFAULT_RANDOM_SEED,
                             results_dir=DEFAULT_RESULTS_DIR, grid_size=401,
                             margin_m=3_000.0, refractive_index=DEFAULT_REFRACTIVE_INDEX,
                             initial_quantile=0.99, delta_t_safe_s=10e-6,
                             t_max_s=1_000.0, time_samples=201,
                             unsync_rates_s_per_s=DEFAULT_UNSYNC_RATES_S_PER_S,
                             regimes=None):
    """Run Stage A and Stage B analyses and save all requested artifacts."""
    if not 0 < initial_quantile < 1:
        raise ValueError("initial_quantile must be between 0 and 1")
    results_dir = Path(results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    geometry = build_geometry_cache(
        refractive_index=refractive_index,
        grid_size=grid_size,
        margin_m=margin_m,
    )
    if regimes is None:
        regimes = get_ptp_parameter_regimes()

    rng = np.random.default_rng(random_seed)
    regime_results = {}
    stage_a_rows = []
    for regime in regimes:
        regime_rng = np.random.default_rng(int(rng.integers(0, np.iinfo(np.uint32).max)))
        samples = sample_regime(regime, trials, regime_rng)
        delta_t_sync_s = samples["max_mismatch_s"]
        areas_m2 = danger_area_m2(delta_t_sync_s, geometry)
        timing_summary = summary_statistics(delta_t_sync_s)
        area_summary = summary_statistics(areas_m2)
        regime_results[regime["name"]] = {
            "regime": regime,
            "delta_t_sync_s": delta_t_sync_s,
            "danger_area_m2": areas_m2,
            "timing_summary_s": timing_summary,
            "area_summary_m2": area_summary,
        }
        stage_a_rows.append({
            "regime": regime["name"],
            **{f"delta_t_{key}_s": value for key, value in timing_summary.items()},
            **{f"area_{key}_m2": value for key, value in area_summary.items()},
        })

    save_stage_a_plots(regime_results, geometry, results_dir)
    with (results_dir / "stage_a_summary.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(stage_a_rows[0]))
        writer.writeheader()
        writer.writerows(stage_a_rows)

    time_s = np.linspace(0, t_max_s, time_samples)
    stage_b_results = {}
    stage_b_rows = []
    for name, result in regime_results.items():
        delta_t_0_s = float(np.quantile(result["delta_t_sync_s"], initial_quantile))
        reference_area_m2 = danger_area_m2(delta_t_0_s, geometry)
        rate_results = {}
        for rate in np.asarray(unsync_rates_s_per_s, dtype=float):
            delta_t_s = delta_t_0_s + rate * time_s
            areas_m2 = danger_area_m2(delta_t_s, geometry)
            label = _format_unsync_rate(rate)
            safe_interval_s = safe_resynchronization_interval_s(delta_t_0_s, rate, delta_t_safe_s)
            rate_results[label] = {
                "unsync_rate_s_per_s": float(rate),
                "delta_t_sync_s": delta_t_s,
                "danger_area_m2": areas_m2,
                "normalized_expansion": areas_m2 / reference_area_m2 if reference_area_m2 > 0 else None,
                "safe_resynchronization_interval_s": safe_interval_s,
            }
            stage_b_rows.append({
                "regime": name,
                "delta_t_0_s": delta_t_0_s,
                "unsync_rate_s_per_s": rate,
                "safe_resynchronization_interval_s": safe_interval_s,
                "area_t0_m2": areas_m2[0],
                "area_tmax_m2": areas_m2[-1],
            })
        stage_b_results[name] = {
            "delta_t_0_s": delta_t_0_s,
            "delta_t_safe_s": delta_t_safe_s,
            "time_s": time_s,
            "rates": rate_results,
        }

    snapshot_times_s = [value for value in (0.0, 100.0, 500.0, 1_000.0) if value <= t_max_s]
    save_stage_b_plots(stage_b_results, geometry, results_dir, snapshot_times_s)
    with (results_dir / "stage_b_resynchronization_summary.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(stage_b_rows[0]))
        writer.writeheader()
        writer.writerows(stage_b_rows)

    # Save compact arrays needed to reproduce downstream analyses without
    # storing the full geometry tensor or every component-error sample.
    raw_dir = results_dir / "raw"
    raw_dir.mkdir(exist_ok=True)
    for name, result in regime_results.items():
        np.savez_compressed(
            raw_dir / f"{_safe_name(name)}.npz",
            delta_t_sync_s=result["delta_t_sync_s"],
            danger_area_m2=result["danger_area_m2"],
        )
    stage_b_raw_dir = results_dir / "stage_b_raw"
    stage_b_raw_dir.mkdir(exist_ok=True)
    for name, result in stage_b_results.items():
        payload = {
            "time_s": result["time_s"],
            "delta_t_0_s": np.asarray(result["delta_t_0_s"]),
            "delta_t_safe_s": np.asarray(result["delta_t_safe_s"]),
        }
        for rate_label, values in result["rates"].items():
            payload[f"{rate_label}_delta_t_sync_s"] = values["delta_t_sync_s"]
            payload[f"{rate_label}_danger_area_m2"] = values["danger_area_m2"]
            normalized = values["normalized_expansion"]
            if normalized is not None:
                payload[f"{rate_label}_normalized_expansion"] = normalized
        np.savez_compressed(stage_b_raw_dir / f"{_safe_name(name)}.npz", **payload)
    np.savez_compressed(
        results_dir / "geometry_cache.npz",
        verifiers_m=geometry["verifiers_m"],
        prover_m=geometry["prover_m"],
        x_m=geometry["x_m"],
        y_m=geometry["y_m"],
        threshold_field_s=geometry["threshold_field_s"],
        cell_area_m2=geometry["cell_area_m2"],
    )

    metadata = {
        "units": {"time": "s", "distance": "m", "area": "m^2"},
        "trials_per_regime": trials,
        "random_seed": random_seed,
        "refractive_index": refractive_index,
        "signal_speed_m_s": geometry["signal_speed_m_s"],
        "grid_size": grid_size,
        "margin_m": margin_m,
        "verifiers_m": geometry["verifiers_m"].tolist(),
        "prover_m": geometry["prover_m"].tolist(),
        "initial_quantile": initial_quantile,
        "delta_t_safe_s": delta_t_safe_s,
        "delta_t_safe_note": "Placeholder default; replace with a protocol-specific threshold when available.",
        "t_max_s": t_max_s,
        "time_samples": time_samples,
        "unsync_rates_s_per_s": np.asarray(unsync_rates_s_per_s).tolist(),
        "regimes": [dict(regime) for regime in regimes],
        "stage_a_summary": stage_a_rows,
        "stage_b_resynchronization_summary": [
            {
                **row,
                "safe_resynchronization_interval_s": (
                    row["safe_resynchronization_interval_s"]
                    if np.isfinite(row["safe_resynchronization_interval_s"])
                    else None
                ),
            }
            for row in stage_b_rows
        ],
    }
    with (results_dir / "analysis_metadata.json").open("w") as handle:
        json.dump(metadata, handle, indent=2, allow_nan=False)
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=100_000)
    parser.add_argument("--seed", type=int, default=DEFAULT_RANDOM_SEED)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    parser.add_argument("--grid-size", type=int, default=401)
    parser.add_argument("--margin-m", type=float, default=3_000.0)
    parser.add_argument("--refractive-index", type=float, default=DEFAULT_REFRACTIVE_INDEX)
    parser.add_argument("--initial-quantile", type=float, default=0.99)
    parser.add_argument("--delta-t-safe-s", type=float, default=10e-6)
    parser.add_argument("--t-max-s", type=float, default=1_000.0)
    parser.add_argument("--time-samples", type=int, default=201)
    args = parser.parse_args()
    run_danger_zone_analysis(
        trials=args.trials,
        random_seed=args.seed,
        results_dir=args.results_dir,
        grid_size=args.grid_size,
        margin_m=args.margin_m,
        refractive_index=args.refractive_index,
        initial_quantile=args.initial_quantile,
        delta_t_safe_s=args.delta_t_safe_s,
        t_max_s=args.t_max_s,
        time_samples=args.time_samples,
    )
    print(f"Saved danger-zone analysis to {args.results_dir}")


if __name__ == "__main__":
    main()
