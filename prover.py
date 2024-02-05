import netsquid as ns
from netsquid.protocols import NodeProtocol
from bool_function import bool_func

class PProtocol(NodeProtocol):
    def __init__(self, node=None, name=None):
        super().__init__(node, name)
        self.x = None
        self.y = None
        self.port_q = self.node.ports['quantum']
        self.port_c = self.node.ports['pv0']
        self.port_c2 = self.node.ports['pv1']
    
    def run(self):
        while True:
            expr = yield (self.await_port_input(self.port_q)) or (yield (self.await_port_input(self.port_c) or self.await_port_input(self.port_c2)))

            print(expr.first_term.first_term.value, expr.second_term.first_term.value, expr.second_term.second_term.value)

            qubit = self.port_q.rx_input().items[0]
            self.x = self.port_c.rx_input().items[0]
            self.y = self.port_c2.rx_input().items[0]

            if bool_func(self.x, self.y) == 0:
                state, prob = ns.qubits.measure(qubit)
                labels_z =  ("|0>", "|1>")
                print(f"{ns.sim_time()}: Particle p received and measured "f"{labels_z[state]} with probability {prob:.2f}")
            else:
                state, prob = ns.qubits.measure(qubit, observable=ns.X)
                labels_z =  ("|+>", "|->")
                print(f"{ns.sim_time()}: Particle p received and measured "
                    f"{labels_z[state]} with probability {prob:.2f}")
            
            self.port_c.tx_output(labels_z[state])
            self.port_c2.tx_output(labels_z[state])