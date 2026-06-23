#%%
import netsquid as ns
import numpy as np
from contextlib import redirect_stdout
from io import StringIO
from netsquid.nodes import Node
import matplotlib.pyplot as plt
from component import (
    QuantumConnection,
    ClassicalConnection,
    CLASSICAL_SIGNAL_SPEED_KM_S,
    QUBIT_SIGNAL_SPEED_KM_S,
    propagation_delay_s,
    propagation_delay_ns,
    seconds_to_ns,
    ns_to_seconds,
)
from verifier import V0Protocol, V1Protocol, V2Protocol
from prover import PProtocol
from bool_function import bool_func
#%%
DEFAULT_RANDOM_SEED = 20260609

PTP_PARAMETER_REGIMES = {
    'ideal_hardware_ptp': {
        'mu_b_s': 0.0,
        'sigma_b_s': 0.0,
        'sigma_ptp_s': 40e-9,
        'sigma_ctrl_s': 0.0,
    },
    'realistic_control_plane_ptp': {
        'mu_b_s': 0.0,
        'sigma_b_s': 0.0,
        'sigma_ptp_s': 40e-9,
        'sigma_ctrl_s': 2.86e-6,
    },
}


def get_ptp_parameter_regimes():
    """Return the two fixed regimes and the nine conservative regime variants."""
    regimes = [
        {'name': name, **parameters}
        for name, parameters in PTP_PARAMETER_REGIMES.items()
    ]
    for sigma_ptp_us in (10, 20, 50):
        for sigma_ctrl_us in (2, 5, 10):
            regimes.append({
                'name': f'conservative_ptp_{sigma_ptp_us}us_ctrl_{sigma_ctrl_us}us',
                'mu_b_s': 0.0,
                'sigma_b_s': 0.0,
                'sigma_ptp_s': sigma_ptp_us * 1e-6,
                'sigma_ctrl_s': sigma_ctrl_us * 1e-6,
            })
    return regimes


def calculate_ptp_schedule_s(classical_distances_km, earliest_release_s,
                             sigma_b_s=0, sigma_ptp_s=0, sigma_ctrl_s=0,
                             rng=None, synchronize_arrivals=True):
    """Sample release times using the requested timing-error model.

    All values in this function are in seconds, except distances, which are km.
    For each verifier i:

        release_i = ideal_i + b_i + epsilon_ptp_i + epsilon_ctrl_i

    The ideal release times compensate deterministic classical propagation
    delays so that all keys reach the prover at the same target time.
    """

    if len(classical_distances_km) != 3:
        raise ValueError('classical_distances_km must contain distances for V0, V1 and V2')
    if sigma_b_s < 0 or sigma_ptp_s < 0 or sigma_ctrl_s < 0:
        raise ValueError('all timing-error standard deviations must be non-negative')
    if rng is None:
        rng = np.random.default_rng(DEFAULT_RANDOM_SEED)

    one_way_delays_s = [
        propagation_delay_s(distance_km, CLASSICAL_SIGNAL_SPEED_KM_S)
        for distance_km in classical_distances_km
    ]
    target_arrival_s = earliest_release_s + max(one_way_delays_s)
    if synchronize_arrivals:
        ideal_release_times_s = [
            target_arrival_s - delay_s
            for delay_s in one_way_delays_s
        ]
    else:
        ideal_release_times_s = [earliest_release_s] * 3

    residual_offsets_s = rng.normal(0, sigma_b_s, 3)
    ptp_jitter_s = rng.normal(0, sigma_ptp_s, 3)
    control_jitter_s = rng.normal(0, sigma_ctrl_s, 3)
    total_timing_errors_s = residual_offsets_s + ptp_jitter_s + control_jitter_s
    release_times_s = [
        max(0.0, ideal + error)
        for ideal, error in zip(ideal_release_times_s, total_timing_errors_s)
    ]
    expected_arrival_times_s = [
        release + delay
        for release, delay in zip(release_times_s, one_way_delays_s)
    ]

    return {
        'units': {'distance': 'km', 'time': 's'},
        'one_way_delays_s': one_way_delays_s,
        'ideal_release_times_s': ideal_release_times_s,
        'residual_offsets_s': residual_offsets_s.tolist(),
        'ptp_jitter_s': ptp_jitter_s.tolist(),
        'control_jitter_s': control_jitter_s.tolist(),
        'total_timing_errors_s': total_timing_errors_s.tolist(),
        'release_times_s': release_times_s,
        'expected_arrival_times_s': expected_arrival_times_s,
        'target_arrival_s': target_arrival_s if synchronize_arrivals else None,
    }


