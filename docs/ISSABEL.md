# Preparação do Issabel/Asterisk

## 1. Extensão WebRTC

Cria uma extensão **PJSIP** própria para o Home Assistant, por exemplo `2003`. Não uses a conta administrativa do Issabel. Nas opções avançadas, confirma os equivalentes a:

- Transporte: WSS.
- WebRTC: ativo.
- AVPF: ativo.
- ICE: ativo.
- Media encryption: DTLS-SRTP.
- DTLS setup: `actpass`.
- RTCP mux: ativo.
- Use received transport: ativo.
- Direct media: desativo.
- Force rport, rewrite contact e RTP symmetric: ativos, sobretudo se existir NAT.
- Codecs: Opus, G.711 μ-law (`ulaw`) e, se necessário, A-law (`alaw`).

O Issabel/FreePBX gera vários ficheiros Asterisk. Não substituas cegamente `pjsip.conf`, `http.conf` ou os ficheiros `*_additional.conf`; usa a interface e os ficheiros `*_custom.conf` previstos pela instalação.

## 2. WSS e certificado

O cartão precisa de um endereço como:

```text
wss://pbx.exemplo.local:8089/ws
```

O exemplo antigo usa `8090`; mantém essa porta apenas se o teu Asterisk estiver realmente configurado nela. O valor habitual na documentação Asterisk é `8089`.

No CLI:

```text
http show status
pjsip show transports
module show like websocket
```

Deve aparecer o servidor HTTPS, o URI `/ws` e um transporte WSS. Um painel Home Assistant servido por HTTPS normalmente não pode usar `ws://`; usa `wss://` com certificado aceite pelo dispositivo.

## 3. AMI para estados

O áudio não passa pelo AMI. O AMI serve apenas para o Home Assistant conhecer registos, estados, linhas ligadas e executar ações expressamente autorizadas.

Cria um utilizador dedicado em `manager_custom.conf` ou no mecanismo equivalente do Issabel, restringido ao IP do Home Assistant. Depois instala a integração [Asterisk para Home Assistant](https://github.com/TECH7Fox/asterisk-hass-integration) e aponta-a para TCP 5038.

Para apenas monitorizar, remove permissões de escrita. Se precisares de `Originate`, adiciona somente `originate,call`; evita `write=all`.

## 4. HT503 e chan_dongle

- A porta FXS do HT503 deve estar registada como uma extensão do Issabel.
- A porta FXO deve ser tratada como trunk/rota, conforme a tua configuração existente.
- `chan_dongle` continua a ser um trunk GSM; as regras de saída escolhem-no pelo prefixo ou padrão definido no Issabel.
- No cartão, marcas a extensão ou o número final. Não coloques a credencial do HT503 nem do dongle no YAML do cartão.

## 5. Teste por etapas

1. Confirma que a extensão WebRTC aparece em `pjsip show endpoint NUMERO`.
2. Abre o painel e autoriza o microfone.
3. Confirma `SIP registado` no topo do cartão.
4. Liga para outra extensão interna.
5. Testa áudio nos dois sentidos.
6. Durante a chamada, testa DTMF.
7. Só depois testa rotas externas pelo HT503 ou `chan_dongle`.

Se regista e chama mas não há áudio, verifica RTP/NAT, ICE, DTLS, codecs e firewall. Se nem regista, começa pelo certificado WSS, porta, URI `/ws`, AOR, utilizador de autenticação e palavra-passe.

