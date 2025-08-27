from mininet.net import Mininet
from mininet.topo import Topo
from mininet.node import Node, Controller, RemoteController, OVSSwitch, Host
from mininet.log import setLogLevel, info
from mininet.cli import CLI
from mininet.link import TCLink
from mininet.link import Intf
from mininet.term import makeTerm
from argparse import ArgumentParser
from subprocess import call
from threading import Thread
import time
from time import ctime, sleep
import os
import datetime
from multiprocessing import Process
import math

class LinuxRouter(Node):
    def config(self, **params):
        super(LinuxRouter, self).config(**params)
        self.cmd('sysctl net.ipv4.ip_forward=1')
    def terminate(self):
        self.cmd('sysctl net.ipv4.ip_forward=0')
        super(LinuxRouter, self).terminate()

def generate_delayed_sequence(duration=60, interval=1, start=50, end=10):
    steps = int(duration / interval)
    delays = []
    for i in range(steps):
        delay = start + (end - start) / 2 * (1 - math.cos(2 * math.pi * i / steps))

        delays.append(f"{round(delay, 2)}ms")

    return delays

def dynamicDelayAndPing(net,interval=1):
    delays = generate_delayed_sequence(duration=60, interval=1, start=50, end=10)
    h1_intf = net.linksBetween(net['h1'], net['r1'])[0].intf1.name
    net['h1'].cmd(f"tc qdisc add dev {h1_intf} root netem delay {delays[0]}")
    info(f"[delay] 初始 delay = {delays[0]} on {h1_intf}\n")
    for delay in delays[1:]:
        time.sleep(interval)
        # 设置双向 delay
        h1.cmd(f"tc qdisc change dev {h1_intf} root netem delay {delay}")
        r1.cmd(f"tc qdisc change dev r1-eth0 root netem delay {delay}")
    
def performanceEvaluation(h1,h2):
  
    info('\n****xquic begin****\n')
    time.sleep(2)
    # h1.cmd("cd /home/mxjpxk/xquic/xquic/build/tests && ./test_server -a 10.0.1.1 -l d > /home/mxjpxk/xquic/xquic_info/test_server.log & ")
    h1.cmd("iperf -s -i 0.5 > /home/mxjpxk/xquic/xquic_info/iperf_server_bbr.log &")
    time.sleep(2)
    # h2.cmd('cd /home/mxjpxk/xquic/xquic/build/tests && ./test_client -a 10.0.1.1 -l d -c b -s 104800000 > /home/mxjpxk/xquic/xquic_info/test_client.log')
    h2.cmd("iperf -c 10.0.1.1 -t 60 -i 0.5 > /home/mxjpxk/xquic/xquic_info/iperf_client_bbr.log")


if __name__ == '__main__':
    setLogLevel('info')
    
    net = Mininet(link=TCLink)
    h1 = net.addHost('h1', ip='10.0.1.1/24')
    h2 = net.addHost('h2', ip='10.0.2.2/24')
    r1 = net.addHost('r1', cls=LinuxRouter, ip='10.0.1.254/24')

    net.addLink(h1, r1, intfName1='h1-eth0', intfName2='r1-eth0', bw=10, max_queue_size=10)
    net.addLink(r1, h2, intfName1='r1-eth1', intfName2='h2-eth0', bw=10, delay='10ms',max_queue_size=10)

    net.start()

    h1.cmd('ip route add default via 10.0.1.254')
    h2.cmd('ip route add default via 10.0.2.254')
    r1.cmd('ifconfig r1-eth1 10.0.2.254/24')
    r1.cmd("tc qdisc add dev r1-eth0 root netem delay 50ms")
    h1.cmd("tc qdisc add dev h1-eth0 root netem delay 50ms")

    p1 = Thread(target = dynamicDelayAndPing,args=(net,1))

    p2 = Thread(target = performanceEvaluation,args=(h1,h2))

    info('****multi-threading: handover and iperf****\n')

    os.system('sysctl net.ipv4.tcp_congestion_control=bbr')
    os.system('sysctl net.ipv4.tcp_congestion_control')
    p1.start()
    p2.start()
    p1.join()
    p2.join()

    CLI(net)
    net.stop()