def check_result(v0_protocol, v1_protocol, v2_protocol, classical_distances_km,
                 allowed_time_window_s=0):
    """Validate commitment, answer consistency, and classical RTT in seconds."""

    if len(classical_distances_km) != 3:
        raise ValueError('classical_distances_km must contain distances for V0, V1 and V2')
    if allowed_time_window_s < 0:
        raise ValueError('allowed_time_window_s must be non-negative')

    a = v0_protocol.get_answer()
    b = v1_protocol.get_answer()
    c = v2_protocol.get_answer()
    m = v0_protocol.get_result()
    commitments = (
        v0_protocol.get_commitment(),
        v1_protocol.get_commitment(),
        v2_protocol.get_commitment(),
    )

    if None in commitments:
        print('Commitment missing')
        return False

    if commitments[0] != commitments[1] or commitments[0] != commitments[2]:
        print('Commitment mismatch')
        return False

    if commitments[0] == 0:
        print('loss')
        return False

    if a == 'Loss' or b == 'Loss' or c == 'Loss' or a is None or b is None or c is None:
        print('loss')
        return False

    if a != b or a != m or c != m or a != c:
        print('Wrong')
        return False

    verifier_protocols = (v0_protocol, v1_protocol, v2_protocol)

    for index, (protocol, distance_km) in enumerate(zip(verifier_protocols, classical_distances_km)):
        actual_round_trip_time_ns = protocol.get_round_trip_time()
        ideal_round_trip_time_s = 2 * propagation_delay_s(
            distance_km,
            CLASSICAL_SIGNAL_SPEED_KM_S,
        )
        if actual_round_trip_time_ns is None:
            print(f'V{index} round-trip time missing')
            return False

        actual_round_trip_time_s = ns_to_seconds(actual_round_trip_time_ns)
        timing_error_s = abs(actual_round_trip_time_s - ideal_round_trip_time_s)

        if timing_error_s > allowed_time_window_s:
            print(
                f'V{index} timing rejected: actual RTT={actual_round_trip_time_s:.9e} s, '
                f'ideal RTT={ideal_round_trip_time_s:.9e} s, '
                f'error={timing_error_s:.9e} s, '
                f'window={allowed_time_window_s:.9e} s'
            )
            return False

    print('Correct')
    return True


def _resolve_ptp_regime(regime, sigma_b_s, sigma_ptp_s, sigma_ctrl_s):
    """Resolve a named regime, or use explicitly supplied standard deviations."""
    if regime is None:
        values = {
            'name': 'custom',
            'sigma_b_s': sigma_b_s,
            'sigma_ptp_s': sigma_ptp_s,
            'sigma_ctrl_s': sigma_ctrl_s,
        }
    elif isinstance(regime, str):
        named_regimes = {
            values['name']: values
            for values in get_ptp_parameter_regimes()
        }
        if regime not in named_regimes:
            raise ValueError(f'Unknown fixed PTP regime: {regime}')
        values = dict(named_regimes[regime])
    else:
        values = dict(regime)
        values.setdefault('name', 'custom')

    for key in ('sigma_b_s', 'sigma_ptp_s', 'sigma_ctrl_s'):
        if key not in values or values[key] < 0:
            raise ValueError(f'{key} must be present and non-negative')
    return values


