#%%
import netsquid as ns
import numpy as np
import random
import matplotlib.pyplot as plt
import pydynaa
from netsquid.components import Channel, QuantumChannel
from netsquid.components import QuantumMemory
from netsquid.nodes.connections import Connection
from netsquid.nodes import Node
from netsquid.components.component import Port
# %%
# Random basis and encoded qubit
x = random.randint(0, 1)
y = random.randint(0, 1)
eta = 0.1
# %% Prepare EPR pairs
q1 = ns.qubits.create_qubits(1)[0]
q2 = ns.qubits.create_qubits(1)[0]
ns.qubits.operate(q1, ns.H)
ns.qubits.operate([q1,q2], ns.CNOT)
#%% Create channels
c10 = Channel('c10')

cp0 = Channel('cp0')
c1p = Channel('c1p')
cp1 = Channel('cp1')
q0p = QuantumChannel('q0p')
# %%
# %%
class V0(pydynaa.Entity):
    length = 2e-3
    def __init__(self, x):
        self.x = x
        self.c01 = Channel('c01', length=self.length)
        self.c0p = Channel('c0p', length=self.length)
        self.q0p = QuantumChannel('q0p', length=self.length)
        self.q1 = ns.qubits.create_qubits(1)[0]
        self.q2 = ns.qubits.create_qubits(1)[0]
        self._wait(pydynaa.EventHandler(self._handle_input_p0), event_type=Port.evtype_input)

    def prepare_epr_pair(self):
        ns.qubits.operate(self.q1, ns.H)
        ns.qubits.operate([self.q1,self.q2], ns.CNOT)
        return self.q1, self.q2
    
    def start(self):
        self.prepare_epr_pair()
        self.q0p.send(self.q1)
        self.c0p.send(self.x)

     
# %%
from netsquid.protocols import NodeProtocol
from netsquid.components import QuantumChannel, ClassicalChannel
from netsquid.nodes import Node, DirectConnection
import netsquid as ns

class V0Protocol(NodeProtocol):
    def run(self):
        print(f"start v0 at t={ns.sim_time()}")
        port = self.node.ports['port_to_channel']
        q1 = ns.qubits.create_qubits(1)[0]
        q2 = ns.qubits.create_qubits(1)[0]
        ns.qubits.operate(q1, ns.H)
        ns.qubits.operate([q1,q2], ns.CNOT)
        port.tx_output(q1)
        while True:
            yield self.await_port_input(port)
            answer = port.rx_input().items[0]
            state, prob = ns.qubits.measure(q2)
            labels_z =  ("|0>", "|1>")
            print(f"{ns.sim_time()}: V0's partical {self.node.name} measured "
                  f"{labels_z[state]} with probability {prob:.2f}")
            if answer == state:
                print('Correct')
            elif answer == 'Loss':
                print('Loss')
            else:
                print('Wrong')

class PProtocol(NodeProtocol):
    def run(self):
        print(f"qubit received at t={ns.sim_time()}")
        port = self.node.ports['port_to_channel']
        while True:
            yield self.await_port_input(port)
            qubit = port.rx_input().item[0]
            state, prob = ns.qubits.measure(qubit)
            labels_z =  ("|0>", "|1>")
            print(f"{ns.sim_time()}: p0's partical {self.node.name} measured "
                  f"{labels_z[state]} with probability {prob:.2f}")
            port.tx_output(state)


ns.sim_reset()
node_v0 = Node('v0', port_names = ['port_to_channel'])
node_p = Node('p', port_names=['port_to_channel'])
connection =  DirectConnection('Connection',
                               QuantumChannel('v2p', delay=10),
                               ClassicalChannel('p2v'))
node_v0.ports['port_to_channel'].connect(connection.ports['A'])
node_p.ports['port_to_channel'].connect(connection.port['B'])
v0_protocol = V0Protocol(node_v0)
p_protocol = PProtocol(node_p)
# %%
