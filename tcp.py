import asyncio, math, time
from tcputils import *
import random

class Servidor:
    def __init__(self, rede, porta):
        self.rede = rede            
        self.porta = porta          
        self.conexoes = {}          
        self.callback = None        
        self.rede.registrar_recebedor(self._rdt_rcv)    

    def registrar_monitor_de_conexoes_aceitas(self, callback):
        """
        Usado pela camada de aplicação para registrar uma função para ser chamada
        sempre que uma nova conexão for aceita
        """
        self.callback = callback
    
    # Função que trata o recebimento de mensagens
    def _rdt_rcv(self, src_addr, dst_addr, segment):        
        src_port, dst_port, seq_no, ack_no, \
            flags, window_size, checksum, urg_ptr = read_header(segment)           
        if dst_port != self.porta:                                                 
            # Ignora segmentos que não são destinados à porta do nosso servidor
            return
        if not self.rede.ignore_checksum and calc_checksum(segment, src_addr, dst_addr) != 0:   
            print('descartando segmento com checksum incorreto')
            return
        payload = segment[4*(flags>>12):]               
        id_conexao = (src_addr, src_port, dst_addr, dst_port)       
        if (flags & FLAGS_SYN) == FLAGS_SYN:                       
            conexao = self.conexoes[id_conexao] = Conexao(self, id_conexao, seq_no + 1)        
            if self.callback:                   
                self.callback(conexao)
            conexao.hand_shake()
        elif id_conexao in self.conexoes:                   
            if (flags & (FLAGS_ACK | FLAGS_FIN)) == FLAGS_ACK | FLAGS_FIN:      
                self.conexoes[id_conexao].recebe_fechar()
            else:
                self.conexoes[id_conexao]._rdt_rcv(seq_no, ack_no, flags, payload)
        else:                                                          
            print('%s:%d -> %s:%d (pacote associado a conexão desconhecida)' %
                  (src_addr, src_port, dst_addr, dst_port))
            