def _timing_summary_s(samples_s):
    """Return compact Monte Carlo statistics for a list of seconds values."""
    valid_samples = np.asarray([value for value in samples_s if value is not None], dtype=float)
    if valid_samples.size == 0:
        return {'mean_s': None, 'p95_s': None, 'max_s': None}
    return {
        'mean_s': float(np.mean(valid_samples)),
        'p95_s': float(np.percentile(valid_samples, 95)),
        'max_s': float(np.max(valid_samples)),
    }


def honest_ptp_sync(round, quantum_distance_km, classical_distances_km, x, y, z,
                    measurement_error=0, loss_rate=0, spam=False, ptp_sync=True,
                    regime=None, sigma_b_s=0, sigma_ptp_s=0, sigma_ctrl_s=0,
                    allowed_time_window_s=0, random_seed=DEFAULT_RANDOM_SEED):
    """Run Monte Carlo trials of the QPV-commitment PTP timing model.

    Distance inputs are km. Every timing-model input and every returned timing
    value is seconds. NetSquid itself schedules events in ns, so release times
    are converted to ns only when passed into verifier protocols.
    """
    if round <= 0:
        raise ValueError('round must be positive')
    if len(classical_distances_km) != 3:
        raise ValueError('classical_distances_km must contain distances for V0, V1 and V2')
    if allowed_time_window_s < 0:
        raise ValueError('allowed_time_window_s must be non-negative')

    resolved_regime = _resolve_ptp_regime(regime, sigma_b_s, sigma_ptp_s, sigma_ctrl_s)
    rng = np.random.default_rng(random_seed)

    quantum_delay_s = propagation_delay_s(quantum_distance_km, QUBIT_SIGNAL_SPEED_KM_S)
    classical_delays_s = [
        propagation_delay_s(distance_km, CLASSICAL_SIGNAL_SPEED_KM_S)
        for distance_km in classical_distances_km
    ]
    # The keys are released only after the commitment can reach every verifier.
    earliest_release_s = quantum_delay_s + max(classical_delays_s)

    accepted_counter = 0
    schedules = []
    actual_arrival_times_s = []
    arrival_spreads_s = []
    round_trip_times_s = []
    round_trip_errors_s = []

    for _ in range(round):
        ns.sim_reset()
        schedule = calculate_ptp_schedule_s(
            classical_distances_km,
            earliest_release_s,
            sigma_b_s=resolved_regime['sigma_b_s'],
            sigma_ptp_s=resolved_regime['sigma_ptp_s'],
            sigma_ctrl_s=resolved_regime['sigma_ctrl_s'],
            rng=rng,
            synchronize_arrivals=ptp_sync,
        )
        schedules.append(schedule)

        node_v0 = Node('v0', port_names=['quantum', 'v0p'])
        node_p = Node('p', port_names=['quantum', 'pv0', 'pv1', 'pv2'])
        node_v1 = Node('v1', port_names=['v1p'])
        node_v2 = Node('v2', port_names=['v2p'])

        verifier_nodes = (node_v0, node_v1, node_v2)
        verifier_ports = ('v0p', 'v1p', 'v2p')
        prover_ports = ('pv0', 'pv1', 'pv2')
        for index, classical_distance_km in enumerate(classical_distances_km):
            connection = ClassicalConnection(
                length=classical_distance_km,
                name=f'ptp_classical_{index}',
                direction='Bi',
            )
            verifier_nodes[index].ports[verifier_ports[index]].connect(connection.ports['A'])
            node_p.ports[prover_ports[index]].connect(connection.ports['B'])

        q_connection = QuantumConnection(
            name='Channel_A2B',
            length=quantum_distance_km,
            direction='A2B',
            p_loss_length=loss_rate,
        )
        node_v0.ports['quantum'].connect(q_connection.ports['A'])
        node_p.ports['quantum'].connect(q_connection.ports['B'])

        # Explicit unit boundary: model seconds -> NetSquid nanoseconds.
        release_times_ns = [seconds_to_ns(value) for value in schedule['release_times_s']]
        v0_protocol = V0Protocol(
            node=node_v0, x=x, y=y, z=z, len=quantum_distance_km,
            p=measurement_error, spam=spam, key_send_delay=release_times_ns[0],
        )
        v1_protocol = V1Protocol(
            node=node_v1, y=y, len=quantum_distance_km,
            key_send_delay=release_times_ns[1],
        )
        v2_protocol = V2Protocol(
            node=node_v2, z=z, len=quantum_distance_km,
            key_send_delay=release_times_ns[2],
        )
        p_protocol = PProtocol(node=node_p, p=measurement_error, len=quantum_distance_km)

        p_protocol.start()
        v0_protocol.start()
        v1_protocol.start()
        v2_protocol.start()
        ns.sim_run()

        if check_result(
            v0_protocol,
            v1_protocol,
            v2_protocol,
            classical_distances_km,
            allowed_time_window_s=allowed_time_window_s,
        ):
            accepted_counter += 1

        arrivals_ns = p_protocol.get_key_arrival_times()
        actual_arrival_times_s.append({
            key: ns_to_seconds(value)
            for key, value in arrivals_ns.items()
        })
        spread_ns = p_protocol.get_key_arrival_spread()
        arrival_spreads_s.append(ns_to_seconds(spread_ns) if spread_ns is not None else None)

        current_rtt_s = {}
        for verifier, protocol in (
            ('v0', v0_protocol),
            ('v1', v1_protocol),
            ('v2', v2_protocol),
        ):
            rtt_ns = protocol.get_round_trip_time()
            current_rtt_s[verifier] = ns_to_seconds(rtt_ns) if rtt_ns is not None else None
        round_trip_times_s.append(current_rtt_s)
        round_trip_errors_s.append({
            verifier: (
                abs(actual_s - 2 * propagation_delay_s(distance_km, CLASSICAL_SIGNAL_SPEED_KM_S))
                if actual_s is not None else None
            )
            for verifier, actual_s, distance_km in zip(
                ('v0', 'v1', 'v2'),
                current_rtt_s.values(),
                classical_distances_km,
            )
        })

    return {
        'units': {'distance': 'km', 'time': 's'},
        'trials': round,
        'random_seed': random_seed,
        'regime': resolved_regime,
        'ptp_sync': ptp_sync,
        'quantum_distance_km': quantum_distance_km,
        'classical_distances_km': tuple(classical_distances_km),
        'allowed_time_window_s': allowed_time_window_s,
        'acceptance_rate': accepted_counter / round,
        'error_rate': (round - accepted_counter) / round,
        'schedules': schedules,
        'actual_arrival_times_s': actual_arrival_times_s,
        'arrival_spreads_s': arrival_spreads_s,
        'arrival_spread_summary_s': _timing_summary_s(arrival_spreads_s),
        'round_trip_times_s': round_trip_times_s,
        'round_trip_errors_s': round_trip_errors_s,
    }


