# Guia Prático: Configuração do Ambiente e Dependências (Python 3.11+)

Este guia orienta a instalação e configuração de todos os binários, interpretadores e bibliotecas necessários para reconstruir e executar a plataforma de geração autônoma em qualquer ambiente Windows.

---

## 1. Instalação do Interpretador Python 3.11+

Recomenda-se utilizar Python 3.11 (64-bit) para compatibilidade plena com os tipos modernos e a nova SDK do Google GenAI.

### Instalação via WinGet no Windows

```powershell
winget install --id Python.Python.3.11
```

Verifique a instalação:

```powershell
py -3.11 --version
```

---

## 2. Instalação do FFmpeg e FFprobe com Suporte a Libass

O FFmpeg e o FFprobe são obrigatórios para:
- Extração de frames para auditoria visual multimodal (`ReviewerAgent`).
- Validação empírica da duração real dos arquivos antes do corte (`get_video_duration`).
- Recorte proporcional 9:16 (*Pan & Scan*) com interpolação Lanczos e CRF 18.
- Composição e queima de legendas `.ass` na trilha de vídeo final.

### Instalação via WinGet

Execute no terminal do PowerShell:

```powershell
winget install Gyan.FFmpeg
```

O pipeline detecta automaticamente o executável do FFmpeg instalado pelo WinGet em `~\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_*\*\bin\ffmpeg.exe`.

---

## 3. Instalação dos Pacotes Python

Atualize o instalador de pacotes e instale as dependências listadas em `requirements.txt`:

```powershell
py -3.11 -m pip install --upgrade pip setuptools wheel
py -3.11 -m pip install -r requirements.txt
```

As dependências principais incluem:
- `google-genai>=2.20.0`: Nova SDK oficial do Gemini com suporte a streaming, multimodal e controle de timeout HTTP.
- `streamlit>=1.62.0`: Interface web interativa com gestão de sessões.
- `edge-tts>=6.1.12`: Síntese de voz neural multilíngue com timestamps por palavra.
- `yt-dlp>=2025.1.26`: Motor de busca e download de transmissões de vídeo em alta definição.
- `pillow>=10.4.0`: Processamento e extração de imagens de quadros.
- `psutil>=5.9.0`: Monitoramento de processos e telemetria de recursos.
- `python-dotenv`: Carregamento automático de credenciais de ambiente.

---

## 4. Configuração das Variáveis de Ambiente (`.env`)

Crie ou edite o arquivo `.env` na raiz do projeto contendo sua chave de acesso à API do Google Gemini:

```env
GEMINI_API_KEY=sua_chave_gemini_aqui
GEMINI_FALLBACK_API_KEY=sua_chave_gemini_backup_aqui
```

---

## 5. Autenticação no YouTube com `cookies.txt` (Bypass Anti-Bot)

Para evitar bloqueios por taxa de requisição e erros de verificação anti-bot (*"Sign in to confirm you're not a bot"*):

1. Instale no seu navegador a extensão [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbngbenipdelhflbcdekhea) (Chrome/Edge/Brave) ou [cookies.txt](https://addons.mozilla.org/pt-BR/firefox/addon/cookies-txt/) (Firefox).
2. Acesse o [YouTube](https://www.youtube.com) conectado à sua conta.
3. Abra a extensão e clique em **Export** para baixar o arquivo `cookies.txt`.
4. Salve o arquivo na raiz do projeto (`C:\Users\piloto\Documents\automotive-slop\cookies.txt`).
5. O motor [broll_engine.py](file:///C:/Users/piloto/Documents/automotive-slop/src/broll_engine.py) detecta automaticamente o arquivo e injeta as credenciais no `yt-dlp`.

---

## 6. Validação da Instalação

Execute a suíte de testes unitários com Python 3.11:

```powershell
py -3.11 -m unittest discover tests
```

Se todos os testes unitários emitirem `OK`, o ambiente está validado e pronto para produção.

