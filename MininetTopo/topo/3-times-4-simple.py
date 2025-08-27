# -*- coding: utf-8 -*-
"""
Created on Wed Oct 13 17:13:44 2025

@author: MXJ
"""

# !/usr/bin/env python3


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
import time
from time import ctime, sleep
import os
import datetime
from multiprocessing import Process


baseTime = datetime.datetime.strptime('2021-12-27 04:00:00', '%Y-%m-%d %H:%M:%S')
endTime = datetime.datetime.strptime('2021-12-27 05:00:00', '%Y-%m-%d %H:%M:%S')
OrbitNumber = 3
satellitePerOrbit = 4
num_router = 12

class LinuxRouter(Node):
    "A Node with IP forwarding enabled."

    def config(self, **params):
        super(LinuxRouter, self).config(**params)
        # Enable forwarding on the router
        self.cmd('sysctl net.ipv4.ip_forward=1')

    def terminate(self):
        self.cmd('sysctl net.ipv4.ip_forward=0')
        super(LinuxRouter, self).terminate()


def satelliteToSatelliteTopoGenerating():
    info('*** Adding Link\n')

    info('***Add in-orbit ISLs\n')
    for i in range(OrbitNumber):
        new_i = str(i + 1)
        for j in range(satellitePerOrbit):
            if j == satellitePerOrbit - 1:
                new_j = str(j + 1)
                new_j_next = str(1)
            else:
                new_j = str(j + 1)
                new_j_next = str(j + 2)
            net.addLink("r"+ new_i + new_j, "r" + new_i + new_j_next, cls=TCLink, bw=10, delay='5.9ms', loss=0)

    info('***Add orbit-to-orbit ISLs\n')
    for i in range(OrbitNumber):
        new_i = str(i + 1)
        if i == OrbitNumber - 1:
            new_i_next = str(1)
        else:
            new_i_next = str(i + 2)
        for j in range(satellitePerOrbit):
            new_j = str(j + 1)
            net.addLink("r" + new_i + new_j, "r" + new_i_next + new_j, cls=TCLink, bw=10, delay='5.9ms', loss=0)

    info('*** Starting network\n')
    net.build()
    info('*** Starting controllers\n')
    for controller in net.controllers:
        controller.start()

    info("Waiting %d seconds for sysctl changes to take effect...\n" % args.sleep)
    time.sleep(args.sleep)

    info('starting zebra and ospfd service:\n')

    # zebra configure
    for i in range(OrbitNumber):
        new_i = str(i + 1)
        for j in range(satellitePerOrbit):
            new_j = str(j + 1)
            net.getNodeByName("r"+ new_i + new_j).cmd("zebra -f /home/mxjpxk/xquic/MininetTopo/config/3-times-4/zebra-r" + new_i + new_j +
                                                    ".conf -d -z /home/mxjpxk/xquic/zebra-r" + new_i + new_j +
                                                    ".api -i /home/mxjpxk/xquic/zebra-r"+ new_i + new_j + ".interface")
    time.sleep(1)
    # ospfd configure
    for i in range(OrbitNumber):
        new_i = str(i + 1)
        for j in range(satellitePerOrbit):
            new_j = str(j + 1)
            net.getNodeByName("r" + new_i + new_j).cmd("ospfd -f /home/mxjpxk/xquic/MininetTopo/config/3-times-4/ospfd-r" + new_i + new_j +
                                                    ".conf -d -z /home/mxjpxk/xquic/zebra-r" + new_i + new_j +
                                                    ".api -i /home/mxjpxk/xquic/ospfd-r"+ new_i + new_j + ".interface")


    info('*** Routing Table on Router:\n')
    for i in range(OrbitNumber):
        new_i = str(i + 1)
        for j in range(satellitePerOrbit):
            new_j = str(j + 1)
            info( net["r"+new_i+new_j].cmd('route'))
            time.sleep(1)

# def handoverProcessofh1():
#     access_satellites = ['r11', 'r21', 'r31']
#     switch_interval = 10
#     for i in range(len(access_satellites)):
#         accessSatellite = net.getNodeByName(access_satellites[i])
#         info('\n**add link: h1<----->' + access_satellites[i] + '**\n')
#         net.addLink('h1', accessSatellite, cls=TCLink, bw=10, delay='3.6667ms', loss=5)
#         h1.cmd('ifconfig h1-eth0 10.1.0.200 netmask 255.255.255.0')
#         accessSatellite.cmd('ifconfig ' + access_satellites[i] + '-eth4 10.1.0.11 netmask 255.255.255.0')
#         h1.cmd('route add default gw 10.1.0.11 dev h1-eth0')
#         time.sleep(switch_interval)
#         info('**delete links between ' + access_satellites[i] + ' and h1**\n')
#         net.delLinkBetween(h1, accessSatellite)
#         info('**h1 handover of current round finish!**\n')

