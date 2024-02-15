class CamadaEnlace:
    ignore_checksum = False

    def __init__(self, linhas_seriais):
        """
        Inicia uma camada de enlace com um ou mais enlaces, cada um conectado
        a uma linha serial distinta. O argumento linhas_seriais é um dicionário
        no formato {ip_outra_ponta: linha_serial}. O ip_outra_ponta é o IP do
        host ou roteador que se encontra na outra ponta do enlace, escrito como
        uma string no formato 'x.y.z.w'. A linha_serial é um objeto da classe
        PTY (vide camadafisica.py) ou de outra classe que implemente os métodos
        registrar_recebedor e enviar.
        """
        self.enlaces = {}
        self.callback = None
        # Constrói um Enlace para cada linha serial
        for ip_outra_ponta, linha_serial in linhas_seriais.items():
            enlace = Enlace(linha_serial)
            self.enlaces[ip_outra_ponta] = enlace
            enlace.registrar_recebedor(self._callback)

    def registrar_recebedor(self, callback):
        """
        Registra uma função para ser chamada quando dados vierem da camada de enlace
        """
        self.callback = callback

    def enviar(self, datagrama, next_hop):
        """
        Envia datagrama para next_hop, onde next_hop é um endereço IPv4
        fornecido como string (no formato x.y.z.w). A camada de enlace se
        responsabilizará por encontrar em qual enlace se encontra o next_hop.
        """
        # Encontra o Enlace capaz de alcançar next_hop e envia por ele
        self.enlaces[next_hop].enviar(datagrama)

    def _callback(self, datagrama):
        if self.callback:
            self.callback(datagrama)


class Enlace:
    def __init__(self, linha_serial):
        self.linha_serial = linha_serial
        self.linha_serial.registrar_recebedor(self.__raw_recv)
        self.dados_residuais = b""

    def registrar_recebedor(self, callback):
        self.callback = callback

    def enviar(self, datagrama):
        aux = datagrama
        datagrama = b''

        for byte in list(aux):
            if byte == 0xc0:
                datagrama = datagrama + b'\xdb\xdc'
            elif byte == 0xdb:
                datagrama = datagrama + b'\xdb\xdd'
            else:
                datagrama = datagrama + bytes([byte])

        datagrama =b'\xc0' + datagrama + b'\xc0'
        self.linha_serial.enviar(datagrama)
        # TODO: Preencha aqui com o código para enviar o datagrama pela linha
        # serial, fazendo corretamente a delimitação de quadros e o escape de
        # sequências especiais, de acordo com o protocolo CamadaEnlace (RFC 1055).
        pass

    def __raw_recv(self, dados):
        dados = self.dados_residuais + dados   # Concatenando dados residuais ao dados recebidos da camada física
        self.dados_residuais = b''              # Resetando dados residuais

        if dados[-1] != b'\xc0':
            datagramas = dados.split(b'\xc0')
            self.dados_residuais = datagramas.pop()     # colocando dados de um datragrama incompleto no vetor de dados residuais
        else:
            datagramas = dados.split(b'\xc0')

        # Tratando sequências de escape

        for datagrama in datagramas:
            datagrama = datagrama.replace(b'\xdb\xdd', b'\xdb')
            datagrama = datagrama.replace(b'\xdb\xdc', b'\xc0')

            if datagrama != b'':
                try:
                    self.callback(datagrama)
                except:
                    pass
                finally:
                    dados = b''


    def __raw_recv_old(self, dados):
        if self.dados_residuais != b'':
            dados = self.dados_residuais + dados
            self.dados_residuais = b''

        if dados[:1] == b'\xc0':        # Caso tenha um pacote inteiro
            dados = dados[1:]

        if b'\xc0' not in dados:
            self.dados_residuais = dados

        while dados != b'':
            if dados[:1] == b'\xc0':
                dados = dados[1:]
            if b'\xc0' not in dados:
                self.dados_residuais = dados
                return
            if b'\xdb' in dados:
                for i in range(len(dados)):
                    # 219 se refere a b'xdb'
                    if dados[i] == 219:
                        # 220 se refere a b'xdc'
                        if dados[i + 1] == 220:
                            dados = dados[:i] + b'\xc0' + dados[i+2:]
                            if dados[-1:] == b'\xc0':
                                self.callback(dados[:-1])
                                dados = b''
                                self.dados_residuais = b''

                            break
                        # 221 se refere a b'xdd'
                        if dados[i+1] == 221:
                            dados = dados[:i + 1] + dados[i+2:]
                            break
            if dados[-1:] == b'\xc0' and b'\xc0' not in dados[:-1]:
                self.callback(dados[:-1])
                dados = b''
                self.dados_residuais = b''
            else:
                for i in range(len(dados)):
                    # 192 se refere a \xc0
                    if dados[i] == 192:
                        break
                if dados[:i] != b'':
                    self.callback(dados[:i])
                    dados = dados[i+1:]