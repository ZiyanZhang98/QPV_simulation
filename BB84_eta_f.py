#%%
import netsquid as ns
import numpy as np
import random
import pydynaa
# %%
# Random basis and encoded qubit
x = random.randint(0, 1)
y = random.randint(0, 1)
eta = 0.1
# %% Prepare EPR pairs
q1 = ns.qubits.create_qubits(1)[0]
q2 = ns.qubits.create_qubits(1)[0]
ns.qubits.operate(q2, ns.H)
ns.qubits.operate([q1,q2], ns.CNOT)
# %%
