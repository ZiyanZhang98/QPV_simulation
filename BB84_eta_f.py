#%%
import netsquid as ns
import numpy as np
from netsquid.protocols import NodeProtocol
from netsquid.components import QuantumChannel, ClassicalChannel
from netsquid.nodes import Node, DirectConnection, Connection
from netsquid.components.models.qerrormodels import FibreLossModel as qfm
from netsquid.components.models.delaymodels import FibreDelayModel as cfm
# %%
class V0Protocol(NodeProtocol):
    def __init__(self, node=None, name=None):
        super().__init__(node, name)
        self.result = None

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
                self.result = 'correct'
            elif answer == None:
                self.result = None
            else:
                self.result = 'wrong'
    
    def get_result(self):
        return self.result

class PProtocol(NodeProtocol):
    def __init__(self, node=None, name=None):
        super().__init__(node, name)
        # self.loss_rate = 1 - 10 ** (-0.2*distance/10)
    
    # def get_loss(self):
    #     return self.loss_rate

    def run(self):
        port_q = self.node.ports['quantum']
        port_c = self.node.ports['classical']
        while True:
            yield self.await_port_input(port_q)
            qubit = port_q.rx_input().items[0]
            state, prob = ns.qubits.measure(qubit)
            labels_z =  ("|0>", "|1>")
            print(f"{ns.sim_time()}: p's particle received and measured "f"{labels_z[state]} with probability {prob:.2f}")
            port_c.tx_output(state)

#%% Run the simulation
round = int(input('Round: '))
distance = np.arange(1, 10)
p_err = []
for d in distance:
    correct_counter = 0
    for i in range(round):
        ns.sim_reset()
        node_v0 = Node('v0', port_names = ['quantum', 'classical'])
        node_p = Node('p', port_names=['quantum', 'classical'])

        c_delay_model = cfm()
        q_delay_model = qfm(p_loss_init=0, p_loss_length=0)

        connection =  DirectConnection('classical',
                                    ClassicalChannel('p2v', length=d, models={'delay_model':c_delay_model}),
                                    ClassicalChannel('v2p', length=d, models={'delay_model':c_delay_model}))

        q_connection = Connection("QuantumConnection")
        q_channel = QuantumChannel("Channel_A2B", length=d, models={'quantum_loss_model':q_delay_model})
        q_connection.add_subcomponent(q_channel,
                                    forward_input=[("A", "send")],
                                    forward_output=[("B", "recv")])
        
        node_v0.ports['classical'].connect(connection.ports['A'])
        node_p.ports['classical'].connect(connection.ports['B'])
        node_v0.ports['quantum'].connect(q_connection.ports['A'])
        node_p.ports['quantum'].connect(q_connection.ports['B'])
        v0_protocol = V0Protocol(node_v0)
        p_protocol = PProtocol(node=node_p)
        v0_protocol.start()
        p_protocol.start()
        stats = ns.sim_run(91)
        if v0_protocol.get_result() == 'correct':
            correct_counter = correct_counter + 1
    #p_err.append((round-correct_counter)/round)
    p_err.append(correct_counter)
# %% Output images
import matplotlib.pyplot as plt
plt.figure(dpi=400)
plt.plot(distance, p_err)
# %%
p_err
# %%
