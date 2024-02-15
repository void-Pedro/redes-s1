from iputils import *
import ipaddress
import struct
import socket
count = 0

def ipParaInt(addr):
    return struct.unpack("!I", socket.inet_aton(addr))[0]

class IP:
    def __init__(self, enlace):
        """
        Inicia a camada de rede. Recebe como argumento uma implementação
        de camada de enlace capaz de localizar os next_hop (por exemplo,
        Ethernet com ARP).
        """
        self.callback = None
        self.enlace = enlace
        self.enlace.registrar_recebedor(self.__raw_recv)
        self.ignore_checksum = self.enlace.ignore_checksum
        self.meu_endereco = None
        self.tabela = []

    def __raw_recv(self, datagrama):
        dscp, ecn, identification, flags, frag_offset, ttl, proto, \
           src_addr, dst_addr, payload = read_ipv4_header(datagrama)
        if dst_addr == self.meu_endereco:
            # atua como host
            if proto == IPPROTO_TCP and self.callback:
                self.callback(src_addr, dst_addr, payload)
        else:
            # atua como roteador
            next_hop = self._next_hop(dst_addr)
            ttl -= 1
            if ttl> 0:
                datagrama= struct.pack('!BBHHHBBHII',69,dscp|ecn,20,identification,flags|frag_offset,ttl,proto,0,int(ipaddress.ip_address(src_addr)),int(ipaddress.ip_address(dst_addr)))
                aux = calc_checksum(datagrama)    
                datagrama= struct.pack('!BBHHHBBHII',69,dscp|ecn,20,identification,flags|frag_offset,ttl,proto,aux,int(ipaddress.ip_address(src_addr)),int(ipaddress.ip_address(dst_addr)))
                # TODO: Trate corretamente o campo TTL do datagrama
                self.enlace.enviar(datagrama, next_hop)
            else:
                nova_next_hop = self._next_hop(src_addr)
                datagramaErrado= struct.pack('!BBHHHBBHII',69,dscp|ecn,48,identification,flags|frag_offset,64,1,0,int(ipaddress.ip_address(self.meu_endereco)),int(ipaddress.ip_address(src_addr)))
                aux = calc_checksum(datagramaErrado)    
                datagramaErrado= struct.pack('!BBHHHBBHII',69,dscp|ecn,48,identification,flags|frag_offset,64,1,aux,int(ipaddress.ip_address(self.meu_endereco)),int(ipaddress.ip_address(src_addr)))
                icmp = struct.pack('!BBHHH', 11, 0, 0, 0, 0)
                aux2 = calc_checksum(icmp + datagramaErrado)
                icmp = struct.pack('!BBHHH', 11, 0, aux2, 0, 0)
                mensagemFormada = datagramaErrado + icmp + datagrama[:28]
                self.enlace.enviar(mensagemFormada,nova_next_hop)
                return None

    def _next_hop(self, dest_addr):
        # TODO: Use a tabela de encaminhamento para determinar o próximo salto
        # (next_hop) a partir do endereço de destino do datagrama (dest_addr).
        # Retorne o next_hop para o dest_addr fornecido.
        array = []
        for i in range(len(self.tabela)):
            if ipaddress.ip_address(dest_addr) in (ipaddress.ip_network(self.tabela[i][0])):
                array.append(i)
        if (len(array)==1):                           
            return self.tabela[array[0]][1]
        elif(len(array)>1):
            final = (ipaddress.ip_network(self.tabela[array[0]][0])).prefixlen
            ret = 0
            for i in range(len(array)):
                aux = (ipaddress.ip_network(self.tabela[array[i]][0])).prefixlen
                if aux > final:
                    final = aux
                    ret = i
            return self.tabela[array[ret]][1]
        else:
            return None

    def definir_endereco_host(self, meu_endereco):
        """
        Define qual o endereço IPv4 (string no formato x.y.z.w) deste host.
        Se recebermos datagramas destinados a outros endereços em vez desse,
        atuaremos como roteador em vez de atuar como host.
        """
        self.meu_endereco = meu_endereco

    def definir_tabela_encaminhamento(self, tabela):
        """
        Define a tabela de encaminhamento no formato
        [(cidr0, next_hop0), (cidr1, next_hop1), ...]

        Onde os CIDR são fornecidos no formato 'x.y.z.w/n', e os
        next_hop são fornecidos no formato 'x.y.z.w'.
        """
        # TODO: Guarde a tabela de encaminhamento. Se julgar conveniente,
        # converta-a em uma estrutura de dados mais eficiente.
        self.tabela = tabela

    def registrar_recebedor(self, callback):
        """
        Registra uma função para ser chamada quando dados vierem da camada de rede
        """
        self.callback = callback

    def enviar(self, segmento, dest_addr):
        """
        Envia segmento para dest_addr, onde dest_addr é um endereço IPv4
        (string no formato x.y.z.w).
        """
        global count
        next_hop = self._next_hop(dest_addr)
        count += 1
        datagrama= struct.pack('!BBHHHBBHII',69,0,20+len(segmento),count,0,64,6,0,int(ipaddress.ip_address(self.meu_endereco)),int(ipaddress.ip_address(dest_addr)))
        aux=calc_checksum(datagrama)
        datagrama= struct.pack('!BBHHHBBHII',69,0,20+len(segmento),count,0,64,6,aux,int(ipaddress.ip_address(self.meu_endereco)) ,int(ipaddress.ip_address(dest_addr)))
        datagrama = datagrama + segmento
        # TODO: Assumindo que a camada superior é o protocolo TCP, monte o
        # datagrama com o cabeçalho IP, contendo como payload o segmento.
        self.enlace.enviar(datagrama, next_hop)