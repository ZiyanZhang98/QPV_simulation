#%%
import netsquid as ns
import numpy as np
import random
# %%
# Random basis and encoded qubit
basis = random.randint(0, 1)
z = random.randint(0, 1)
# %%
qubit_v0 = ns.qubits.create_qubits(1)
# %%