def run_ptp_timing_regimes(round, quantum_distance_km, classical_distances_km,
                           x, y, z, allowed_time_window_s,
                           measurement_error=0, loss_rate=0, spam=False,
                           random_seed=DEFAULT_RANDOM_SEED, verbose=False):
    """Run Monte Carlo experiments for every requested PTP parameter regime."""
    results = {}
    for index, regime in enumerate(get_ptp_parameter_regimes()):
        kwargs = dict(
            round=round,
            quantum_distance_km=quantum_distance_km,
            classical_distances_km=classical_distances_km,
            x=x,
            y=y,
            z=z,
            measurement_error=measurement_error,
            loss_rate=loss_rate,
            spam=spam,
            regime=regime,
            allowed_time_window_s=allowed_time_window_s,
            random_seed=random_seed + index,
        )
        if verbose:
            results[regime['name']] = honest_ptp_sync(**kwargs)
        else:
            # Existing protocols print per-trial diagnostics; silence them for
            # large Monte Carlo batches while retaining them in direct calls.
            with redirect_stdout(StringIO()):
                results[regime['name']] = honest_ptp_sync(**kwargs)
    return results


#%% Run the simulation
def honest_distance_error(round, distance, x, y, z, measurement_error=0.3, loss_rate=0.2,
                          spam=False, allowed_time_window_s=0):
    fibre_distance = np.arange(1, distance)
    p_err = []
    time = []
    for d in fibre_distance:
        correct_counter = 0
        for i in range(round):
            ns.sim_reset()
            # Init three nodes
            node_v0 = Node('v0', port_names = ['quantum', 'v0p'])
            node_p = Node('p', port_names=['quantum', 'pv0', 'pv1', 'pv2'])
            node_v1 = Node('v1', port_names=['v1p'])
            node_v2 = Node('v2', port_names=['v2p'])
            # Classical channel with fibre delay = distance /3e5, connection between V0 and P
            c_connection1 = ClassicalConnection(length=d, name='p0v1', direction='Bi')
            node_v0.ports['v0p'].connect(c_connection1.ports['A'])
            node_p.ports['pv0'].connect(c_connection1.ports['B'])
            # Classical connection between P and V1
            c_connection2 = ClassicalConnection(length=d, name='v1p', direction='Bi')
            node_v1.ports['v1p'].connect(c_connection2.ports['A'])
            node_p.ports['pv1'].connect(c_connection2.ports['B'])
            # Classical connection between P and V2
            c_connection3 = ClassicalConnection(length=d, name='v2p', direction='Bi')
            node_v2.ports['v2p'].connect(c_connection3.ports['A'])
            node_p.ports['pv2'].connect(c_connection3.ports['B'])
            # Quantum connection between V0 and P, with delay = d/2e5, and attenuation
            q_connection = QuantumConnection(name="Channel_A2B", length=d, direction='A2B',  p_loss_length=loss_rate)
            node_v0.ports['quantum'].connect(q_connection.ports['A'])
            node_p.ports['quantum'].connect(q_connection.ports['B'])

            v0_protocol = V0Protocol(node=node_v0, x=x, y=y, z=z, len=d, p=measurement_error, spam=spam, )
            p_protocol = PProtocol(node=node_p, p=measurement_error, len=d)
            v1_protocol = V1Protocol(node=node_v1, y=y, len=d)
            v2_protocol = V2Protocol(node=node_v2, z=z, len=d)
            # Start protocol
            p_protocol.start()
            v0_protocol.start()
            v1_protocol.start()
            v2_protocol.start()

            stats = ns.sim_run()
            if check_result(
                v0_protocol, v1_protocol, v2_protocol, (d, d, d),
                allowed_time_window_s=allowed_time_window_s,
            ):
                correct_counter = correct_counter + 1
            # Reset the timer
            ns.sim_reset()

        time.append(v0_protocol.get_elapsed_time())
        p_err.append((round-correct_counter)/round)
    return p_err, fibre_distance, time

