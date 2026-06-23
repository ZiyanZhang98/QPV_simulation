#%%
import netsquid as ns
from netsquid.protocols import NodeProtocol
from component import (
    BitflipError,
    CLASSICAL_SIGNAL_SPEED_KM_S,
    QUBIT_SIGNAL_SPEED_KM_S,
    propagation_delay_ns,
)
from bool_function import bool_func
#%%
def parse_protocol_message(message):
    if isinstance(message, dict):
        return message.get('kind'), message.get('value')
    return 'answer', message


class V0Protocol(NodeProtocol):
    def __init__(self, len, node=None, name=None, x=1, y=1, z=1, p=0,spam=False, me=True, sp=False,
                 key_send_delay=None):
        super().__init__(node, name)
        self.result = None
        self.answer = None
        self.commitment = None
        self.start_time = 0
        self.end_time = 0
        self.key_send_time = None
        self.answer_arrival_time = None
        self.len = len
        self.x = x
        self.y = y
        self.z = z 
        self.p = p
        self.spam = spam
        self.me = me
        self.sp = sp
        self.wait_time = 0
        self.key_send_delay = key_send_delay

    def set_time(self):
        self.wait_time = (
            propagation_delay_ns(self.len, QUBIT_SIGNAL_SPEED_KM_S)
            - propagation_delay_ns(self.len, CLASSICAL_SIGNAL_SPEED_KM_S)
        )

    def get_elapsed_time(self):
        return self.end_time - self.start_time
    
    def get_ideal_time(self):
        return 2 * propagation_delay_ns(self.len, QUBIT_SIGNAL_SPEED_KM_S)
    
    def apply_sp_error(self, qubit):
        error = BitflipError(p=self.p)
        error.error_operation(qubit=qubit)

    def apply_measurement_error(self, qubit):
        error = BitflipError(p = self.p)
        error.error_operation(qubit=qubit)

    def get_result(self):
        return self.result
    
    def get_answer(self):
        return self.answer

    def get_commitment(self):
        return self.commitment

    def get_round_trip_time(self):
        if self.key_send_time is None or self.answer_arrival_time is None:
            return None
        return self.answer_arrival_time - self.key_send_time
    
    def prepare_epr_pair(self):
        q1 = ns.qubits.create_qubits(1)[0]
        q2 = ns.qubits.create_qubits(1)[0]
        if self.spam is True or self.sp is True:
            self.apply_sp_error(q1)
            self.apply_sp_error(q2)
        ns.qubits.operate(q1, ns.H)
        ns.qubits.operate([q1,q2], ns.CNOT)
        return q1, q2

    def handle_classical_message(self, classical_message, q2):
        if classical_message is None:
            return
        for item in classical_message.items:
            kind, value = parse_protocol_message(item)
            if kind == 'commitment':
                self.commitment = value
                print(f'commitment received at V0 with value {self.commitment}')
                continue

            answer = value
            print(f'answer received at V0 with state {answer} ')
            if self.me is True:
                self.apply_measurement_error(q2)
            if answer is not None and answer != 'Loss':
                if bool_func(self.x, self.y, self.z) == 0:
                    state, prob = ns.qubits.measure(q2)
                    labels_z =  ("|0>", "|1>")
                else:
                    state, prob = ns.qubits.measure(q2, observable=ns.X)
                    labels_z =  ("|+>", "|->")
                self.result = labels_z[state]
            else:
                self.result = None

            self.end_time = ns.sim_time()
            self.answer_arrival_time = ns.sim_time()
            self.answer = answer

    def run(self):
        self.start_time = ns.sim_time()
        port_q = self.node.ports['quantum']
        port_c1 = self.node.ports['v0p']
        q1, q2 = self.prepare_epr_pair()
        port_q.tx_output(q1)
        key_delay = self.key_send_delay
        if key_delay is None:
            key_delay = (
                propagation_delay_ns(self.len, QUBIT_SIGNAL_SPEED_KM_S)
                - propagation_delay_ns(self.len, CLASSICAL_SIGNAL_SPEED_KM_S)
            )
        wait_start = ns.sim_time()
        yield self.await_port_input(port_c1)
        self.handle_classical_message(port_c1.rx_input(), q2)
        remaining_delay = key_delay - (ns.sim_time() - wait_start)
        if remaining_delay > 0:
            yield self.await_timer(duration=remaining_delay)
        self.key_send_time = ns.sim_time()
        port_c1.tx_output(self.x)

        while True:
            yield self.await_port_input(port_c1)
            self.handle_classical_message(port_c1.rx_input(), q2)
