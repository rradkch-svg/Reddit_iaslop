# Guia Prático: Gestão de Cotas, Rate Limiting e Alertas de Throttling

Este guia explica como a plataforma gerencia as restrições da cota gratuita (*Free Tier*) e paga do Google Gemini, o mecanismo de detecção de throttling de API e download, e como configurar a concorrência ideal para produção contínua sem bloqueios.

---

## 1. Parâmetros Oficiais de Cota (Gemini API)

No modelo padrão `gemini-flash-lite-latest`:
- **RPM Máximo (Requests Per Minute):** 15 requisições por minuto na camada gratuita.
- **RPD Máximo (Requests Per Day):** 1.500 requisições por dia.
- **TPM Máximo (Tokens Per Minute):** 1.000.000 tokens por minuto.
- **Timeout Padrão de Chamada:** Configurado para **60.0 segundos** (`types.HttpOptions(timeout=60000)`) na SDK `google-genai` para prevenir erros 504 (*Deadline Exceeded*) no tráfego multimodal de imagens.

---

## 2. O Rate Limiter Thread-Safe (`GeminiRateLimiter`)

Quando a plataforma coleta e inspeciona múltiplas cenas em paralelo via `ThreadPoolExecutor` (padrão: 4 workers), várias threads tentam acessar a API simultaneamente.

Para evitar rajadas (*bursts*) que ativem o erro `429 ResourceExhausted`, a classe `GeminiRateLimiter` em `agents.py` impõe um intervalo mínimo entre requisições consecutivas:

$$
\Delta t_{\text{intervalo}} = \frac{60.0}{\text{max\_rpm}}
$$

Para um limite seguro de 14 RPM:

$$
\Delta t = \frac{60.0}{14} \approx 4.28\text{ segundos}
$$

Qualquer chamada concorrente aguarda automaticamente sua vez na fila com um bloqueio atômico de thread (`threading.Lock`), garantindo que o teto de 15 RPM nunca seja violado.

---

## 3. Mecanismo de Alertas de Throttling na WebUI

O módulo `logger.py` implementa um rastreador thread-safe de eventos de estrangulamento (`record_throttling`), exibindo alertas proativos diretamente no topo da interface Streamlit:

- **Throttling de API (`API_GEMINI`):** Registra erros `429 Too Many Requests` ou `ResourceExhausted`, calculando o tempo de espera (*Retry-After*) e notificando a WebUI.
- **Throttling de Download de Vídeo (`YOUTUBE_DOWNLOAD`):** Identifica bloqueios de taxa de download de mídia externa (HTTP 429 ou desafios de bot) e aciona espera proporcional com aviso visual.
- **Escopo Estrito:** O detector rastreia estritamente throttling de rede externa (API e Download de Vídeo), **sem incluir throttling de CPU**.

---

## 4. Estratégia de Fallback em Cascata e Redundância Multi-Chave

Se um modelo ou chave de API atingir indisponibilidade temporária (503/504) ou esgotamento de cota diária/minuto (429 `RESOURCE_EXHAUSTED`), o motor executa camadas integradas de proteção automática:

### A. Redundância e Rotação Automática de Chaves de API

Caso uma chave primária atinja a cota diária ou limite por minuto (HTTP 429), o motor detecta o erro instantaneamente, registra o tempo de espera (*Retry-After*) e aciona a chave de redundância (`GEMINI_FALLBACK_API_KEY`):

$$
\text{Chave Principal (429)} \longrightarrow \text{Chave de Redundância/Fallback (Ativa)}
$$

Além disso, a função `get_prioritized_keys()` promove dinamicamente chaves ativas para a frente da fila, garantindo que requisições subsequentes não sofram a penalidade de tentar novamente uma chave em cooldown.

### B. Fallback de Modelos em Cascata

Se todas as chaves configuradas esgotarem a cota no modelo preferencial, o motor avança sequencialmente entre os modelos definidos em `DEFAULT_FALLBACK_MODELS`:

$$
\text{gemini-3.6-flash} \longrightarrow \text{gemini-3.5-flash-lite} \longrightarrow \text{gemini-3.1-flash-lite}
$$

### C. Cooldown Dinâmico com Barra Regressiva

Se todas as chaves e modelos da cadeia esgotarem simultaneamente a janela de cota, o motor extrai o tempo exato indicado pelo cabeçalho da API e exibe uma contagem regressiva em tempo real na tela até a liberação da janela.
