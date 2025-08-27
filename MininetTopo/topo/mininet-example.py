#!/usr/bin/env python3
# coding: utf-8
 
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import Node
from mininet.log import setLogLevel, info
from mininet.cli import CLI
import time
import os
 
class LinuxRouter( Node ):
    '''模拟路由器的节点'''
    def config( self, **params ):
        super( LinuxRouter, self).config( **params )
        # 启动时，打开路由转发功能
        self.cmd( 'sysctl net.ipv4.ip_forward=1' )
 
    def terminate( self ):
        # 结束时，关闭路由转发功能
        self.cmd( 'sysctl net.ipv4.ip_forward=0' )
        super( LinuxRouter, self ).terminate()
 
class NetworkTopo( Topo ):
    '''网络拓扑，A LinuxRouter connecting three IP subnets'''
    def build( self, **_opts ):
        defaultIP1 = '10.0.3.10/24'  # IP address for r1-eth0
        defaultIP2 = '10.0.3.20/24'  # IP address for r2-eth0
        
        # 添加两个路由节点router1, router2, 并配置IP
        router1 = self.addNode( 'r1', cls=LinuxRouter, ip=defaultIP1 )
        router2 = self.addNode( 'r2', cls=LinuxRouter, ip=defaultIP2 )
 
        #添加两个主机节点h1, h2，并配置IP，缺省网关
        h1 = self.addHost( 'h1', ip='10.0.1.100/24', defaultRoute='via 10.0.1.10')
        h2 = self.addHost( 'h2', ip='10.0.2.100/24', defaultRoute='via 10.0.2.20')
 
        # 添加router1与router2之间的链路
        self.addLink(router1,router2,intfName1='r1-eth0',intfName2='r2-eth0')
        
        # 添加h1与router1之间的链路
        self.addLink(h1,router1,intfName2='r1-eth1',params2={ 'ip' : '10.0.1.10/24' })#params2 define the eth1 ip address
        # 添加h2与router2之间的链路
        self.addLink(h2,router2,intfName2='r2-eth1',params2={ 'ip' : '10.0.2.20/24' })
 
def run():
    '''Test linux router'''
    
    # 创建网络拓扑
    topo = NetworkTopo()
    # 启动mininet
    net = Mininet(controller = None, topo=topo )  # controller is not used
    net.start()
    info( '*** Routing Table on Router:\n' )
 
    r1=net.getNodeByName('r1')
    r2=net.getNodeByName('r2')
 
    info('starting zebra and ospfd service:\n')
    # 启动路由节点zebra，ospf进程
    r1.cmd('zebra -f /etc/quagga/r1zebra.conf -d -z /tmp/r1zebra.api -i /tmp/r1zebra.interface')
    r2.cmd('zebra -f /etc/quagga/r2zebra.conf -d -z /tmp/r2zebra.api -i /tmp/r2zebra.interface')
    time.sleep(1)#time for zebra to create api socket
    r1.cmd('ospfd -f /etc/quagga/r1ospfd.conf -d -z /tmp/r1zebra.api -i /tmp/r1ospfd.interface')
    r2.cmd('ospfd -f /etc/quagga/r2ospfd.conf -d -z /tmp/r2zebra.api -i /tmp/r2ospfd.interface')
 
    # 启动网络命令行
    CLI( net )
    net.stop()
 
    # 清理ospf, zebra进程，删除临时文件
    os.system("killall -9 ospfd zebra")
    os.system("rm -f /tmp/*.api")
    os.system("rm -f /tmp/*.interface")
 
if __name__ == '__main__':
    setLogLevel( 'info' )
    run()