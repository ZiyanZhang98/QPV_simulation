#%%
import netsquid as ns
import numpy as np
from netsquid.protocols import NodeProtocol
from netsquid.nodes import Node
import matplotlib.pyplot as plt
from component import QuantumConnection, ClassicalConnection
from bool_function import bool_func
from verifier import V0Protocol, V1Protocol
# %%
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

            is_q = expr.first_term.first_term.value
            is_basis = (expr.second_term.first_term.value,expr.second_term.second_term.value)
            print(is_q, is_basis)

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
#%% Run the simulation
def main(round, distance, x, y):
    fibre_distance = np.arange(1, distance)
    p_err = []
    time = []
    for d in fibre_distance:
        correct_counter = 0
        for i in range(round):
            ns.sim_reset()
            # Init three nodes
            node_v0 = Node('v0', port_names = ['quantum', 'v0p', 'v0v1'])
            node_p = Node('p', port_names=['quantum', 'pv0', 'pv1'])
            node_v1 = Node('v1', port_names=['v1p', 'v1v0'])
            # Classical channel with fibre delay = distance /3e5, connection between V0 and P
            c_connection1 = ClassicalConnection(length=d, name='p0v1', direction='Bi')
            node_v0.ports['v0p'].connect(c_connection1.ports['A'])
            node_p.ports['pv0'].connect(c_connection1.ports['B'])
            # Classical connection between P and V1
            c_connection2 = ClassicalConnection(length=d, name='v1p', direction='Bi')
            node_v1.ports['v1p'].connect(c_connection2.ports['A'])
            node_p.ports['pv1'].connect(c_connection2.ports['B'])
            # Classical connection between V0 and V1
            c_connection3 = ClassicalConnection(length=d, name='v0v1', direction='Bi')
            node_v0.ports['v0v1'].connect(c_connection3.ports['A'])
            node_v1.ports['v1v0'].connect(c_connection3.ports['B'])
            # Quantum connection between V0 and P, with delay = d/2e5, and attenuation
            q_connection = QuantumConnection(name="Channel_A2B", length=d, direction='A2B')
            node_v0.ports['quantum'].connect(q_connection.ports['A'])
            node_p.ports['quantum'].connect(q_connection.ports['B'])

            v0_protocol = V0Protocol(node=node_v0, x=x, y=y)
            p_protocol = PProtocol(node=node_p)
            v1_protocol = V1Protocol(node=node_v1, y=y)
            # Start protocol
            v0_protocol.start()
            v1_protocol.start()
            p_protocol.start()
            stats = ns.sim_run()
            # Check results
            a = v0_protocol.get_answer()
            b = v1_protocol.get_answer()
            t_a = v0_protocol.get_elapsed_time()
            t_b = v1_protocol.get_elapsed_time()
            m = v0_protocol.get_result()
            
            if a == 'Loss' or b == 'Loss' or a is None or b is None:
                pass
            else:
                if a == b and a == m and t_a == t_b:
                    print('Time and answer matches, correct!')
                    correct_counter = correct_counter + 1
                elif a != b or t_a != t_b or a != m:
                    print('Wrong')
                else:
                    print('Abort')
            # Reset the timer
            ns.sim_reset()

        time.append(v0_protocol.get_elapsed_time())
        p_err.append((round-correct_counter)/round)
    return p_err, fibre_distance, time
# %% Output images
p_err, distance, time = main(round=10, distance=200, x=1, y=0)
plt.figure(dpi=400)
plt.plot(distance, p_err)
plt.xlabel('Distance (km)')
plt.ylabel('Error rate')
# %%
# %%
