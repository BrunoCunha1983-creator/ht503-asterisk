# Asterisk Console BC para Home Assistant

Softphone WebRTC e consola de estado para Asterisk/Issabel dentro de um painel do Home Assistant.

[![Adicionar ao HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=BrunoCunha1983-creator&repository=ht503-asterisk&category=integration)

Esta edição parte do projeto MIT [SIP Core](https://github.com/TECH7Fox/sipcore-hass-integration), de Jordy Kuhne/TECH7Fox, e acrescenta o cartão `custom:asterisk-console-card`, compatibilidade direta com a configuração antiga `custom:sipjs-client-card`, interface em português e proteção adicional das credenciais SIP.

## O que inclui

- Fazer, receber, atender e desligar chamadas no navegador ou na app do Home Assistant.
- Microfone, silêncio e teclado DTMF durante a chamada.
- Campo para marcar extensões, números externos, códigos `*`/`#` e atalhos.
- Descoberta automática de extensões e respetivos estados através da integração Asterisk do Home Assistant.
- Estado separado do cliente SIP/WebRTC e da ligação AMI.
- Estado Livre, Em chamada, Ocupado, Indisponível, A tocar e Em espera.
- Linha remota ligada a cada extensão, quando fornecida pela integração Asterisk.
- Ações opcionais de serviços do Home Assistant, com confirmação configurável.
- Compatibilidade com Asterisk 18/Issabel, PJSIP WebRTC, HT503 e trunks como `chan_dongle` através do dialplan.
- Mantém também os cartões originais `sip-call-card`, `sip-contacts-card` e `sip-call-button`.

## Instalação fácil pelo HACS

1. Carrega no botão **Adicionar ao HACS** acima.
2. Se o HACS pedir confirmação, adiciona o repositório como categoria **Integração**.
3. Instala **Asterisk Console BC**.
4. Reinicia o Home Assistant.
5. Vai a **Definições → Dispositivos e serviços → Adicionar integração**.
6. Procura **Asterisk Console BC (SIP Core)** e adiciona-a.
7. Cria um cartão manual no painel com `type: custom:asterisk-console-card`.

Também podes adicionar manualmente este repositório personalizado no HACS:

```text
https://github.com/BrunoCunha1983-creator/ht503-asterisk
```

Seleciona a categoria **Integração**.

## Instalação manual por ficheiros

1. Descarrega ou clona o repositório.
2. Copia a pasta `sip_core` para `/config/custom_components/sip_core` no Home Assistant.
3. Reinicia o Home Assistant.
4. Vai a **Definições → Dispositivos e serviços → Adicionar integração**.
5. Procura **Asterisk Console BC (SIP Core)** e adiciona-a.
6. Abre as opções da integração para configurar o servidor e as contas, ou usa o bloco compatível abaixo.

O ficheiro JavaScript é servido e registado automaticamente pela integração. Não é necessário adicionar manualmente um recurso Lovelace.

## Migração direta do cartão antigo

O formato apresentado no exemplo antigo continua válido. Basta mudar o tipo do cartão:

```yaml
type: custom:asterisk-console-card
title: Asterisk / Issabel
server: PBX_IP_OU_NOME:8090
ringtone: /local/ringtone.mp3
client: "1"
clients:
  "1":
    aor: sip:2003@192.168.0.174
    username: "2003"
    password: "ALTERAR_PALAVRA_PASSE"
```

Substitui os valores pelos dados reais do teu Asterisk. Podes indicar apenas `IP:porta`; o cartão acrescenta automaticamente `wss://` e `/ws`. Também aceita um URL completo como `wss://pbx.exemplo.pt:8089/ws`. Com um único elemento em `clients`, a linha `client:` pode ser omitida.

> **Atenção:** neste modo, a palavra-passe fica guardada na configuração do painel. O modo seguinte é recomendado para uma instalação permanente.

## Modo recomendado, sem palavra-passe no cartão

Configura a conta nas opções da integração SIP Core e usa no painel apenas:

```yaml
type: custom:asterisk-console-card
title: Telefones da casa
auto_discover: true
show_keypad: true
show_server_status: true
```

Exemplo do objeto nas opções da integração:

```yaml
pbx_server: 192.168.0.174
custom_wss_url: wss://192.168.0.174:8090/ws
ice_config:
  iceGatheringTimeout: 5000
  iceCandidatePoolSize: 0
  iceTransportPolicy: all
  iceServers:
    - urls:
        - stun:stun.l.google.com:19302
  rtcpMuxPolicy: require
incomingRingtoneUrl: /sip_core_files/ring-tone.mp3
outgoingRingtoneUrl: /sip_core_files/ringback-tone.mp3
allow_backup_user: false
backup_user:
  ha_username: desativado
  extension: "0000"
  password: ALTERAR
users:
  - ha_username: ID_OU_NOME_DO_UTILIZADOR_HA
    display_name: Bruno
    extension: "2003"
    password: PALAVRA_PASSE_FORTE_DA_EXTENSAO
sip_video: false
auto_answer: false
popup_override_component: null
popup_config:
  auto_open: true
  large: false
  hide_header_button: false
  buttons: []
  extensions: {}
```

Com `allow_backup_user: false`, um utilizador do Home Assistant sem conta SIP atribuída não recebe uma credencial de reserva. A API entrega ao navegador somente a conta correspondente ao utilizador autenticado; não entrega as palavras-passe dos restantes utilizadores.

## Extensões, HT503 e atalhos

Quando a [integração Asterisk](https://github.com/TECH7Fox/asterisk-hass-integration) está instalada e ligada ao AMI, o cartão tenta descobrir automaticamente entidades com nomes como `2003 Registered`, `2003 State` e `2003 Connected Line`.

Também podes fixar nomes e entidades:

```yaml
type: custom:asterisk-console-card
title: Central telefónica
ami_entity: binary_sensor.ami_connected
auto_discover: true
endpoints:
  "2003":
    name: Home Assistant
    icon: mdi:home-assistant
    registered_entity: binary_sensor.2003_registered
    state_entity: sensor.2003_state
    connected_entity: sensor.2003_connected_line
  "201":
    name: Telefone analógico HT503
    icon: mdi:phone-classic
  "299":
    name: Porta FXO do HT503
    icon: mdi:phone-incoming-outgoing
quick_numbers:
  - name: Telemóvel
    number: "NUMERO_REAL"
    icon: mdi:cellphone
  - name: Correio de voz
    number: "*97"
    icon: mdi:voicemail
```

O HT503 e o modem `chan_dongle` não são controlados diretamente pelo JavaScript. O cartão chama uma extensão/número; o dialplan e as rotas de saída do Issabel decidem se a chamada segue pela FXS/FXO, pelo dongle GSM ou por outro trunk.

## Ações opcionais

As ações usam serviços normais do Home Assistant. Nada administrativo é ativado por defeito:

```yaml
actions:
  - name: Reiniciar HT503
    icon: mdi:restart
    domain: script
    service: turn_on
    service_data:
      entity_id: script.reiniciar_ht503
    confirmation: Reiniciar o HT503 agora?
```

## Requisitos do Asterisk

- PJSIP com transporte WSS.
- Módulos `res_http_websocket` e `res_pjsip_transport_websocket`.
- Endpoint WebRTC com `webrtc=yes`, ICE e DTLS-SRTP.
- HTTPS no Home Assistant para o navegador autorizar o microfone.
- Certificado confiável no endereço WSS; certificados autoassinados podem ser bloqueados silenciosamente pelo navegador.
- Porta WSS acessível entre o dispositivo que mostra o painel e o Asterisk.
- Para estados de extensões: integração Asterisk do Home Assistant e utilizador AMI restrito ao IP do Home Assistant.

Os exemplos para Asterisk autónomo e as notas específicas do Issabel estão em `examples/` e `docs/ISSABEL.md`.

## Diagnóstico rápido

No CLI do Asterisk:

```text
http show status
pjsip show transports
pjsip show endpoint 2003
pjsip show contacts
module show like websocket
```

No navegador, abre as ferramentas de programador e procura mensagens `SIP-CORE`. Se WSS usar certificado autoassinado, visita uma vez `https://ENDERECO_DO_ASTERISK:PORTA/ws` e verifica se o navegador permite confiar no certificado.

## Segurança

- Nunca publiques um YAML ou captura de ecrã contendo `password:`.
- Não exponhas AMI/TCP 5038 diretamente à Internet.
- Restringe o AMI ao IP do Home Assistant com `permit`/`deny`.
- Usa uma extensão WebRTC própria e uma palavra-passe longa; não reutilizes a palavra-passe do painel Issabel.
- Usa VPN/Tailscale ou proxy TLS corretamente configurado para acesso remoto.
- O cartão não utiliza AJAM e não envia a credencial AMI ao navegador.

## Créditos e licença

Código original: [TECH7Fox/sipcore-hass-integration](https://github.com/TECH7Fox/sipcore-hass-integration). Licença MIT preservada no ficheiro `LICENSE`.

Os ficheiros históricos `etc/asterisk/` e `ht-503-grandstream.md` já existentes neste repositório vêm do projeto [grahammiln/ht503-asterisk](https://github.com/grahammiln/ht503-asterisk) e foram mantidos intactos.
