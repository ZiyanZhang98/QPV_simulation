#%%
import netsquid as ns
import numpy as np
from netsquid.nodes import Node
import matplotlib.pyplot as plt
from component import QuantumConnection, ClassicalConnection
from verifier import V0Protocol, V1Protocol, V2Protocol
from prover import PProtocol
from bool_function import bool_func
#%% Run the simulation
def honest_distance_error(round, distance, x, y, z):
    fibre_distance = np.arange(1, distance)
    p_err = []
    time = []
    for d in fibre_distance:
        correct_counter = 0
        for i in range(round):
            ns.sim_reset()
            # Init three nodes
            node_v0 = Node('v0', port_names = ['quantum', 'v0p'])
            node_p = Node('p', port_names=['quantum', 'pv0', 'pv1', 'pv2'])
            node_v1 = Node('v1', port_names=['v1p'])
            node_v2 = Node('v2', port_names=['v2p'])
            # Classical channel with fibre delay = distance /3e5, connection between V0 and P
            c_connection1 = ClassicalConnection(length=d, name='p0v1', direction='Bi')
            node_v0.ports['v0p'].connect(c_connection1.ports['A'])
            node_p.ports['pv0'].connect(c_connection1.ports['B'])
            # Classical connection between P and V1
            c_connection2 = ClassicalConnection(length=d, name='v1p', direction='Bi')
            node_v1.ports['v1p'].connect(c_connection2.ports['A'])
            node_p.ports['pv1'].connect(c_connection2.ports['B'])
            # Classical connection between P and V2
            c_connection3 = ClassicalConnection(length=d, name='v2p', direction='Bi')
            node_v2.ports['v2p'].connect(c_connection3.ports['A'])
            node_p.ports['pv2'].connect(c_connection3.ports['B'])

            # Classical connection between V0 and V1
            # c_connection3 = ClassicalConnection(length=d, name='v0v1', direction='Bi')
            # node_v0.ports['v0v1'].connect(c_connection3.ports['A'])
            # node_v1.ports['v1v0'].connect(c_connection3.ports['B'])

            # Quantum connection between V0 and P, with delay = d/2e5, and attenuation
            q_connection = QuantumConnection(name="Channel_A2B", length=d, direction='A2B',  p_loss_length=0)
            node_v0.ports['quantum'].connect(q_connection.ports['A'])
            node_p.ports['quantum'].connect(q_connection.ports['B'])

            v0_protocol = V0Protocol(node=node_v0, x=x, y=y, z=z, len=d)
            p_protocol = PProtocol(node=node_p)
            v1_protocol = V1Protocol(node=node_v1, y=y, len=d)
            v2_protocol = V2Protocol(node=node_v2, z=z, len=d)
            # Start protocol
            p_protocol.start()
            v0_protocol.start()
            v1_protocol.start()
            v2_protocol.start()
            
            stats = ns.sim_run()
            # Check results
            a = v0_protocol.get_answer()
            b = v1_protocol.get_answer()
            c = v2_protocol.get_answer()
            # t_a = v0_protocol.get_elapsed_time()
            # t_b = v1_protocol.get_elapsed_time()
            m = v0_protocol.get_result()
            
            if a == 'Loss' or b == 'Loss' or c == 'Loss' or a is None or b is None or c is None:
                pass
            else:
                if a == b == m == c: 
                    print('Time and answer matches, correct!')
                    correct_counter = correct_counter + 1
                elif a != b or a != m or c != m or a != c:
                    print('Wrong')
                else:
                    print('Abort')
            # Reset the timer
            ns.sim_reset()

        time.append(v0_protocol.get_elapsed_time())
        p_err.append((round-correct_counter)/round)
    return p_err, fibre_distance, time
