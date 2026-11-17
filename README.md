# Monitoramento ambiental com ESP32

Protótipo de IoT que mede **temperatura**, **umidade** e **luminosidade** com um ESP32 e envia cada leitura por Wi-Fi, em JSON (HTTP POST), para um servidor em Python. O servidor grava o histórico no **MongoDB** e mostra os dados em um **dashboard web** atualizado em tempo real.

- Vídeo demonstrativo: [https://youtu.be/lDfZbuiANzo?is=lZVIlx5v4KdXY-su]

## Como funciona

```
DHT11 + módulo LDR  ->  ESP32  --Wi-Fi / HTTP POST (JSON)-->  API Flask  ->  MongoDB
                                                                  |
                                                         dashboard web (navegador)
```

A cada 10 segundos o ESP32 lê os sensores e envia:

```json
{"dispositivo":"esp32-01","temperatura":24.1,"umidade":44,"luminosidade":"claro"}
```

O servidor responde `201 Created` quando a leitura é gravada no banco.

## Estrutura do repositório

```
esp32_dht11_ldr_http2/
├── esp32_dht11_ldr_http2.ino   # firmware do ESP32 (Arduino IDE)
├── servidor/
│   ├── servidor.py             # API Flask + dashboard
│   └── requirements.txt        # dependências do Python
└── README.md
```

## Hardware

- ESP32 DevKit (30 pinos)
- Módulo DHT11 (temperatura e umidade)
- Módulo de luminosidade com LDR (saída digital DO)
- Protoboard, jumpers e cabo micro-USB **de dados**

### Ligações

| Módulo | Pino do módulo | ESP32 |
| --- | --- | --- |
| DHT11 | VCC | 3V3 |
| DHT11 | DATA | GPIO 22 (D22) |
| DHT11 | GND | GND |
| Módulo LDR | VCC | 3V3 |
| Módulo LDR | DO | GPIO 4 (D4) |
| Módulo LDR | GND | GND |

O limite entre claro e escuro do módulo LDR é ajustado no trimpot azul do próprio módulo.

## Firmware (ESP32)

### Requisitos

- [Arduino IDE](https://www.arduino.cc/en/software) 2.x
- Pacote de placas **esp32 by Espressif Systems** (Boards Manager). Se ele não aparecer, adicione em *File > Preferences > Additional boards manager URLs*:
  `https://espressif.github.io/arduino-esp32/package_esp32_index.json`
- Biblioteca **DHT sensor library** (Adafruit), instalada junto com a **Adafruit Unified Sensor** (Library Manager)
- Driver USB **CP210x** da Silicon Labs, se o Windows não criar uma porta COM para a placa

`WiFi.h` e `HTTPClient.h` já vêm com o pacote esp32.

### Configuração

No início do `esp32_dht11_ldr_http2.ino`, preencha:

```cpp
const char* WIFI_SSID  = "NOME_DA_REDE";    // rede 2,4 GHz
const char* WIFI_SENHA = "SENHA_DA_REDE";
const char* URL_SERVIDOR = "http://IP_DO_COMPUTADOR:5000/api/leituras";
```

O `IP_DO_COMPUTADOR` é o "Endereço IPv4" do adaptador **Wi-Fi** do computador que roda o servidor (comando `ipconfig` no Windows). O ESP32 e o computador precisam estar na mesma rede.

Se a luminosidade aparecer invertida, troque `LOW` por `HIGH` em `#define NIVEL_COM_LUZ`.

### Gravação

1. Em *Tools > Board*, escolha **ESP32 Dev Module**.
2. Em *Tools > Port*, escolha a porta do ESP32 (aparece como *Silicon Labs CP210x* no Gerenciador de Dispositivos).
3. Em *Tools > Upload Speed*, escolha **115200**.
4. Clique em **Upload**. Se travar em "Connecting...", segure o botão **BOOT** da placa até a gravação começar.
5. Abra o **Serial Monitor** em **115200 baud**. A cada envio aparece `Enviado: {...} -> HTTP 201`.

## Servidor e dashboard

### Requisitos

- Python 3.10 ou superior
- [MongoDB Community Server](https://www.mongodb.com/try/download/community) rodando em `mongodb://localhost:27017` (no Windows: `winget install MongoDB.Server`)

### Como rodar

```bash
cd servidor
pip install -r requirements.txt
python servidor.py
```

Abra **http://localhost:5000** no navegador. Se o Windows perguntar sobre o Firewall, permita o acesso do Python, senão o ESP32 não consegue enviar os dados.

Para usar outro MongoDB (por exemplo, o MongoDB Atlas), defina a variável de ambiente `MONGO_URI` antes de rodar o servidor.

### Rotas

| Método | Rota | Função |
| --- | --- | --- |
| POST | `/api/leituras` | Recebe o JSON do ESP32 e grava no banco |
| GET | `/api/leituras` | Últimas 50 leituras em JSON |
| GET | `/api/dados?minutos=60` | Leituras de um período (`0` = todas) |
| GET | `/` | Dashboard |

Os dados ficam no banco `monitoramento`, coleção `leituras`, um documento por leitura.

## Problemas comuns

| Sintoma | Solução |
| --- | --- |
| `Write timeout` ou "tempo limite do semáforo" no upload | A porta escolhida não é o ESP32 (geralmente é do Bluetooth). Instale o driver CP210x e use um cabo de dados. |
| `Unable to verify flash chip connection` | Reduza o *Upload Speed* para 115200. |
| Menu *Port* apagado | O computador não está vendo a placa: confira cabo e driver. |
| Serial mostra "Falha ao ler o DHT11" | Confira as ligações do DHT11 e o pino em `PINO_DHT`. |
| Serial mostra `erro: connection refused` ou timeout | Confira o IP em `URL_SERVIDOR`, se o servidor está rodando e se o Firewall libera a porta 5000. |
| Servidor diz "Não consegui conectar ao MongoDB" | O serviço do MongoDB não está rodando (`Get-Service *mongo*` no PowerShell). |

## Autores

- Thales Yoshihico Mathuy de Sá
- [nome do integrante]
- [nome do integrante]
- [nome do integrante]
