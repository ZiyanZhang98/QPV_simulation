#%%
import netsquid as ns
from netsquid.protocols import NodeProtocol
from bool_function import bool_func
#%%
class V0Protocol(NodeProtocol):
    def __init__(self, len, node=None, name=None, x=1, y=1):
        super().__init__(node, name)
        self.result = None
        self.answer = None
        self.start_time = 0
        self.end_time = 0
        self.len = len
        self.x = x
        self.y = y

    def get_elapsed_time(self):
        return self.end_time - self.start_time
    
    def get_result(self):
        return self.result
    
    def get_answer(self):
        return self.answer
    
    def prepare_epr_pair(self):
        q1 = ns.qubits.create_qubits(1)[0]
        q2 = ns.qubits.create_qubits(1)[0]
        ns.qubits.operate(q1, ns.H)
        ns.qubits.operate([q1,q2], ns.CNOT)
        return q1, q2
    
    def run(self):
        self.start_time = ns.sim_time()
        port_q = self.node.ports['quantum']
        port_c1 = self.node.ports['v0p']
        q1, q2 = self.prepare_epr_pair()
        port_q.tx_output(q1)
        yield self.await_timer(duration = (self.len/2e5-self.len/3e5)*1e9)
        port_c1.tx_output(self.x)

        while True:
            yield self.await_port_input(port_c1)
            answer = port_c1.rx_input().items[0]
            if answer != 'Loss':
                if bool_func(self.x, self.y) == 0:
                    state, prob = ns.qubits.measure(q2)
                    labels_z =  ("|0>", "|1>")
                    print(f"V0's particle {self.node.name} measured "
                          f"{labels_z[state]} with probability {prob:.2f}")
                else:
                    state, prob = ns.qubits.measure(q2, observable=ns.X)
                    labels_z =  ("|+>", "|->")
                    print(f"V0's particle {self.node.name} measured "
                        f"{labels_z[state]} with probability {prob:.2f}")
                self.result = labels_z[state]
            else:
                self.result = "Loss"

            self.end_time = ns.sim_time()
            self.answer = answer
#%%
class V1Protocol(NodeProtocol):
    def __init__(self, len, y=1, node=None, name=None):
        super().__init__(node, name)
        self.answer = None
        self.end_time = 0
        self.start_time = 0
        self.y = y
        self.len = len

    def run(self):
        port_c = self.node.ports['v1p']
        yield self.await_timer(duration = (self.len/2e5-self.len/3e5)*1e9)
        port_c.tx_output(self.y)
        self.start_time = ns.sim_time()
        while True:
            yield self.await_port_input(port_c)
            self.answer = port_c.rx_input().items[0]
            self.end_time = ns.sim_time()
            print(f'answer received at V1 with state {self.answer} ')

    def get_elapsed_time(self):
        return self.end_time - self.start_time
    
    def get_answer(self):
        return self.answer
# %%