#%% Run under different quantum error rate
def honest_quantum_error(round, distance, x, y, z, measurement_error, loss_rate,
                         spam=False, sp=False, me=True, allowed_time_window_s=0):
    p_err = []
    time = []
    d = distance
    for r in measurement_error:
        correct_counter = 0
        for i in range(round):
            ns.sim_reset()
            # Init three nodes
            node_v0 = Node('v0', port_names = ['quantum', 'v0p'])
            node_p = Node('p', port_names=['quantum', 'pv0', 'pv1', 'pv2'])
            node_v1 = Node('v1', port_names=['v1p'])
            node_v2 = Node('v2', port_names=['v2p'])
            # Classical channel with fibre delay = distance /3e5, connection between V0 and P
            c_connection1 = ClassicalConnection(length=d, name='p0v1', direction='Bi')
            node_v0.ports['v0p'].connect(c_connection1.ports['A'])
            node_p.ports['pv0'].connect(c_connection1.ports['B'])
            # Classical connection between P and V1
            c_connection2 = ClassicalConnection(length=d, name='v1p', direction='Bi')
            node_v1.ports['v1p'].connect(c_connection2.ports['A'])
            node_p.ports['pv1'].connect(c_connection2.ports['B'])
            # Classical connection between P and V2
            c_connection3 = ClassicalConnection(length=d, name='v2p', direction='Bi')
            node_v2.ports['v2p'].connect(c_connection3.ports['A'])
            node_p.ports['pv2'].connect(c_connection3.ports['B'])
            # Quantum connection between V0 and P, with delay = d/2e5, and attenuation
            q_connection = QuantumConnection(name="Channel_A2B", length=d, direction='A2B',  p_loss_length=loss_rate)
            node_v0.ports['quantum'].connect(q_connection.ports['A'])
            node_p.ports['quantum'].connect(q_connection.ports['B'])

            v0_protocol = V0Protocol(node=node_v0, x=x, y=y, z=z, len=d, p=r, spam=spam, sp=sp, me=me)
            p_protocol = PProtocol(node=node_p, p=r, me=me, len=d)
            v1_protocol = V1Protocol(node=node_v1, y=y, len=d)
            v2_protocol = V2Protocol(node=node_v2, z=z, len=d)
            # Start protocol
            p_protocol.start()
            v0_protocol.start()
            v1_protocol.start()
            v2_protocol.start()
            
            stats = ns.sim_run()
            if check_result(
                v0_protocol, v1_protocol, v2_protocol, (d, d, d),
                allowed_time_window_s=allowed_time_window_s,
            ):
                correct_counter = correct_counter + 1
            # Reset the timer
            ns.sim_reset()

        time.append(v0_protocol.get_elapsed_time())
        p_err.append((round-correct_counter)/round)
    return p_err
