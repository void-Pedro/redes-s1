#!/usr/bin/env python3
import asyncio
from tcp import Servidor
import re

dados_residuais= b''
apelidos_em_uso = {}
lista_de_canais = {}

def validar_nome(nome):
    return re.match(br'^[a-zA-Z][a-zA-Z0-9_-]*$', nome) is not None


def sair(conexao):
    global apelidos_em_uso
    global lista_de_canais

    print(conexao, 'conexão fechada')

    for _canal, _lista_de_usuarios in lista_de_canais.items():
        if conexao in _lista_de_usuarios:
            for c in _lista_de_usuarios:
                c.enviar(b':'+apelidos_em_uso[conexao]+b' QUIT :Connection closed\n')
            lista_de_canais[_canal].remove(conexao)
	
    if conexao in apelidos_em_uso.keys():
    	apelidos_em_uso.pop(conexao)

    conexao.fechar()


def dados_recebidos(conexao, dados):
    global dados_residuais
    global apelidos_em_uso
    global lista_de_canais

    dados = dados_residuais + dados
    if dados == b'':
        return sair(conexao)

    dados_separados = dados.split(b'\n')

    if dados.endswith(b'\n'):
        dados_residuais = b''
    else:
        dados_residuais = dados_separados[len(dados_separados)-1]

    for i in range(len(dados_separados)-1):
        # PING
        if dados_separados[i].startswith(b'PING'):
            conexao.enviar(b':server PONG server :' + dados_separados[i].split(b' ', 1)[1] + b'\n')

        # NICK
        if dados_separados[i].startswith(b'NICK'):
            apelido_novo = dados_separados[i].split(b' ', 1)[1]
            apelido_novo = apelido_novo.split(b'\r')[0]
            apelido_atual = b'*'

            if validar_nome(apelido_novo):
                if conexao not in apelidos_em_uso.keys(): # Se a conexão ainda não criou um apelido
                    if apelido_novo.lower() not in [apld.lower() for apld in apelidos_em_uso.values()]: # Novo apelido
                        apelidos_em_uso[conexao] = apelido_novo
                        conexao.enviar(b':server 001 ' + apelido_novo + b' :Welcome\r\n')
                        conexao.enviar(b':server 422 ' + apelido_novo + b' :MOTD File is missing\r\n')
                    else: # Apelido em uso
                        conexao.enviar(b':server 433 ' + apelido_atual + b' ' + apelido_novo + b' :Nickname is already in use\r\n')
                else: # Se a conexão já criou um apelido
                    apelido_atual = apelidos_em_uso[conexao]
                    if apelido_novo.lower() not in [apld.lower() for apld in apelidos_em_uso.values()]: # Troca de apelidos
                        conexao.enviar(b':' + apelidos_em_uso[conexao] + b' NICK ' + apelido_novo+b'\r\n')
                        apelidos_em_uso[conexao] = apelido_novo
                    else: # Apelido em uso
                        conexao.enviar(b':server 433 ' + apelido_atual + b' ' + apelido_novo + b' :Nickname is already in use\r\n')
            else: # Apelido inválido
                if conexao in apelidos_em_uso.keys():
                    apelido_atual = apelidos_em_uso[conexao]

                conexao.enviar(b':server 432 ' + apelido_atual + b' ' + apelido_novo + b' :Erroneous nickname\r\n')

        # PRIVMSG
        if dados_separados[i].startswith(b'PRIVMSG'):
            remetente = apelidos_em_uso[conexao]
            destinatario = dados_separados[i].split(b' ')[1]
            mensagem = dados_separados[i].split(b':')[1]

            if destinatario.startswith(b'#'):
                # Para canais
                canal = destinatario[1:]
                for _canal, _lista_de_conexoes in lista_de_canais.items():
                    if canal.lower() == _canal.lower():
                        for usuario in _lista_de_conexoes:
                            if usuario != conexao:
                                usuario.enviar(b':' + apelidos_em_uso[conexao] + b' PRIVMSG #' + _canal + b' :' + mensagem + b'\n')
                        break
            else:
                # Para usuários
                for _conexao, _apelido in apelidos_em_uso.items():
                    if destinatario.lower() == _apelido.lower():
                        _conexao.enviar(b':' + apelidos_em_uso[conexao] + b' PRIVMSG ' + _apelido + b' :' + mensagem+ b'\n')

        # JOIN
        if dados_separados[i].startswith(b'JOIN'):
            canal = dados_separados[i].split(b'#')[1]
            canal = canal[:len(canal)-1]
            if validar_nome(canal):
                lista_de_canais.setdefault(canal, [])
                lista_de_canais[canal].append(conexao)

                # Avisa a todos do canal que a pessoa entrou
                for _canal, _lista_de_conexoes in lista_de_canais.items():
                    if canal.lower() == _canal.lower():
                        for usuario in _lista_de_conexoes:
                            usuario.enviar(b':'+apelidos_em_uso[conexao]+b' JOIN :#'+canal+b'\r\n')
                        break

                # Mostra lista de canais
                conexoes_no_canal = lista_de_canais[canal]
                apelidos_no_canal = []
                for c in conexoes_no_canal:
                    apelidos_no_canal.append(apelidos_em_uso[c])
                apelidos_no_canal.sort()
                mensagem_lista = b':server 353 ' + apelidos_em_uso[conexao] + b' = #' + canal + b' :'
                for apelido in apelidos_no_canal:
                    if len(mensagem_lista + apelido + b'\n') <=512:
                        mensagem_lista = mensagem_lista + apelido + b' '
                    else:
                        mensagem_lista = mensagem_lista + b'\n'
                        conexao.enviar(mensagem_lista)
                        mensagem_lista = b':server 353 ' + apelidos_em_uso[conexao] + b' = #' + canal + b' :' + apelido + b' '
                mensagem_lista = mensagem_lista + b'\n'
                conexao.enviar(mensagem_lista)
                conexao.enviar(b':server 366 ' + apelidos_em_uso[conexao] + b' #' + canal + b' :End of /NAMES list.\r\n')
                #print(b':server 366 ' + apelidos_em_uso[conexao] + b' #' + canal + b' :End of /NAMES list.\r\n')
		
            else:
                conexao.enviar(b':server 403 '+canal+b' :No such channel\n')

        # PART
        if dados_separados[i].startswith(b'PART'):
            canal = dados_separados[i].split(b'#')[1]
            canal = canal[:len(canal)-1]
            canal = canal.split(b' ')[0]
            # Avisa a todos do canal que a pessoa saiu
            if validar_nome(canal):
                for _canal, _lista_de_conexoes in lista_de_canais.items():
                    if canal.lower() == _canal.lower():
                        for usuario in _lista_de_conexoes:
                            usuario.enviar(b':'+apelidos_em_uso[conexao]+b' PART #'+canal+b'\r\n')
                        break
                lista_de_canais[canal].remove(conexao)
            else:
                conexao.enviar(b':server 403 ' + canal + b' :No such channel\r\n')

    print(conexao, dados)


def conexao_aceita(conexao):
    print(conexao, 'nova conexão')
    conexao.registrar_recebedor(dados_recebidos)

servidor = Servidor(6667)
servidor.registrar_monitor_de_conexoes_aceitas(conexao_aceita)
asyncio.get_event_loop().run_forever()