# def handoverProcessofh2():
#     for i in range(len(handover_h2)):
#         info('\n**add link: h2<----->' + handover_h2[i][3] + '**\n')
#         accessSatellite = net.getNodeByName(handover_h2[i][3])
#         net.addLink('h2', accessSatellite, cls=TCLink, bw=10, delay='3.6667ms', loss=5)
#         h2.cmd('ifconfig h2-eth0 10.2.0.200 netmask 255.255.255.0')
#         accessSatellite.cmd('ifconfig ' + handover_h2[i][3] + '-eth4 10.2.0.56 netmask 255.255.255.0')
#         h2.cmd('route add default gw 10.2.0.56 dev h2-eth0')
#         # info(accessSatellite.cmd('route'))
#         time.sleep(handover_h2[i][2])
#         info('**delete links between ' + handover_h2[i][3] + ' and h2**\n')
#         net.delLinkBetween(h2, accessSatellite)
#         info('**h2 handover of current round finish!**\n')

# def performanceEvaluation():
#     # print(datetime.datetime.now())
#     # net.iperf((h1, h2), seconds=10)
#     # print(datetime.datetime.now())
#     # makeTerm(h1, cmd="bash -c 'ping 10.2.0.200;'")
#     # makeTerm(r11, cmd="bash -c 'tcpdump host 10.2.0.200;'")
#     info("iperf")
#     makeTerm(h2, cmd="bash -c 'iperf -s -t 37 -i 0.001 -f k > /home/hui-1/Desktop/cubic-interval-0.01s-all-37s-server_perf_k.txt'")
#     makeTerm(h1, cmd="bash -c 'iperf -c 10.2.0.200 -t 37 -i 0.001 -f k > /home/hui-1/Desktop/cubic-interval-0.01s-all-37s-client_perf_k.txt'")
#     # time.sleep(2)
#     # makeTerm(h1, cmd="bash -c 'tcpdump -XX -n -i h1-eth0 > /home/hui-1/Desktop/h1.pcap' ")


# processes = []
#   p1 = Process(target=performanceEvaluation)
#   processes.append(p1)
# p2 = Process(target=handoverProcessofh1)
# processes.append(p2)
# # p3 = Process(target=handoverProcessofh2)
# # processes.append(p3)



if __name__ == "__main__":
    setLogLevel('info')
    parser = ArgumentParser("Configure 1 OSPF AS in Mininet.")
    parser.add_argument('--sleep', default=3, type=int)
    args = parser.parse_args()

    net = Mininet(topo=None,
                  build=False,
                  ipBase='10.0.0.0/8')
    # ROUTERS
    info('*** Adding satellite routers\n')
    for i in range(OrbitNumber):
        for j in range(satellitePerOrbit):
            net.addHost("r" + str(i + 1) + str(j + 1), cls=LinuxRouter, ip='0.0.0.0')

    info('*** Adding Host\n')
    # HOSTS
    h1 = net.addHost('h1', cls=Host, ip='10.1.0.200/24', defaultRoute=None)  # define gateway
    h2 = net.addHost('h2', cls=Host, ip='10.2.0.200/24', defaultRoute=None)

    satelliteToSatelliteTopoGenerating()

    net.start()
    info('\n****dynamic part one:Initialization****\n')
    net.addLink('h1',net['r11'])
    h1.cmd('ifconfig h1-eth0 10.1.0.200 netmask 255.255.255.0')
    net['r11'].cmd('ifconfig r11-eth4 10.1.0.11 netmask 255.255.255.0')
    h1.cmd('route add default gw 10.1.0.11 dev h1-eth0')
    
    net.addLink('h2', net['r34'])
    h2.cmd('ifconfig h2-eth0 10.2.0.200 netmask 255.255.255.0')
    net['r34'].cmd('ifconfig r34-eth4 10.2.0.34 netmask 255.255.255.0')
    h2.cmd('route add default gw 10.2.0.34 dev h2-eth0')
    time.sleep(20)
    info('\n*r11 route table*\n')
    info( net[ 'r11' ].cmd( 'route' ) )

    # time.sleep(30)
    # info('\n****xquic begin****\n')
    # h1.cmd('cd /home/mxjpxk/xquic/xquic/build/tests')
    # h2.cmd('cd /home/mxjpxk/xquic/xquic/build/tests')
    # h1.cmd("./test_server -a 10.1.0.200 -l d > /home/mxjpxk/xquic/xquic_info/test_server.log & ")
    # time.sleep(5)
    # h2.cmd('./test_client -a 10.1.0.200 -l d -c b -S 10 -n 500 > /home/mxjpxk/xquic/xquic_info/test_client.log')
  
    CLI(net)
    net.stop()
    os.system("killall -9 ospfd zebra")
    os.system("rm -f /home/mxjpxk/xquic/*.api")
    os.system("rm -f /home/mxjpxk/xquic/*.interface")