# %% Output images
# p_without_quantum = [0.06,0.13,0.13,0.18,0.17,0.19,0.29,0.23,0.33,0.35,0.43,0.44,0.5, 0.57,0.5,0.47,0.58,0.47,0.68,0.69,0.62,0.65,0.63,0.63, 0.76,0.73,0.63,0.75,0.67,0.73, 0.75,0.77,0.77,0.8, 0.78, 0.75,0.78,0.85,0.85,0.82,0.87,0.84,0.9,0.85,0.88,0.88,0.89,0.88, 0.9]
# p_with_me = [0.5,0.56,0.66,0.61,0.7,0.61,0.53,0.73,0.7,0.72,0.76,0.67,0.75,0.69,0.73,0.7,0.8,0.81,0.71,0.8,0.83,0.77,0.85,0.87,0.87,0.86,0.88,0.85,0.89,0.88,0.91,0.87,0.88,0.87, 0.84, 0.94, 0.9, 0.88, 0.94,0.92, 0.92, 0.94, 0.95, 0.96, 0.94, 0.94, 0.97, 0.96, 0.92]
# # %%
# p_err, distance, time = honest_distance_error(round=100, distance=50, x=1, y=0, z=3)
# plt.figure(dpi=400)
# plt.plot(distance, p_err, label='Honest prover')
# # plt.plot(distance, p_with_me, label='With measurement error')
# # plt.plot(distance, p_without_quantum, label='Without quantum error')
# plt.legend()
# plt.ylim(0, 1)
# plt.xlabel('Distance (km)')
# plt.ylabel('Error rate')
# # %%
# def main(round, distance, x, y, z):
#     d = distance
#     loss_rate = np.arange(0, 1.05, step=0.05)
#     p_err = []
#     time = []

#     for p in loss_rate:
#         correct_counter = 0
#         for i in range(round):
#             ns.sim_reset()
#             # Init three nodes
#             node_v0 = Node('v0', port_names = ['quantum', 'v0p'])
#             node_p = Node('p', port_names=['quantum', 'pv0', 'pv1', 'pv2'])
#             node_v1 = Node('v1', port_names=['v1p'])
#             node_v2 = Node('v2', port_names=['v2p'])
#             # Classical channel with fibre delay = distance /3e5, connection between V0 and P
#             c_connection1 = ClassicalConnection(length=d, name='p0v1', direction='Bi')
#             node_v0.ports['v0p'].connect(c_connection1.ports['A'])
#             node_p.ports['pv0'].connect(c_connection1.ports['B'])
#             # Classical connection between P and V1
#             c_connection2 = ClassicalConnection(length=d, name='v1p', direction='Bi')
#             node_v1.ports['v1p'].connect(c_connection2.ports['A'])
#             node_p.ports['pv1'].connect(c_connection2.ports['B'])
#             # Classical connection between P and V2
#             c_connection3 = ClassicalConnection(length=d, name='v2p', direction='Bi')
#             node_v2.ports['v2p'].connect(c_connection3.ports['A'])
#             node_p.ports['pv2'].connect(c_connection3.ports['B'])

#             # Classical connection between V0 and V1
#             # c_connection3 = ClassicalConnection(length=d, name='v0v1', direction='Bi')
#             # node_v0.ports['v0v1'].connect(c_connection3.ports['A'])
#             # node_v1.ports['v1v0'].connect(c_connection3.ports['B'])

#             # Quantum connection between V0 and P, with delay = d/2e5, and attenuation
#             q_connection = QuantumConnection(name="Channel_A2B", length=d, direction='A2B', p_loss_length=p)
#             node_v0.ports['quantum'].connect(q_connection.ports['A'])
#             node_p.ports['quantum'].connect(q_connection.ports['B'])

#             v0_protocol = V0Protocol(node=node_v0, x=x, y=y, z=z, len=d)
#             p_protocol = PProtocol(node=node_p)
#             v1_protocol = V1Protocol(node=node_v1, y=y, len=d)
#             v2_protocol = V2Protocol(node=node_v2, z=z, len=d)
#             # Start protocol
#             p_protocol.start()
#             v0_protocol.start()
#             v1_protocol.start()
#             v2_protocol.start()
            
#             stats = ns.sim_run()
#             # Check results
#             a = v0_protocol.get_answer()
#             b = v1_protocol.get_answer()
#             c = v2_protocol.get_answer()
#             # t_a = v0_protocol.get_elapsed_time()
#             # t_b = v1_protocol.get_elapsed_time()
#             m = v0_protocol.get_result()
            
#             if a == 'Loss' or b == 'Loss' or c == 'Loss' or a is None or b is None or c is None:
#                 pass
#             else:
#                 if a == b == m == c: 
#                     print('Time and answer matches, correct!')
#                     correct_counter = correct_counter + 1
#                 elif a != b or a != m or c != m or a != c:
#                     print('Wrong')
#                 else:
#                     print('Abort')
#             # Reset the timer
#             ns.sim_reset()

#         time.append(v0_protocol.get_elapsed_time())
#         p_err.append((round-correct_counter)/round)
#     return p_err, loss_rate, time
# #%%
# p_err, loss_rate, time = main(round=100, distance=20, x=1, y=0, z=3)
# plt.figure(dpi=400)
# plt.plot(loss_rate, p_err)
# plt.legend()
# plt.xlabel('Photon loss rate')
# plt.ylabel('Error rate')
# # %%
