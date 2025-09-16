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


# 路径配置
bw_file_path = '../trace/bw_1.txt'
delay_file_path = '../trace/delay_1.txt'

# Linux Router 类
class LinuxRouter(Node):
    def config(self, **params):
        super(LinuxRouter, self).config(**params)
        self.cmd('sysctl net.ipv4.ip_forward=1')

    def terminate(self):
        self.cmd('sysctl net.ipv4.ip_forward=0')
        super(LinuxRouter, self).terminate()

# 带宽每10ms平均
def average_bandwidth_per_10ms(bandwidth_data, interval_ms=10):
    averaged_data = []
    for i in range(0, len(bandwidth_data), interval_ms):
        chunk = bandwidth_data[i:i+interval_ms]
        avg = sum(chunk) / len(chunk)
        averaged_data.append(avg)
    return averaged_data

# 读取 trace 文件
def generate_DelayAndBandwidth_sequence():
    bandwidth_data = []

    with open(bw_file_path, 'r') as f:
        cur = None
        cnt = 0
        for line in f:
            t = int(line.strip())
            if t == cur:
                cnt += 1
            else:
                if cur is not None:
                    bandwidth_data.append(cnt * 12)  # 每毫秒一个数据点
                cur, cnt = t, 1
        if cur is not None:
            bandwidth_data.append(cnt * 12)

    averaged_data = average_bandwidth_per_10ms(bandwidth_data, 10)

    with open(delay_file_path, 'r') as f:
        delays = [float(line.strip()) * 2 for line in f if line.strip()]

    return averaged_data, delays

# 动态设置延迟和带宽
def dynamicDelayAndPing(net, averaged_data, delays, interval=1):
    h1, r1 = net['h1'], net['r1']
    h1_intf = net.linksBetween(h1, r1)[0].intf1.name
    r1_intf = net.linksBetween(h1, r1)[0].intf2.name

    num_steps = min(len(averaged_data), len(delays))

    for i in range(num_steps):
        bw = averaged_data[i]
        delay = delays[i]

        h1.cmd(f"tc qdisc replace dev {h1_intf} root handle 1: tbf rate {bw}mbit burst 200mbit latency 400ms")
        h1.cmd(f"tc qdisc replace dev {h1_intf} parent 1:1 handle 10: netem delay {delay}ms")

        r1.cmd(f"tc qdisc replace dev {h1_intf} root handle 1: tbf rate {bw}mbit burst 200mbit latency 400ms")
        r1.cmd(f"tc qdisc replace dev {h1_intf} parent 1:1 handle 10: netem delay {delay}ms")

        info(f"[{i}] delay = {delay} ms, bandwidth = {bw} mbit\n")
        time.sleep(interval)
        
# 启动 QUIC 服务
def performanceEvaluation(h1, h2):
    info('\n****xquic begin****\n')
    time.sleep(2)
    # h1.cmd("cd /home/mxjpxk/xquic/xquic/build/tests && ./test_server -a 10.0.1.1 -l e > /home/mxjpxk/xquic/xquic_info/test_server.log &")
    # time.sleep(2)
    # h2.cmd("cd /home/mxjpxk/xquic/xquic/build/tests && ./test_client -a 10.0.1.1 -l e -c b -s 104800000 > /home/mxjpxk/xquic/xquic_info/test_client.log")
    h1.cmd('iperf -s -i 0.5 > /home/mxjpxk/xquic/xquic_info/iperf_server_cubic2.log &')
    time.sleep(2)
    h2.cmd('iperf -c 10.0.1.1 -t 240 -i 0.5 > /home/mxjpxk/xquic/xquic_info/iperf_client_cubic2.log')
# 主函数
if __name__ == '__main__':
    setLogLevel('info')

    # 预加载 trace 数据
    averaged_data, delays = generate_DelayAndBandwidth_sequence()

    # 拓扑设置
    net = Mininet(link=TCLink)
    h1 = net.addHost('h1', ip='10.0.1.1/24')
    h2 = net.addHost('h2', ip='10.0.2.2/24')
    r1 = net.addHost('r1', cls=LinuxRouter, ip='10.0.1.254/24')

    # net.addLink(h1, r1, intfName1='h1-eth0', intfName2='r1-eth0', bw=10, max_queue_size=10)
    # net.addLink(r1, h2, intfName1='r1-eth1', intfName2='h2-eth0', bw=10, max_queue_size=10)
    net.addLink(h1, r1, intfName1='h1-eth0', intfName2='r1-eth0', bw=10)
    net.addLink(r1, h2, intfName1='r1-eth1', intfName2='h2-eth0', bw=10)
    net.start()

    # 路由配置
    h1.cmd('ip route add default via 10.0.1.254')
    h2.cmd('ip route add default via 10.0.2.254')
    r1.cmd('ifconfig r1-eth1 10.0.2.254/24')

    # 初始链路设置（防止 tc 报错）
    h1.cmd("tc qdisc add dev h1-eth0 root netem delay 100ms")
    r1.cmd("tc qdisc add dev r1-eth0 root netem delay 100ms")

    os.system('sysctl net.ipv4.tcp_congestion_control=cubic')
    os.system('sysctl net.ipv4.tcp_congestion_control')
    # 启动线程
    p1 = Thread(target=dynamicDelayAndPing, args=(net, averaged_data, delays, 1))
    p2 = Thread(target=performanceEvaluation, args=(h1, h2))

    info('****multi-threading: dynamic network and QUIC****\n')
    # p1.start()
    p2.start()
    # p1.join()
    p2.join()

    CLI(net)
    net.stop()