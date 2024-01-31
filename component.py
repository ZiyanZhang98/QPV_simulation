
#%%
from netsquid.components import QuantumChannel, ClassicalChannel
from netsquid.nodes import DirectConnection, Connection
from netsquid.components.models.qerrormodels import FibreLossModel
from netsquid.components.models.delaymodels import FibreDelayModel
#%%
class ClassicalConnection(DirectConnection):
    def __init__(self, length, name='ClassicalConnection', direction='Bi', models=None):
        '''
        Init classical connection(s) between nodes. We assume data is tranmistted with microwave at speed c=3e5.

        IMPORTANT NOTE: it seems the default fibre delay model is broken. 
        '''
        super().__init__(name=name)
        self.len = length

        if direction != 'B2A':
            self.add_subcomponent(ClassicalChannel('Channel_A2B', length=self.len, deyal=self.len/3e5, models=models),
                                  forward_input=[('A', 'send')],
                                  forward_output=[('B', 'recv')])

        if direction != 'A2B':
            self.add_subcomponent(ClassicalChannel('Channel_B2A', length=self.len, delay=self.len/3e5, models=models),
                                  forward_input=[('B', 'send')],
                                  forward_output=[('A', 'recv')])
# %%
class QuantumConnection(Connection):
    def __init__(self, length, name='QuantumConnection', direction='A2B', models=None, p_loss_init=0, p_loss_length=0.2):
        super().__init__(name=name)
        self.len = length
        if models is None:
            models = {
                'quantum_loss_model': FibreLossModel(p_loss_init=p_loss_init, p_loss_length=p_loss_length),
                'delay_model': FibreDelayModel(c=2e5)
            }

        if direction != 'B2A':
            self.add_subcomponent(QuantumChannel('QChannel_A2B', length=self.len, models=models),
                                  forward_input=[('A', 'send')],
                                  forward_output=[('B', 'recv')])

        if direction != 'A2B':
            self.add_subcomponent(QuantumChannel('QChannel_B2A', length=self.len, models=models),
                                  forward_input=[('B', 'send')],
                                  forward_output=[('A', 'recv')])
# %%
