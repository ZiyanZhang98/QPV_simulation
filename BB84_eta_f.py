#%%
from netsquid.protocols import NodeProtocol
from netsquid.components import QuantumChannel, ClassicalChannel
from netsquid.nodes import Node, DirectConnection, Connection
import netsquid as ns
from netsquid.qubits import qubitapi as qapi
import random
import numpy as np
# %%
correct_counter = 0

class V0Protocol(NodeProtocol):
    def __init__(self, node=None, name=None):
        super().__init__(node, name)
        # self.basis = basis

    def run(self):
        print(f"start v0 at t={ns.sim_time()}")
        port_q = self.node.ports['quantum']
        port_c = self.node.ports['classical']
        q1 = ns.qubits.create_qubits(1)[0]
        q2 = ns.qubits.create_qubits(1)[0]
        ns.qubits.operate(q1, ns.H)
        ns.qubits.operate([q1,q2], ns.CNOT)
        port_q.tx_output(q1)
        # port_c.tx_output(self.basis)
        while True:
            yield self.await_port_input(port_c)
            answer = port_c.rx_input().items[0]
            state, prob = ns.qubits.measure(q2)
            labels_z =  ("|0>", "|1>")
            print(f"{ns.sim_time()}: V0's particle {self.node.name} measured "
                  f"{labels_z[state]} with probability {prob:.2f}")
            if answer == state:
                global correct_counter
                correct_counter = correct_counter + 1
            elif answer == 'Loss':
                print('Loss')
            else:
                print('Wrong')

class PProtocol(NodeProtocol):
    def __init__(self, distance, node=None, name=None):
        super().__init__(node, name)
        self.loss_rate = 1 - 10 ** (-0.2*distance/10)

    def run(self):
        port_q = self.node.ports['quantum']
        port_c = self.node.ports['classical']
        while True:
            yield self.await_port_input(port_q)
            qubit = port_q.rx_input().items[0]
            p = np.random.choice([0,1], p=[self.loss_rate, 1-self.loss_rate])
            if p == 1:
                state, prob = ns.qubits.measure(qubit)
                labels_z =  ("|0>", "|1>")
                print(f"{ns.sim_time()}: p0's particle measured "
                  f"{labels_z[state]} with probability {prob:.2f}")
            else:
                state = 'Loss'
                print(f'{ns.sim_time()}: photon loss with loss rate: {self.loss_rate:.2f}')
            port_c.tx_output(state)

#%% Run the simulation
round = int(input('Round: '))
distance = np.arange(1, 50)
p_err = []
for d in distance:
    for i in range(round):
        ns.sim_reset()
        node_v0 = Node('v0', port_names = ['quantum', 'classical'])
        node_p = Node('p', port_names=['quantum', 'classical'])
        connection =  DirectConnection('classical',
                                    ClassicalChannel('p2v', delay=21),
                                    ClassicalChannel('v2p', delay=21))

        q_connection = Connection("QuantumConnection")
        q_channel = QuantumChannel("Channel_A2B", delay=30)
        q_connection.add_subcomponent(q_channel,
                                    forward_input=[("A", "send")],
                                    forward_output=[("B", "recv")])
        
        node_v0.ports['classical'].connect(connection.ports['A'])
        node_p.ports['classical'].connect(connection.ports['B'])
        node_v0.ports['quantum'].connect(q_connection.ports['A'])
        node_p.ports['quantum'].connect(q_connection.ports['B'])
        v0_protocol = V0Protocol(node_v0)
        p_protocol = PProtocol(distance=d, node=node_p)
        v0_protocol.start()
        p_protocol.start()
        stats = ns.sim_run(91)
    p_err.append((round-correct_counter)/round)
    correct_counter = 0
# %% Output images
import matplotlib.pyplot as plt
plt.figure(dpi=400)
plt.plot(distance, p_err)
# %%
