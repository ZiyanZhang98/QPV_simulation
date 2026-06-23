
#%%
from netsquid.components import QuantumChannel, ClassicalChannel
from netsquid.nodes import DirectConnection, Connection
from netsquid.components.models.qerrormodels import FibreLossModel
from netsquid.components.models import qerrormodels
import netsquid as ns
import random
#%%
LIGHT_SPEED_KM_S = 3e5
CLASSICAL_SIGNAL_SPEED_KM_S = LIGHT_SPEED_KM_S
QUBIT_SIGNAL_SPEED_KM_S = 2 * LIGHT_SPEED_KM_S / 3
NS_PER_SECOND = 1e9


def propagation_delay_s(length_km, speed_km_s):
    """Return propagation time in seconds for distance in km and speed in km/s."""
    return length_km / speed_km_s


def seconds_to_ns(seconds):
    """Convert seconds to NetSquid's nanosecond simulation-time unit."""
    return seconds * NS_PER_SECOND


def ns_to_seconds(nanoseconds):
    """Convert NetSquid nanoseconds to seconds."""
    return nanoseconds / NS_PER_SECOND


def propagation_delay_ns(length_km, speed_km_s):
    return seconds_to_ns(propagation_delay_s(length_km, speed_km_s))


class ClassicalConnection(DirectConnection):
    def __init__(self, length, name='ClassicalConnection', direction='Bi', models=None):
        '''
        Classical messages propagate at c = 3e5 km/s.

        IMPORTANT NOTE: it seems the default fibre delay model is broken. 
        '''
        super().__init__(name=name)
        self.len = length

        if direction != 'B2A':
            self.add_subcomponent(ClassicalChannel(
                                  'Channel_A2B',
                                  length=self.len,
                                  delay=propagation_delay_ns(self.len, CLASSICAL_SIGNAL_SPEED_KM_S),
                                  models=models),
                                  forward_input=[('A', 'send')],
                                  forward_output=[('B', 'recv')])

        if direction != 'A2B':
            self.add_subcomponent(ClassicalChannel(
                                  'Channel_B2A',
                                  length=self.len,
                                  delay=propagation_delay_ns(self.len, CLASSICAL_SIGNAL_SPEED_KM_S),
                                  models=models),
                                  forward_input=[('B', 'send')],
                                  forward_output=[('A', 'recv')])
# %%
class QuantumConnection(Connection):
    def __init__(self, length, name='QuantumConnection', direction='A2B', models=None, p_loss_init=0, p_loss_length=0.2):
        super().__init__(name=name)
        self.len = length
        if models is None:
            models = {
                'quantum_loss_model': FibreLossModel(p_loss_init=p_loss_init, p_loss_length=p_loss_length)
            }

        if direction != 'B2A':
            self.add_subcomponent(QuantumChannel(
                                  'QChannel_A2B',
                                  length=self.len,
                                  delay=propagation_delay_ns(self.len, QUBIT_SIGNAL_SPEED_KM_S),
                                  models=models),
                                  forward_input=[('A', 'send')],
                                  forward_output=[('B', 'recv')])

        if direction != 'A2B':
            self.add_subcomponent(QuantumChannel(
                                  'QChannel_B2A',
                                  length=self.len,
                                  delay=propagation_delay_ns(self.len, QUBIT_SIGNAL_SPEED_KM_S),
                                  models=models),
                                  forward_input=[('B', 'send')],
                                  forward_output=[('A', 'recv')])
# %%
class BitflipError():
    def __init__(self, p=0.1):
        self.p = p * 100
        self.qubit = None
    
    def error_operation(self, qubit):
        self.qubit = qubit
        r = random.randint(1, 100)
        if r <= self.p:
            dice = random.randint(0, 1)
            if dice == 1:
                ns.qubits.operate(self.qubit, ns.X)
            else:
                ns.qubits.operate(self.qubit, ns.H)
        else:
            ns.qubits.operate(self.qubit, ns.I)

        return self.qubit
