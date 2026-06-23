import netsquid as ns
from netsquid.protocols import NodeProtocol
from bool_function import bool_func
from component import BitflipError, QUBIT_SIGNAL_SPEED_KM_S, propagation_delay_ns

class PProtocol(NodeProtocol):
    def __init__(self, node=None, name=None, p=0, me=True, len=None):
        super().__init__(node, name)
        self.x = None
        self.y = None
        self.z = None
        self.p = p
        self.me = me
        self.len = len
        self.key_arrival_times = {}
        self.port_q = self.node.ports['quantum']
        self.port_c = self.node.ports['pv0']
        self.port_c2 = self.node.ports['pv1']
        self.port_c3 = self.node.ports['pv2']
    
    def apply_measurement_error(self, qubit):
        error = BitflipError(p = self.p)
        error.error_operation(qubit=qubit)

    def broadcast(self, kind, value):
        message = {'kind': kind, 'value': value}
        self.port_c.tx_output(message)
        self.port_c2.tx_output(message)
        self.port_c3.tx_output(message)

    def get_key_arrival_times(self):
        return dict(self.key_arrival_times)

    def get_key_arrival_spread(self):
        if len(self.key_arrival_times) != 3:
            return None
        times = list(self.key_arrival_times.values())
        return max(times) - min(times)

    def receive_available_keys(self):
        for name, port in (('x', self.port_c), ('y', self.port_c2), ('z', self.port_c3)):
            message = port.rx_input()
            if message is None or not message.items:
                continue
            setattr(self, name, message.items[0])
            self.key_arrival_times[name] = ns.sim_time()

    def run(self):
        while True:
            if self.len is None:
                yield self.await_port_input(self.port_q)
            else:
                quantum_timeout = propagation_delay_ns(self.len, QUBIT_SIGNAL_SPEED_KM_S) + 1
                yield (self.await_port_input(self.port_q) | self.await_timer(duration=quantum_timeout))
            q_message = self.port_q.rx_input()
            qubit = q_message.items[0] if q_message is not None and q_message.items else None
            commitment = 1 if qubit is not None else 0
            self.broadcast('commitment', commitment)

            while self.x is None or self.y is None or self.z is None:
                yield (self.await_port_input(self.port_c) | self.await_port_input(self.port_c2) | self.await_port_input(self.port_c3))
                self.receive_available_keys()

            if qubit is None:
                self.broadcast('answer', 'Loss')
                return
            
            if self.me is True:
                self.apply_measurement_error(qubit=qubit)

            if bool_func(self.x, self.y, self.z) == 0:
                state, prob = ns.qubits.measure(qubit)
                labels_z =  ("|0>", "|1>")
                print(f"{ns.sim_time()}: Particle p received and measured "f"{labels_z[state]} with probability {prob:.2f}")
            else:
                state, prob = ns.qubits.measure(qubit, observable=ns.X)
                labels_z =  ("|+>", "|->")
                print(f"{ns.sim_time()}: Particle p received and measured "
                    f"{labels_z[state]} with probability {prob:.2f}")

            self.broadcast('answer', labels_z[state])
            return
