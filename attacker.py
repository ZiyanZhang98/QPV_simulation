#%%
import netsquid as ns
from netsquid.protocols import NodeProtocol
from component import BitflipError
import random
from bool_function import bool_func
#%%
class AliceProtocol(NodeProtocol):
    def __init__(self, node=None, name=None):
        super().__init__(node, name)
        self.state = ["|0>", "|1>", "|+>", "|->"]
        self.answer = None        
        self.port_q = self.node.ports['Alice_q']
        self.port_c1 = self.node.ports['Alice_c1']
        self.port_c2 = self.node.ports['Alice_c2']
        self.port_c3 = self.node.ports['Alice_c3']
    
    def random_guess(self):
         self.answer = self.state[random.randint(0, 3)]
         return self.answer
    
    def run(self):
        while True:
            yield self.await_port_input(self.port_c1)
            self.random_guess()
            # print(f'Random guess:{self.answer}')
            self.port_c1.tx_output(self.answer)
            self.port_c2.tx_output(self.answer)
            self.port_c3.tx_output(self.answer)
#%%