#%%
class V1Protocol(NodeProtocol):
    def __init__(self, len, y=1, node=None, name=None, key_send_delay=None):
        super().__init__(node, name)
        self.answer = None
        self.commitment = None
        self.end_time = 0
        self.start_time = 0
        self.key_send_time = None
        self.answer_arrival_time = None
        self.y = y
        self.len = len
        self.key_send_delay = key_send_delay

    def handle_classical_message(self, classical_message):
        if classical_message is None:
            return
        for item in classical_message.items:
            kind, value = parse_protocol_message(item)
            if kind == 'commitment':
                self.commitment = value
                print(f'commitment received at V1 with value {self.commitment}')
                continue
            self.answer = value
            self.end_time = ns.sim_time()
            self.answer_arrival_time = ns.sim_time()
            print(f'answer received at V1 with state {self.answer} ')

    def run(self):
        port_c2 = self.node.ports['v1p']
        key_delay = self.key_send_delay
        if key_delay is None:
            key_delay = (
                propagation_delay_ns(self.len, QUBIT_SIGNAL_SPEED_KM_S)
                - propagation_delay_ns(self.len, CLASSICAL_SIGNAL_SPEED_KM_S)
            )
        wait_start = ns.sim_time()
        yield self.await_port_input(port_c2)
        self.handle_classical_message(port_c2.rx_input())
        remaining_delay = key_delay - (ns.sim_time() - wait_start)
        if remaining_delay > 0:
            yield self.await_timer(duration=remaining_delay)
        self.key_send_time = ns.sim_time()
        port_c2.tx_output(self.y)
        self.start_time = ns.sim_time()
        while True:
            yield self.await_port_input(port_c2)
            self.handle_classical_message(port_c2.rx_input())

    def get_elapsed_time(self):
        return self.end_time - self.start_time
    
    def get_answer(self):
        return self.answer

    def get_commitment(self):
        return self.commitment

    def get_round_trip_time(self):
        if self.key_send_time is None or self.answer_arrival_time is None:
            return None
        return self.answer_arrival_time - self.key_send_time
# %%
class V2Protocol(NodeProtocol):
    def __init__(self, len, z=1, node=None, name=None, key_send_delay=None):
        super().__init__(node, name)
        self.answer = None
        self.commitment = None
        self.end_time = 0
        self.start_time = 0
        self.key_send_time = None
        self.answer_arrival_time = None
        self.z = z
        self.len = len
        self.key_send_delay = key_send_delay

    def handle_classical_message(self, classical_message):
        if classical_message is None:
            return
        for item in classical_message.items:
            kind, value = parse_protocol_message(item)
            if kind == 'commitment':
                self.commitment = value
                print(f'commitment received at V2 with value {self.commitment}')
                continue
            self.answer = value
            self.end_time = ns.sim_time()
            self.answer_arrival_time = ns.sim_time()
            print(f'answer received at V2 with state {self.answer} ')

    def run(self):
        port_c3 = self.node.ports['v2p']
        key_delay = self.key_send_delay
        if key_delay is None:
            key_delay = (
                propagation_delay_ns(self.len, QUBIT_SIGNAL_SPEED_KM_S)
                - propagation_delay_ns(self.len, CLASSICAL_SIGNAL_SPEED_KM_S)
            )
        wait_start = ns.sim_time()
        yield self.await_port_input(port_c3)
        self.handle_classical_message(port_c3.rx_input())
        remaining_delay = key_delay - (ns.sim_time() - wait_start)
        if remaining_delay > 0:
            yield self.await_timer(duration=remaining_delay)
        self.key_send_time = ns.sim_time()
        port_c3.tx_output(self.z)
        self.start_time = ns.sim_time()
        while True:
            yield self.await_port_input(port_c3)
            self.handle_classical_message(port_c3.rx_input())

    def get_elapsed_time(self):
        return self.end_time - self.start_time
    
    def get_answer(self):
        return self.answer

    def get_commitment(self):
        return self.commitment

    def get_round_trip_time(self):
        if self.key_send_time is None or self.answer_arrival_time is None:
            return None
        return self.answer_arrival_time - self.key_send_time
