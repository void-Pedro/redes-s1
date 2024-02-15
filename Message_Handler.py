import re
from tcp import *

_nick_dict = {}  # tuplas conexao:nick
_canal_dict = {}  # tuplas canal:
# -----------------------------------------------------------------#

def Message_Handler(conexao, dados):
  # tirar espacos no comeco e no fim da msg
  dados = dados.strip()

  # switch dos tipos de dados
  if dados == b'':
    return sair(conexao)

  if dados[0:4].upper() == b'PING':
    alvo, response = PING_handler(conexao, dados)

  elif dados[0:4].upper() == b'NICK':
    alvo, response = NICK_handler(conexao, dados)

  elif dados[0:4].upper() == b'JOIN':
    alvo, response = JOIN_handler(conexao, dados)

  elif dados[0:7].upper() == b'PRIVMSG':
    alvo, response = PRIVMSG_handler(conexao, dados)

  elif dados[0:4].upper() == b'PART':
    alvo, response = PART_handler(conexao, dados)

  # retorna o erro ou sucesso da dados
  return alvo, response

# -----------------------------------------------------------------#

def PING_handler(conexao, dados):
  return conexao, b':server PONG server :' + dados.split(b' ', 1)[1] + b'\r\n'

# -----------------------------------------------------------------#

def NICK_handler(conexao, dados):
  # separar comando de conteudo e tirar espacos da mensagem
  comando, apelido = dados.split(b' ', 1)

  # vejo se essa conexao ja tem nick
  apelido_atual = _nick_dict.get(conexao)

  # se nao tiver marco como *
  if apelido_atual is None:
    apelido_atual = b'*'

  # caso se o nome nao eh valido da erro
  if not validar_nome(apelido):
    # envia msg de erro apelido invalido
    return conexao, b':server 432 ' + apelido_atual + b' ' + apelido + b' :Erroneous nickname\r\n'

  # caso se o nome q quer colocar ja ta em uso
  if apelido.lower() in _nick_dict.values():
    # msg de erro ja existe esse aplido
    return conexao, b':server 433 ' + apelido_atual + b' ' + apelido + b' :Nickname is already in use\r\n'

  # casos deu bom

  # deu bom e primeira vez
  if apelido_atual == b'*':
    # adiciona no dict
    _nick_dict[conexao] = apelido.lower()

    # envia msg
    return conexao, b':server 001 ' + apelido + b' :Welcome\r\n:server 422 ' + apelido + b' :MOTD File is missing\r\n'

  # deu bom e ta trocando de apelido
  if apelido_atual != b'*':
    _nick_dict[conexao] = apelido.lower()
    return conexao, b':' + apelido_atual + b' NICK ' + apelido + b'\r\n'

# -----------------------------------------------------------------#

def PRIVMSG_handler(conexao, mensagem):
  # Pegar o nick do sender
  sender = _nick_dict[conexao]
  # Pegar o nick do receiver (Na mensagem)
  mensagem = mensagem.split(maxsplit=2)
  receiver = mensagem[1]
  # (Passo 6) verificar se o receiver é um canal
  if (receiver.startswith(b'#')):
    return PRIVMSG_handler_canal(conexao, sender, receiver.lower(),
                                 mensagem[2].replace(b':', b''))
  # Comparar com o dicionário de nicks
  if not (receiver.lower() in _nick_dict.values()):
    return conexao, b''
  # Enviar mensagem
  targetPos = list(_nick_dict.values()).index(receiver.lower())
  answer = b':' + sender + b' PRIVMSG ' + receiver + b' ' + mensagem[2] + b'\r\n'
  return list(_nick_dict.keys())[targetPos], answer

# -----------------------------------------------------------------#

def PRIVMSG_handler_canal(conexao, sender, canal, conteudo):
  # montando mensagem
  canal = canal.replace(b'#', b'')
  mensagem = b':' + sender + b' PRIVMSG #' + canal + b' :' + conteudo + b'\r\n'

  # Enviar mensagem para todos do canal
  for conex in _canal_dict[canal]:
    if (conex != conexao):
      conex.enviar(mensagem)

  return conexao, b''

# -----------------------------------------------------------------#

def JOIN_handler(conexao, mensagem):
  # verificar validade do nome do canal
  canal = mensagem.split(b' ', 1)[1].replace(b'#', b'').lower()
  if not validar_nome(canal):
    return conexao, b':server 403 ' + mensagem + b' :No such channel\r\n'

  # se nao existe cria
  if _canal_dict.get(canal) is None:
    # cria o canal no dict
    _canal_dict[canal] = {}
    # cria a lista de nicks com essa conexao e adiciona o primeiro nick
    _canal_dict[canal][conexao] = _nick_dict[conexao]

  # se existe adiciona
  if _canal_dict.get(canal) is not None:
    # adiciona a conexao no dict
    _canal_dict[canal][conexao] = _nick_dict[conexao]
    # envia a msg de criacao do canal para todos do canal (menos o que entrou)
    for conex in _canal_dict[canal]:
      if (conex != conexao):
        print(conex, b':' + _nick_dict[conexao] + b' JOIN :#' + canal + b'\r\n')
        conex.enviar(b':' + _nick_dict[conexao] + b' JOIN :#' + canal + b'\r\n')

  # mensagem de join no canal para o recem chegado
  mensagemJoin = b':' + _nick_dict[conexao] + b' JOIN :#' + canal + b'\r\n'

  # mensagem de listar membros do canal para o recem chegado
  template = b':server 353 ' + _nick_dict[conexao] + b' = #' + canal + b' :'
  membros = b''
  membrosLista=[]

  for conexao in _canal_dict[canal]:
    membrosLista.append(_nick_dict[conexao])
  for mem in sorted(membrosLista):
    membros += mem + b' '

  mensagemMembros = template + membros + b'\r\n'
  mensagemFimMembros = b':server 366 ' + \
  _nick_dict[conexao]+b' #'+canal+b' :End of /NAMES list.\r\n'

  mensagem = mensagemJoin + mensagemMembros + mensagemFimMembros

  # enviar mensagens para recem chegado
  return conexao, mensagem

# -----------------------------------------------------------------#

# -----------------------------------------------------------------#

def PART_handler(conexao, dados):
  # pegar o nome do canal
  canal = dados.split(b' ', 2)[1].replace(b'#', b'').lower()
  # enviar mensagem de saida do canal para todos do canal
  for conex in _canal_dict[canal]:
    conex.enviar(b':' + _nick_dict[conexao] + b' PART #' + canal + b'\r\n')

  # remover a conexao do canal
  _canal_dict[canal].pop(conexao)

  return conexao, b''

# -----------------------------------------------------------------#


def validar_nome(nome):
  return re.match(br'^[a-zA-Z][a-zA-Z0-9_-]*$', nome) is not None

# -----------------------------------------------------------------#

def sair(conexao):
  print(conexao, 'conexão fechada')
  conexao.fechar()

# -----------------------------------------------------------------#