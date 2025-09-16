# -*- coding: utf-8 -*-
"""
Created on Wed Oct 13 17:13:44 2021

@author: HH
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
import math
from threading import Thread
import logging

# 设置日志输出到文件和终端
logging.basicConfig(filename='/home/mxjpxk/xquic/xquic_info/mininet.log', level=logging.INFO, format='%(asctime)s %(message)s',filemode = 'w')
logging.getLogger().addHandler(logging.StreamHandler())

handover_h1 = [(0, 'r12'), (1, 'r13'), (2, 'r14')]
OrbitNumber = 3
satellitePerOrbit = 4
num_router = 12

# 启用 IP 转发功能
class LinuxRouter(Node):
    "A Node with IP forwarding enabled."

    def config(self, **params):
        super(LinuxRouter, self).config(**params)
        # Enable forwarding on the router
        self.cmd('sysctl net.ipv4.ip_forward=1')

    def terminate(self):
        self.cmd('sysctl net.ipv4.ip_forward=0')
        super(LinuxRouter, self).terminate()

# 生成轨道内与轨道间的 ISL 链路，启动路由服务
def satelliteToSatelliteTopoGenerating():
    info('*** Adding Link\n')
    
    # 同轨道卫星间的链路
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
            # net.addLink("r"+ new_i + new_j, "r" + new_i + new_j_next, cls=TCLink, bw=10, delay='5.9ms',max_queue_size=10,loss=0)
            net.addLink("r"+ new_i + new_j, "r" + new_i + new_j_next, cls=TCLink, bw=10, delay='5.9ms',loss=0)
    # 不同轨道间的链路
    info('***Add orbit-to-orbit ISLs\n')
    for i in range(OrbitNumber):
        new_i = str(i + 1)
        if i == OrbitNumber - 1:
            new_i_next = str(1)
        else:
            new_i_next = str(i + 2)
        for j in range(satellitePerOrbit):
            new_j = str(j + 1)
            # net.addLink("r" + new_i + new_j, "r" + new_i_next + new_j, cls=TCLink, bw=10, delay='5.9ms', max_queue_size=10,loss=0)
            net.addLink("r" + new_i + new_j, "r" + new_i_next + new_j, cls=TCLink, bw=10, delay='5.9ms',loss=0)
    info('*** Starting network\n')
    net.build()
    info('*** Starting controllers\n')
    for controller in net.controllers:
        controller.start()

    info("Waiting %d seconds for sysctl changes to take effect...\n" % args.sleep)
    time.sleep(args.sleep)

    info('starting zebra and ospfd service:\n')

    # 配置路由，使用 zebra和ospfd生成ospf路由
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

    # 生成路由表
    info('*** Routing Table on Router:\n')
    for i in range(OrbitNumber):
        new_i = str(i + 1)
        for j in range(satellitePerOrbit):
            new_j = str(j + 1)
            info( net["r"+new_i+new_j].cmd('route'))
            time.sleep(1)

# 生成延迟序列，用于模拟卫星由远及近再到远的过程
def generate_delayed_sequence(duration=60, interval=1, start=15, end=5):
    steps = int(duration / interval)
    delays = []
    for i in range(steps):
        delay = start + (end - start) / 2 * (1 - math.cos(2 * math.pi * i / steps))
        delays.append(f"{round(delay, 2)}ms")
    return delays

def handover_and_rtt_thread_1(net, h1, h2, interval=1):

    info(f"*** Starting handover_and_rtt_thread_1 ***\n")
    try:
        bandwidths = [6, 7, 8]
        delays = generate_delayed_sequence(duration=60, interval=1, start=15, end=5)
        delay_index = 0
        handover_index = 0
        handover_time = 60
        last_handover_time = time.time()
        last_rtt_update_time = time.time()
        current_satellite = net.getNodeByName('r11')  # 初始化连接 r11
        max_cycles = len(handover_h1)
        start_time = time.time()

        info(f"*** Handover cycle count: {max_cycles} ***\n")

        while handover_index < max_cycles:
            now = time.time()
            elapsed = now - start_time
            # 更新 h1-卫星链路的动态延迟
            if now - last_rtt_update_time >= interval:
                current_delay = delays[delay_index % len(delays)]
                info(f"*** Updating delay to {current_delay} on h1-{current_satellite.name} link ***\n")                
                try:
                    if current_satellite:
                        link = net.linksBetween(h1, current_satellite)
                        if link:
                            h1_intf = link[0].intf1.name
                            sat_intf = link[0].intf2.name
                            # 更新 h1 和卫星接口的延迟
                            h1.cmd(f"tc qdisc change dev {h1_intf}  parent 1:1 handle 10: netem delay {current_delay}ms")
                            current_satellite.cmd(f"tc qdisc change dev {sat_intf} parent 1:1 handle 10: netem delay {current_delay}ms")
                            info(f"[RTT] Delay set to {current_delay}ms on {h1_intf} and {sat_intf}\n")
                except Exception as e:
                    info(f"*** Error in delay update loop: {e} ***\n")
                    raise
                delay_index += 1
                last_rtt_update_time = now
            # 切换
            if now - last_handover_time >= handover_time:
                info(f"*** Performing handover, index: {handover_index} ***\n")
                try:
                    if current_satellite:
                        link = net.linksBetween(h1, current_satellite)
                        if link:
                            h1_intf = link[0].intf1.name
                            sat_intf = link[0].intf2.name
                            # 清除旧接口的动态延迟，恢复固定延迟
                            h1.cmd(f"ifconfig {h1_intf} down")
                            current_satellite.cmd(f"ifconfig {sat_intf} down")
                            h1.cmd(f"tc qdisc del dev {h1_intf} root 2>/dev/null")
                            current_satellite.cmd(f"tc qdisc del dev {sat_intf} root 2>/dev/null")
                            info(f"** Disabled link between h1 and {current_satellite.name} **\n")
                except Exception as e:
                    info(f"*** Error deleting link to {current_satellite.name}: {e} ***\n")
                    raise

                item = handover_h1[handover_index % len(handover_h1)]
                sat_name = item[1]
                try:
                    current_bandwidth = bandwidths[handover_index % len(bandwidths)]
                    current_satellite = net.getNodeByName(sat_name)
                    sat_ip = f"10.1.0.{int(sat_name[1:])}"
                    info(f"*** Adding link to {sat_name} with IP {sat_ip} ***\n")
                    # net.addLink('h1', current_satellite, cls=TCLink, bw= current_bandwidth, delay='3.6667ms', max_queue_size=10,loss=0)
                    net.addLink('h1', current_satellite, cls=TCLink, bw= current_bandwidth, delay='3.6667ms',loss=0)
                    info(f"****11111111111111111***\n")
                    result = h1.cmd('tc class show dev h1-eth0')
                    info(f"切换后结果为：{result}\n")
                    link = net.linksBetween(h1, current_satellite)[0]

                    h1_intf = link.intf1.name
                    sat_intf = link.intf2.name
                    h1.cmd(f"ifconfig {h1_intf} up")
                    current_satellite.cmd(f"ifconfig {sat_intf} up")
                    h1.cmd(f"ifconfig {h1_intf} 10.1.0.200 netmask 255.255.255.0")
                    current_satellite.cmd(f"ifconfig {sat_intf} {sat_ip} netmask 255.255.255.0")
                    h1.cmd(f'ip route del default 2>/dev/null')
                    h1.cmd(f'ip route add default via {sat_ip} dev {h1_intf}')
                    info(f"** h1 connected to {sat_name} with gateway {sat_ip} **\n")
                    # 设置新链路的动态延迟
                    current_delay = delays[0]  # 15ms
                    info(f"*** Applying HTB+NETEM on {h1.name}:{h1_intf} for bw={current_bandwidth}Mbps delay={current_delay} ***\n")
                    # 删除旧的配置
                    h1.cmd(f"tc qdisc del dev {h1_intf} root 2>/dev/null")  
                    current_satellite.cmd(f"tc qdisc del dev {sat_intf} root 2>/dev/null")
                    # 添加 htb + netem（下挂 netem 实现 delay/loss）
                    h1.cmd(f"tc qdisc add dev {h1_intf} root handle 1: htb default 1")
                    h1.cmd(f"tc class add dev {h1_intf} parent 1: classid 1:1 htb rate {current_bandwidth}mbit ceil {current_bandwidth}mbit")
                    h1.cmd(f"tc qdisc add dev {h1_intf} parent 1:1 handle 10: netem delay {current_delay} loss 0%")
                    current_satellite.cmd(f"tc qdisc add dev {sat_intf} root handle 1: htb default 1")
                    current_satellite.cmd(f"tc class add dev {sat_intf} parent 1: classid 1:1 htb rate {current_bandwidth}mbit ceil {current_bandwidth}mbit")
                    current_satellite.cmd(f"tc qdisc add dev {sat_intf} parent 1:1 handle 10: netem delay {current_delay} loss 0%")
                    # 打印确认
                    info(f"--- h1 tc show ---\n{h1.cmd(f'tc qdisc show dev {h1_intf}')} {h1.cmd(f'tc class show dev {h1_intf}')}")
                    info(f"--- sat tc show ---\n{current_satellite.cmd(f'tc qdisc show dev {sat_intf}')} {current_satellite.cmd(f'tc class show dev {sat_intf}')}")
                    last_rtt_update_time = now
                    delay_index = 0
 
                    # 验证切换后是否生效
                    info(f"** Pinging from h1 to h2 (10.2.0.200) after connecting to {sat_name} **\n")
                    ping_result = h1.cmd('ping -c 3 10.2.0.200')
                    info(f"Ping result:\n{ping_result}\n")
                except Exception as e:
                    info(f"*** Error during handover to {sat_name}: {e} ***\n")
                    raise
                handover_index += 1
                last_handover_time = now
            time.sleep(max(0, 0.1 - (time.time() - now)))
        info(f"*** Handover complete, total elapsed time: {(time.time() - start_time):.2f}s ***\n")
    except Exception as e:
        info(f"*** Fatal error in handover_and_rtt_thread_1: {e} ***\n")
        raise
   
def performanceEvaluation(h1, h2):
    info('\n****xquic begin****\n')
    time.sleep(2)
    h1.cmd("cd /home/mxjpxk/xquic/xquic/build/tests && ./test_server -a 10.1.0.200 -l e -c b > /home/mxjpxk/xquic/xquic_info/test_server.log & ")
    time.sleep(5)
    h2.cmd('cd /home/mxjpxk/xquic/xquic/build/tests && ./test_client -a 10.1.0.200 -l e -c b -s 104800400 -t 10 -1 > /home/mxjpxk/xquic/xquic_info/test_client.log')

# def performanceEvaluation(h1,h2):
#     info('\n****Performance evaluation with BBR and iperf begin****\n')
#     info('*** Starting iperf server on h1 ***\n')
#     h1.cmd('iperf -s -i 0.5 > /home/mxjpxk/xquic/xquic_info/iperf_server_reno.log &')
#     time.sleep(2)
#     info('*** Starting iperf client on h2, sending data to h1 (10.1.0.200) for 240s ***\n')
#     h2.cmd('iperf -c 10.1.0.200 -t 240 -i 0.5 > /home/mxjpxk/xquic/xquic_info/iperf_client_reno.log')
#     # h2.cmd("bash -c 'for i in {1..480}; do ss -ti dst 10.1.0.200 >> /home/mxjpxk/xquic/xquic_info/cwnd_client_cubic.log; sleep 0.5; done'")
#     info('\n****Performance evaluation complete****\n')


if __name__ == "__main__":
    setLogLevel('info')
    parser = ArgumentParser("Configure 1 OSPF AS in Mininet.")
    parser.add_argument('--sleep', default=3, type=int)
    args = parser.parse_args()
    net = Mininet(topo=None, build=False, ipBase='10.0.0.0/8')
    # ROUTERS
    info('*** Adding satellite routers\n')
    for i in range(OrbitNumber):
        for j in range(satellitePerOrbit):
            net.addHost("r" + str(i + 1) + str(j + 1), cls=LinuxRouter, ip='0.0.0.0')

    info('*** Adding Host\n')
    # HOSTS
    h1 = net.addHost('h1', cls=Host, ip='10.1.0.200/24', defaultRoute=None)
    h2 = net.addHost('h2', cls=Host, ip='10.2.0.200/24', defaultRoute=None)

    satelliteToSatelliteTopoGenerating()
    net.start()

    info('\n****dynamic part one:Initialization****\n')
    sat_name = 'r11'
    sat_ip = f"10.1.0.{int(sat_name[1:])}"  # Dynamic IP: r11 -> 10.1.0.11
    # net.addLink('h1', net[sat_name], cls=TCLink, bw=5, delay='3.6667ms',max_queue_size=10,loss=0)
    net.addLink('h1', net[sat_name], cls=TCLink, bw=5, delay='3.6667ms',loss=0)
    link = net.linksBetween(h1, net[sat_name])[0]
    h1_intf = link.intf1.name
    sat_intf = link.intf2.name
    h1.cmd(f'ifconfig {h1_intf} 10.1.0.200 netmask 255.255.255.0')
    net[sat_name].cmd(f'ifconfig {sat_intf} {sat_ip} netmask 255.255.255.0')
    h1.cmd(f'route add default gw {sat_ip} dev {h1_intf}')
    
    # net.addLink('h2', net['r34'], cls=TCLink, bw=10, delay='3.6667ms', max_queue_size=10,loss=0)
    net.addLink('h2', net['r34'], cls=TCLink, bw=10, delay='3.6667ms',loss=0)
    link = net.linksBetween(h2, net['r34'])[0]
    h2_intf = link.intf1.name
    sat_intf = link.intf2.name
    h2.cmd(f'ifconfig {h2_intf} 10.2.0.200 netmask 255.255.255.0')
    net['r34'].cmd(f'ifconfig {sat_intf} 10.2.0.34 netmask 255.255.255.0')
    h2.cmd(f'route add default gw 10.2.0.34 dev {h2_intf}')
    time.sleep(70)
    info('\n*r11 route table*\n')
    info(net['r11'].cmd('route'))

    ping_result = h1.cmd('ping -c 3 10.2.0.200')
    info(f"Ping result:\n{ping_result}\n")
    ping_result = h2.cmd('ping -c 3 10.1.0.200')
    info(f"Ping result:\n{ping_result}\n")

    os.system('sysctl net.ipv4.tcp_congestion_control=reno')
    os.system('sysctl net.ipv4.tcp_congestion_control')

    t1 = Thread(target=handover_and_rtt_thread_1, args=(net,h1,h2,1))
    t2 = Thread(target=performanceEvaluation, args=(h1, h2))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    CLI(net)
    net.stop()
    os.system("killall -9 ospfd zebra")
    os.system("rm -f /home/mxjpxk/xquic/*.api")
    os.system("rm -f /home/mxjpxk/xquic/*.interface")