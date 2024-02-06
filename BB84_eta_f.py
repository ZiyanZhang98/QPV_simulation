#%%
import netsquid as ns
import numpy as np
from netsquid.protocols import NodeProtocol
from netsquid.nodes import Node, Network
import matplotlib.pyplot as plt
from component import QuantumConnection, ClassicalConnection
from bool_function import bool_func
from verifier import V0Protocol, V1Protocol
from prover import PProtocol
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

            v0_protocol = V0Protocol(node=node_v0, x=x, y=y, len=d)
            p_protocol = PProtocol(node=node_p)
            v1_protocol = V1Protocol(node=node_v1, y=y, len=d)
            # Start protocol
            p_protocol.start()
            v0_protocol.start()
            v1_protocol.start()

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
                if a == b and a == m:
                    print('Time and answer matches, correct!')
                    correct_counter = correct_counter + 1
                elif a != b or a != m:
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
node_v0 = Node('v0', port_names = ['quantum', 'v0p', 'v0v1'])
node_p = Node('p', port_names=['quantum', 'pv0', 'pv1'])
node_v1 = Node('v1', port_names=['v1p', 'v1v0'])
network = Network('QPV_BB84')
network.add_nodes([node_p, node_v0, node_v1])
network.add_connection(node_v1, node_v0, connection=ClassicalConnection(length=3, name='v0v1', direction='Bi'), port_name_node1='v1v0', port_name_node2='v0v1')
network.add_connection(node_v1, node_p, connection=ClassicalConnection(length=3, name='v1p', direction='Bi'), port_name_node1='v1p', port_name_node2='pv1')
network.add_connection(node_v0, node_p, connection=ClassicalConnection(length=3, name='v0p', direction='Bi'), port_name_node1='v0p', port_name_node2='pv0')
network.add_connection(node_v0, node_p, connection=QuantumConnection(name="Channel_A2B", length=3, direction='A2B'), port_name_node1='quantum', port_name_node2='quantum')
#%%
handler_v0 = lambda m: print(f"V0 received {m} at {ns.sim_time()}!")
handler_v1 = lambda m: print(f"V1 received {m} at {ns.sim_time()}!")
handler_vp = lambda m: print(f'p received {m} at {ns.sim_time()}!')
node_v0.ports['v0v1'].bind_input_handler(handler_v0)
node_v1.ports['v1v0'].bind_input_handler(handler_v1)
node_p.ports['quantum'].bind_input_handler(handler_vp)
q1 = ns.qubits.create_qubits(1)[0]
q2 = ns.qubits.create_qubits(1)[0]
ns.qubits.operate(q1, ns.H)
ns.qubits.operate([q1,q2], ns.CNOT)
node_v0.ports['quantum'].tx_output(q1)

node_v0.ports['v0v1'].tx_output("Hi v1!")
node_v1.ports['v1v0'].tx_output("Hi v0!")

x = ns.sim_run()
ns.sim_reset()
# %%