class Conexao:
    def __init__(self, servidor, id_conexao, ack_no):
        self.servidor = servidor
        self.id_conexao = id_conexao
        self.callback = None
        self.timer = None  
        self.seq_no = random.randint(0, 0xffff)          
        self.ack_no = ack_no
        self.esperando_ack_fin = False
        self.unsent_data = b''
        self.unacked_data = b''

        # Atributos relacionados ao timer de envio
        self.time_interval = 0.5       
        self.estimatedRTT = None
        self.devRTT = None
        self.t0 = None
        self.n_tentativa = 0           
        self.window_size = 1            
        self.increase_window_size = False
        self.next_seq_no = 0

    def _rdt_rcv(self, seq_no, ack_no, flags, payload):
        if seq_no == self.ack_no:       
            if len(payload) > 0:    
                self.ack_no += len(payload) 
                
                self.callback(self, payload)  

                self.send_ack()
            if len(self.unacked_data) > 0:
                self.recv_ack(ack_no)
                
    def hand_shake(self):
        src_addr, src_port, dst_addr, dst_port = self.id_conexao
        header = make_header(dst_port, src_port, self.seq_no, self.ack_no, FLAGS_SYN | FLAGS_ACK) 
        self.servidor.rede.enviar(fix_checksum(header, dst_addr, src_addr), src_addr)
        self.seq_no += 1

    # Função que envia a confirmação dos dados
    def send_ack(self):
        src_addr, src_port, dst_addr, dst_port = self.id_conexao
        header = make_header(dst_port, src_port, self.seq_no, self.ack_no, FLAGS_ACK) 
        self.servidor.rede.enviar(fix_checksum(header, dst_addr, src_addr), src_addr)       

    # Função que trata o recebimento de ACKs
    def recv_ack(self, ack_no):     
        if self.t0 != None:             
            self._calc_time_interval()         
        self._stop_timer()         
        if ack_no == self.next_seq_no:                 
            self.unacked_data = b''

            self.seq_no = self.next_seq_no
            if self.increase_window_size and self.n_tentativa == 0:
                self.window_size += 1              
                print(f'Aumentando window_size para {self.window_size}')
                self.increase_window_size = False              
            if len(self.unsent_data) > 0:      
                self.fazEnvio()
            self.n_tentativa = 0
        elif self.n_tentativa > 0:                                        
            self.unacked_data = self.unacked_data[MSS:]     
            self.seq_no += MSS
            if len(self.unacked_data) > 0:                  
                self.reenvia()      
            else:
                self.n_tentativa = 0                            

    def registrar_recebedor(self, callback):
        """
        Usado pela camada de aplicação para registrar uma função para ser chamada
        sempre que dados forem corretamente recebidos
        """
        self.callback = callback

    # Função que coloca os dados em buffer e chama a função que faz o envio de fato
    def enviar(self, dados):     
        self.unsent_data += dados          
        self.fazEnvio()                     

    # Função que pega os dados do buffer e envia
    def fazEnvio(self):
        src_addr, src_port, dst_addr, dst_port = self.id_conexao   
        self.increase_window_size = len(self.unsent_data[:self.window_size * MSS]) / MSS >= self.window_size     
        self.next_seq_no = self.seq_no
        for i in range(self.window_size):
            segmento = self.unsent_data[:MSS]                       
            if len(segmento) > 0:
                self.unsent_data = self.unsent_data[MSS:]                                    
                self.unacked_data += segmento
                header = make_header(dst_port, src_port, self.next_seq_no, self.ack_no, FLAGS_ACK)
                self.servidor.rede.enviar(fix_checksum(header + segmento, dst_addr, src_addr), src_addr)
                self.next_seq_no += len(segmento)
        self.t0 = time.time()                                    
        self._start_timer()

    def reenvia(self):
        self.t0 = None
        src_addr, src_port, dst_addr, dst_port = self.id_conexao    
        segmento = self.unacked_data[:MSS]
        header = make_header(dst_port, src_port, self.seq_no, self.ack_no, FLAGS_ACK)
        self.servidor.rede.enviar(fix_checksum(header + segmento, dst_addr, src_addr), src_addr)
        self._start_timer()

    '''Funções referentes ao timer'''
    # Inicia o timer e chama a função de envio
    def _start_timer(self):
        self._stop_timer()
        self.timer = asyncio.get_event_loop().call_later(self.time_interval, self._timer_timeout)

    # Para o timer
    def _stop_timer(self):
        if self.timer != None:
            self.timer.cancel()

    def _timer_timeout(self):
        self.n_tentativa += 1
        # Diminui o tamanho da janela de envio
        self.window_size = math.ceil(self.window_size /2)
        self.window_size = self.window_size if self.window_size != 0 else 1
        print(f'diminundo para {self.window_size}')
        
        self.reenvia()

    # Calcula o intervalo de tempo
    def _calc_time_interval(self):
        sampleRTT = time.time() - self.t0
        self.t0 = None
        self.is_reenvio = -1
        if self.estimatedRTT == None:       
            self.estimatedRTT = sampleRTT
            self.devRTT = sampleRTT / 2
        else:
            # Calculando o Estimated RTT
            alpha = 0.125
            self.estimatedRTT = (1 - alpha) * self.estimatedRTT + alpha * sampleRTT
            
            # Calculando o Deviation RTT
            beta = 0.25
            self.devRTT = (1 - beta) * self.devRTT + beta * abs(sampleRTT - self.estimatedRTT)

        # Calulando o Time Interval
        self.time_interval = self.estimatedRTT + 4 * self.devRTT
        print(f'ajustando time interval para {self.time_interval}s')

    def recebe_fechar(self):
        self.ack_no += 1               
        self.callback(self, b'')       
        self.send_ack()
        del self.servidor.conexoes[self.id_conexao]

    # Esta função envia um FIN e receber o ACK
    def fechar(self):
        src_addr, src_port, dst_addr, dst_port = self.id_conexao   
        if self.esperando_ack_fin:      
            del self.servidor.conexoes[self.id_conexao]
        else:                        
            header = make_header(dst_port, src_port, self.seq_no, self.ack_no, FLAGS_FIN)
            self.callback(self, b'')
            self.servidor.rede.enviar(fix_checksum(header, dst_addr, src_addr), src_addr)          
            self.esperando_ack_fin = True
            self.seq_no += 1