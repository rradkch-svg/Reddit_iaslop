# Tutorial: Criação do Primeiro Vídeo 9:16 com a WebUI

Este tutorial prático orienta você do zero até a geração e exportação do seu primeiro vídeo vertical (Shorts / Reels / TikTok) para qualquer tema ou nicho de conhecimento em formato nativo 1080x1920, com narração neural de alta fidelidade, legendas dinâmicas com destaque de palavra (*Pill Box*) e tomadas de vídeo reais auditadas por IA multimodal.

---

## 1. Pré-Requisitos Mínimos

Antes de iniciar, certifique-se de que seu ambiente possui:
- Python 3.11+ (64-bit) instalado.
- FFmpeg e FFprobe com suporte a `libass` adicionados ao `PATH` (ex: build Gyan.FFmpeg no Windows).
- Chave de API ativa do Google Gemini configurada no arquivo `.env` ou inserida diretamente na interface.

---

## 2. Inicialização da Interface Web

Abra o terminal na raiz do projeto e execute o comando:

```powershell
py -3.11 -m streamlit run app.py --server.port 8501
```

Acesse a interface no navegador através do endereço `http://localhost:8501`.

---

## 3. Fluxo de Execução Passo a Passo

### Passo 1: Configuração do Modelo e Proposta de Temas
1. Na barra lateral (*Sidebar*), insira sua chave do Gemini ou verifique se ela foi carregada do `.env`.
2. Selecione o modelo primário (recomendado: `gemini-flash-lite-latest`).
3. Mantenha ativadas as opções de **Fallback Automático** e **Cooldown com Contador Regressivo**.
4. Configure a concorrência desejada (padrão: **4 Workers**) para proteção contra limites de taxa da API.
5. Na aba principal **🎬 Estúdio de Produção**, clique no botão **💡 Propor Novos Temas**.
6. O `ProposerAgent` gerará propostas estruturadas contendo título do tema, gancho inicial (*hook*) de retenção e explicação central do conceito.

### Passo 2: Avaliação e Seleção do Tema
1. Selecione um dos temas gerados na lista interativa.
2. Clique em **⚖️ Avaliar Tema Selecionado**.
3. O `EvaluatorAgent` atribuirá uma nota de 0.0 a 10.0 e emitirá um parecer sobre a clareza conceitual, apelo visual e potencial de retenção.

### Passo 3: Produção Automatizada do Vídeo Completo
1. Clique no botão de destaque **🚀 Gerar Vídeo Completo**.
2. O sistema executará automaticamente os seguintes estágios:
   - **Roteiro e Storyboard:** O `DirectorAgent` decompõe o tema em cenas sequenciais com narração concisa e termos de busca visuais em inglês.
   - **Síntese de Voz:** O `AudioEngine` sintetiza a narração contínua via Edge-TTS e extrai os carimbos de tempo precisos palavra por palavra.
   - **Coleta e Auditoria Concorrente:** O `BRollEngine` baixa e valida a duração real dos arquivos via `ffprobe`, recortando e examinando múltiplos trechos em paralelo com o `ReviewerAgent` (Gemini Vision) para garantir imagens limpas e sem pessoas.
   - **Legendas Dinâmicas:** O módulo `subtitles.py` compila o arquivo `.ass` com destaque de palavra em caixa de realce (*Pill Box*).
   - **Renderização Final:** O FFmpeg compõe as trilhas de vídeo, áudio e legendas em resolução nativa de 1080x1920 (CRF 18).

---

## 4. Visualização, Diagnóstico e Download

Ao finalizar o pipeline:
- O vídeo será exibido no player integrado do Streamlit em formato vertical 9:16.
- O botão **⬇️ Baixar Vídeo 9:16 (.mp4)** permitirá salvar o arquivo final renderizado.
- O painel expansível **🛡️ Relatório de Auditoria Visual** apresentará a lista de todas as cenas aprovadas pelo `ReviewerAgent` com suas respectivas notas e elementos visuais detectados.
- Caso ocorra throttling de API ou de download de vídeo durante a execução, alertas informativos serão exibidos automaticamente na WebUI e na aba **📊 Central de Logs & Diagnóstico**.
