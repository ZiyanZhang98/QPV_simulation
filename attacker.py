#%%
import netsquid as ns
from netsquid.protocols import NodeProtocol
from component import BitflipError
import random
from bool_function import bool_func
#%%
class Alice_g(NodeProtocol):
    def __init__(self, node=None, name=None):
        super().__init__(node, name)
        self.basis = None
        self.qubit = None
        self.answer = None   
        self.port_q = self.node.ports['Alice_q']
        self.port_ab = self.node.ports['Alice_b']
        self.port_ac = self.node.ports['Alice_c']
        self.port_c = self.node.ports['Alice_c3']
    
    def random_guess(self):
         self.basis = self.state[random.randint(0, 2)]
         if self.basis == 0:
                state, prob = ns.qubits.measure(self.qubit)
                labels_z =  ("|0>", "|1>")
                self.answer = labels_z[state]
                print(f"guess:{self.answer}")
         else:
            state, prob = ns.qubits.measure(self.qubit, observable=ns.X)
            labels_z =  ("|+>", "|->")
            self.answer = labels_z[state]
            print(f"guess:{self.answer}")
    
    def run(self):
        while True:
            yield (self.await_port_input(self.port_q) or self.await_port_input(self.port_c))
            self.qubit = self.port_q.rx_input().items[0]
            z = self.port_c.rx_input().items[0]
            self.random_guess()
            yield (self.await_port_input(self.port_ab) or self.await_port_input(self.port_ac))
            x = self.port_ab.rx_input().items[0]
            y = self.port_ac.rx_input().items[0]
            if bool_func(x, y, z) == self.basis:
                self.answer = None
            self.port_ab.tx_output(self.answer)
            self.port_ac.tx_output(self.answer)
            self.port_c.tx_output(self.answer)

class Bob_g(NodeProtocol):
    def __init__(self, node=None, name=None):
        super().__init__(node, name)
        self.answer = None        
        self.port_ba = self.node.ports['ba']
        self.port_c = self.node.ports['Bob']
    
    def run(self):
        while True:
            yield self.await_port_input(self.port_c)
            self.answer = self.port_c.rx_input().items[0]
            self.port_ba.tx_output(self.answer)
            yield self.await_port_input(self.port_ba)
            self.port_c.tx_output(self.answer)

class Charlie_g(NodeProtocol):
    def __init__(self, node=None, name=None):
        super().__init__(node, name)
        self.answer = None        
        self.port_ca = self.node.ports['ca']
        self.port_c = self.node.ports['Charlie']
    
    def run(self):
        while True:
            yield self.await_port_input(self.port_c)
            self.answer = self.port_c.rx_input().items[0]
            self.port_ca.tx_output(self.answer)
            yield self.await_port_input(self.port_ca)
            self.port_c.tx_output(self.answer)