#!/usr/bin/env python3
import os
from time import sleep

from mininet.net import Mininet
from mininet.topo import Topo
from mininet.log import setLogLevel
from mininet.cli import CLI
from p4_mininet import P4Switch

# --- 1. Define the Dumbbell Topology ---
class DumbbellTopo(Topo):
    "Dumbbell topology with two P4 switches and a bottleneck link"

    def build(self, **_opts):
        # Define the bottleneck link properties (10 Mbps)
        link_opts = dict(bw=10)

        # Add switches
        # s1 will run our P4 program
        s1 = self.addSwitch('s1', sw_path='simple_switch_grpc',
                            json_path='qos.json',
                            p4runtime_port=50051)
        # s2 will ALSO run our P4 program
        s2 = self.addSwitch('s2', sw_path='simple_switch_grpc',
                            json_path='qos.json',
                            p4runtime_port=50052)

        # Add hosts
        h1 = self.addHost('h1', ip='10.0.0.1/24', mac='00:00:00:00:00:01')
        h2 = self.addHost('h2', ip='10.0.0.2/24', mac='00:00:00:00:00:02')
        h3 = self.addHost('h3', ip='10.0.0.3/24', mac='00:00:00:00:00:03')
        h4 = self.addHost('h4', ip='10.0.0.4/24', mac='00:00:00:00:00:04')

        # Link hosts to switches
        self.addLink(h1, s1) # s1-eth1
        self.addLink(h2, s1) # s1-eth2
        self.addLink(h3, s2) # s2-eth1
        self.addLink(h4, s2) # s2-eth2

        # Link switches to create the bottleneck
        self.addLink(s1, s2, **link_opts) # s1-eth3 <-> s2-eth3


# --- 2. Function to set up the Priority Queues ---
def setup_queues(switch, port):
    print("Setting up priority queues on %s port %s..." % (switch.name, port))

    # 1. Delete any existing queue disciplines
    switch.cmd('tc qdisc del dev %s root' % port)

    # 2. Create a 'prio' (priority) queue discipline with 2 "bands"
    switch.cmd('tc qdisc add dev %s root handle 1: prio bands 2' % port)

    # 3. Add a 10Mbit rate limit to the *entire* queue
    # This is our bottleneck!
    switch.cmd('tc qdisc add dev %s parent 1: handle 10: tbf rate 10mbit buffer 1600 limit 3000' % port)

    # 4. Create a filter to map P4 priority '1' to the high-priority band (band 0)
    switch.cmd('tc filter add dev %s parent 1: protocol ip prio 1 handle 1: basic' % port)

    # 5. Map P4 priority '0' (the default) to the low-priority band (band 1)
    switch.cmd('tc filter add dev %s parent 1: protocol ip prio 0 handle 2: basic' % port)

    print("Queues are set up.")


# --- 3. The Main Program ---
def main():
    print("\n" + "="*30)
    print("Network is ready!")
    print("1. Open a new terminal and run: /usr/bin/python3.8 -m p4runtime_sh --grpc-addr 127.0.0.1:50051 --config p4info.txt,qos.json < rules_s1.txt")
    print("2. Open a *third* terminal and run: /usr/bin/python3.8 -m p4runtime_sh --grpc-addr 127.0.0.1:50052 --config p4info.txt,qos.json < rules_s2.txt")
    print("3. In this terminal, run the benchmark (h2 ... & then h1 ...)")
    print("="*30 + "\n")
    if not os.path.exists('qos.json'):
        print("Error: 'qos.json' not found.")
        return

    topo = DumbbellTopo()
    net = Mininet(topo=topo, controller=None)

    net.start()
    print("Mininet network started.")

    s1 = net.get('s1')
    s2 = net.get('s2')

    # --- This is the critical step ---
    # Apply the bottleneck queues to the egress side of the shared link
    setup_queues(s1, 's1-eth3')

    h3 = net.get('h3')
    h4 = net.get('h4')

    print("Starting iperf servers on h3 and h4...")
    h3.cmd('iperf -s &')
    h4.cmd('iperf -s &')

    sleep(1)

    print("\n" + "="*30)
    print("Network is ready!")
    print("1. Open a new terminal and run: p4runtime-shell --grpc-addr 127.0.0.1:50051 --config p4info.txt,qos.json < rules_s1.txt")
    print("2. Open a *third* terminal and run: p4runtime-shell --grpc-addr 127.0.0.1:50052 --config p4info.txt,qos.json < rules_s2.txt")
    print("3. In this terminal, run the benchmark (h2 ... & then h1 ...)")
    print("="*30 + "\n")

    CLI(net)

    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    main()