#%% Run under different quantum error rate
def honest_photon_loss(round, x, y, z, eta, measurement_error=0.4, spam=False,
                       sp=False, me=True, allowed_time_window_s=0):
    p_err = []
    d = 10
    for e in eta:
        correct_counter = 0
        for i in range(round):
            ns.sim_reset()
            # Init three nodes
            node_v0 = Node('v0', port_names = ['quantum', 'v0p'])
            node_p = Node('p', port_names=['quantum', 'pv0', 'pv1', 'pv2'])
            node_v1 = Node('v1', port_names=['v1p'])
            node_v2 = Node('v2', port_names=['v2p'])
            # Classical channel with fibre delay = distance /3e5, connection between V0 and P
            c_connection1 = ClassicalConnection(length=d, name='p0v1', direction='Bi')
            node_v0.ports['v0p'].connect(c_connection1.ports['A'])
            node_p.ports['pv0'].connect(c_connection1.ports['B'])
            # Classical connection between P and V1
            c_connection2 = ClassicalConnection(length=d, name='v1p', direction='Bi')
            node_v1.ports['v1p'].connect(c_connection2.ports['A'])
            node_p.ports['pv1'].connect(c_connection2.ports['B'])
            # Classical connection between P and V2
            c_connection3 = ClassicalConnection(length=d, name='v2p', direction='Bi')
            node_v2.ports['v2p'].connect(c_connection3.ports['A'])
            node_p.ports['pv2'].connect(c_connection3.ports['B'])
            # Quantum connection between V0 and P, with delay = d/2e5, and attenuation
            q_connection = QuantumConnection(name="Channel_A2B", length=d, direction='A2B',  p_loss_length=e)
            node_v0.ports['quantum'].connect(q_connection.ports['A'])
            node_p.ports['quantum'].connect(q_connection.ports['B'])

            v0_protocol = V0Protocol(node=node_v0, x=x, y=y, z=z, len=d, p=measurement_error, spam=spam, sp=sp, me=me)
            p_protocol = PProtocol(node=node_p, p=measurement_error, me=me, len=d)
            v1_protocol = V1Protocol(node=node_v1, y=y, len=d)
            v2_protocol = V2Protocol(node=node_v2, z=z, len=d)

            # Start protocol
            p_protocol.start()
            v0_protocol.start()
            v1_protocol.start()
            v2_protocol.start()
            
            stats = ns.sim_run()
            if check_result(
                v0_protocol, v1_protocol, v2_protocol, (d, d, d),
                allowed_time_window_s=allowed_time_window_s,
            ):
                correct_counter = correct_counter + 1
            # Reset the timer
            ns.sim_reset()
        p_err.append((round-correct_counter)/round)
    return p_err
