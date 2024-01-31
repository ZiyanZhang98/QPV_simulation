#%%
import netsquid as ns
import numpy as np
from netsquid.protocols import NodeProtocol
from netsquid.nodes import Node
import matplotlib.pyplot as plt
from component import QuantumConnection, ClassicalConnection 
# %%
def bool_func(x, y):
    '''
    Pre-shared boolean function to determine measurement basis. 
    '''
    return (x + y) % 2

#%%
class V0Protocol(NodeProtocol):
    def __init__(self, node=None, name=None, x=1, y=1):
        super().__init__(node, name)
        self.result = None
        self.answer = None
        self.end_time = 0
        self.x = x
        self.y = y

    def run(self):
        print(f"start v0 at t={ns.sim_time()}")
        port_q = self.node.ports['quantum']
        port_c1 = self.node.ports['v0p']
        q1 = ns.qubits.create_qubits(1)[0]
        q2 = ns.qubits.create_qubits(1)[0]
        ns.qubits.operate(q1, ns.H)
        ns.qubits.operate([q1,q2], ns.CNOT)
        port_q.tx_output(q1)
        port_c1.tx_output(self.x)
        while True:
            yield self.await_port_input(port_c1)
            answer = port_c1.rx_input().items[0]
            if bool_func(self.x, self.y) == 0:
                state, prob = ns.qubits.measure(q2)
                labels_z =  ("|0>", "|1>")
                print(f"{ns.sim_time()}: V0's particle {self.node.name} measured "
                    f"{labels_z[state]} with probability {prob:.2f}")
            else:
                state, prob = ns.qubits.measure(q2, observable=ns.X)
                labels_z =  ("|+>", "|->")
                print(f"{ns.sim_time()}: V0's particle {self.node.name} measured "
                    f"{labels_z[state]} with probability {prob:.2f}")
                
            self.end_time = ns.sim_time()
            self.result = labels_z[state]
            self.answer = answer

    def get_time(self):
        return self.end_time
    
    def get_result(self):
        return self.result
    
    def get_answer(self):
        return self.answer

class V1Protocol(NodeProtocol):
    def __init__(self, y=1, node=None, name=None):
        super().__init__(node, name)
        self.answer = None
        self.end_time = 0
        self.y = y

    def run(self):
        port_c = self.node.ports['v1p']
        port_c.tx_output(self.y)
        while True:
            yield self.await_port_input(port_c)
            self.answer = port_c.rx_input().items[0]
            self.end_time = ns.sim_time()
            print(f'{self.end_time} answer received at V1 with state {self.answer} ')

    def get_time(self):
        return self.end_time
    
    def get_result(self):
        return self.answer

class PProtocol(NodeProtocol):
    def __init__(self, node=None, name=None):
        super().__init__(node, name)
        self.x = None
        self.y = None
    
    def run(self):
        port_q = self.node.ports['quantum']
        port_c = self.node.ports['pv0']
        port_c2 = self.node.ports['pv1']
        while True:
            expr = yield (self.await_port_input(port_q) or self.await_port_input(port_c) or self.await_port_input(port_c2))

            if expr.first_term.first_term.value is not True:
                port_c.tx_output('Loss')
                port_c2.tx_output('Loss')
                return 0
            
            qubit = port_q.rx_input().items[0]
            self.x = port_c.rx_input().items[0]
            self.y = port_c2.rx_input().items[0]

            if bool_func(self.x, self.y) == 0:
                state, prob = ns.qubits.measure(qubit)
                labels_z =  ("|0>", "|1>")
                print(f"{ns.sim_time()}: Particle p received and measured "f"{labels_z[state]} with probability {prob:.2f}")
            else:
                state, prob = ns.qubits.measure(qubit, observable=ns.X)
                labels_z =  ("|+>", "|->")
                print(f"{ns.sim_time()}: Particle p received and measured "
                    f"{labels_z[state]} with probability {prob:.2f}")
            
            port_c.tx_output(labels_z[state])
            port_c2.tx_output(labels_z[state])

#%% Run the simulation
def main(round, distance, x, y):
    fibre_distance = np.arange(1, distance)
    p_err = []
    time = []
    for d in fibre_distance:
        correct_counter = 0
        for i in range(round):
            ns.sim_reset()
            node_v0 = Node('v0', port_names = ['quantum', 'v0p', 'v0v1'])
            node_p = Node('p', port_names=['quantum', 'pv0', 'pv1'])
            node_v1 = Node('v1', port_names=['v1p', 'v1v0'])

            # Classical channel with fibre delay = distance / speed in fibre
            c_connection1 = ClassicalConnection(length=d, name='p0v1', direction='Bi')

            c_connection2 = ClassicalConnection(length=d, name='v1p', direction='Bi')

            c_connection3 = ClassicalConnection(length=d, name='v0v1', direction='Bi')

            # Quantum connection between V0 and P

            q_connection = QuantumConnection(name="Channel_A2B", length=d, direction='A2B')

            node_v0.ports['quantum'].connect(q_connection.ports['A'])
            node_p.ports['quantum'].connect(q_connection.ports['B'])
            # Classical connection between V0 and P
            node_v0.ports['v0p'].connect(c_connection1.ports['A'])
            node_p.ports['pv0'].connect(c_connection1.ports['B'])
            # Classical connection between V0 and V1
            node_v0.ports['v0v1'].connect(c_connection3.ports['A'])
            node_v1.ports['v1v0'].connect(c_connection3.ports['B'])
            # Classical connection between V1 and P
            node_v1.ports['v1p'].connect(c_connection2.ports['A'])
            node_p.ports['pv1'].connect(c_connection2.ports['B'])

            v0_protocol = V0Protocol(node=node_v0, x=x, y=y)
            p_protocol = PProtocol(node=node_p)
            v1_protocol = V1Protocol(node=node_v1, y=y)

            v0_protocol.start()
            v1_protocol.start()
            p_protocol.start()

            stats = ns.sim_run()

            # Check results
            a = v0_protocol.get_answer()
            b = v1_protocol.get_result()
            t_a = v0_protocol.get_time()
            t_b = v1_protocol.get_time()
            m = v0_protocol.get_result()
            
            if a is None or b is None:
                print('Loss')
            else:
                if a == b and a == m:
                    print('Time and answer matches, correct!')
                    correct_counter = correct_counter + 1
                elif a != b and t_a != t_b and a != m:
                    print('Wrong')
                else:
                    print('Abort')
            # Reset the timer
            ns.sim_reset()

        time.append(v0_protocol.get_time())
        p_err.append((round-correct_counter)/round)
    return p_err, fibre_distance, time
# %% Output images
p_err, distance, time = main(round=10, distance=200, x=1, y=0)
plt.figure(dpi=400)
plt.plot(distance, p_err)
plt.xlabel('Distance (km)')
plt.ylabel('Error rate')
# %%
