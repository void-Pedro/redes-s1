from grader.iputils import *


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
            # TODO: Trate corretamente o campo TTL do datagrama
            dscp, ecn, identification, flags, frag_offset, ttl, proto, \
                src_addr, dst_addr, payload = read_ipv4_header(datagrama)
            
            if ttl == 1:
                self.icmp_time_limit_exceed(datagrama, src_addr)
                return
            else:
                ttl -= 1

            # Refazendo cabeçalho com ttl decrementado
            hdr = struct.pack('!BBHHHBBH', 0x45, dscp|ecn, 20+len(payload), identification, \
                (flags<<13)|frag_offset, ttl, proto, 0) + str2addr(src_addr) + str2addr(dst_addr)

            # Corrigindo checksum
            checksum = calc_checksum(hdr)

            hdr = struct.pack('!BBHHHBBH', 0x45, dscp|ecn, 20+len(payload), identification, \
                (flags<<13)|frag_offset, ttl, proto, checksum) + str2addr(src_addr) + str2addr(dst_addr)

            datagrama = hdr + payload

            self.enlace.enviar(datagrama, next_hop)


    def icmp_time_limit_exceed(self, datagrama, src_addr):
        payload = struct.pack('!BBHI', 11, 0, 0, 0) + datagrama[:28]
        checksum = calc_checksum(payload)
        payload = struct.pack('!BBHI', 11, 0, checksum, 0) + datagrama[:28]

        self.enviar(payload, src_addr, IPPROTO_ICMP)

    def addr2bitstring(self,addr):
        arr = list(int(x) for x in addr.split('.'))
        string = ""

        for element in arr:
            string += '{0:08b}'.format(element)

        return string

    def _next_hop(self, dest_addr):
        # TODO: Use a tabela de encaminhamento para determinar o próximo salto
        # (next_hop) a partir do endereço de destino do datagrama (dest_addr).
        # Retorne o next_hop para o dest_addr fornecido.
        prev_matched = {'bits': -1, 'next_hop':None}
        
        for cidr, next_hop in self.tabela:
            no_matching_bits = self._addr_match(cidr, dest_addr)

            if no_matching_bits > prev_matched['bits']:
                prev_matched['bits'] = no_matching_bits
                prev_matched['next_hop'] = next_hop
            
        return prev_matched['next_hop']
    
    def _addr_match(self, cidr, addr):
        cidr_base, no_matching_bits = cidr.split("/", 1)

        no_matching_bits = int(no_matching_bits)
        cidr_base = self.addr2bitstring(cidr_base)
        addr = self.addr2bitstring(addr)
        if (cidr_base[:no_matching_bits] == addr[:no_matching_bits]):
            return no_matching_bits
        else:
            return -1
        
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

    def enviar(self, segmento, dest_addr, proto = IPPROTO_TCP):
        """
        Envia segmento para dest_addr, onde dest_addr é um endereço IPv4
        (string no formato x.y.z.w).
        """
        next_hop = self._next_hop(dest_addr)
        # TODO: Assumindo que a camada superior é o protocolo TCP, monte o
        # datagrama com o cabeçalho IP, contendo como payload o segmento.
        vihl = (4 << 4) | 5
        dscpecn = 0 | 0
        total_len = 20 + len(segmento)
        identification = 0
        flagsfrag = (0 << 13) | 0
        ttl = 64
        
        hdr = struct.pack('!BBHHHBBH', vihl, dscpecn, total_len, identification,
                          flagsfrag, ttl, proto, 0) + str2addr(self.meu_endereco) + str2addr(dest_addr)
        
        checksum = calc_checksum(hdr)
        hdr = struct.pack('!BBHHHBBH', vihl, dscpecn, total_len, identification, \
             flagsfrag, ttl, proto, checksum) + str2addr(self.meu_endereco) + str2addr(dest_addr)
        datagrama = hdr + segmento

        self.enlace.enviar(datagrama, next_hop)
