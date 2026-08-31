# Como Introduzir Métricas de Vídeos e Analisar o Sucesso no Algoritmo

Este guia passo a passo orienta como inserir as métricas reais do YouTube Shorts (visualizações, retenção aos 3s, APV, CTR) no arquivo template na raiz do projeto e calibrar a inteligência algorítmica da IA.

---

---

## 1. Fluxo Principal: Ingestão Direta de Export do YouTube (.zip em `/analytics`)

O método mais rápido, automático e livre de erros é utilizar o arquivo `.zip` exportado diretamente do YouTube Studio Analytics:

1. **No YouTube Studio:** Acesse *Analytics* $\to$ *Modo Avançado* $\to$ Clique em **Exportar dados atuais** $\to$ Escolha formato **.zip** (ou .csv).
2. **Coloque o arquivo na pasta `/analytics`:** Solte o arquivo `.zip` baixado diretamente dentro da pasta `analytics/` na raiz do projeto.
3. **Execute a sincronização:**
   ```bash
   python scripts/sync_metrics.py
   ```
   *O sistema detectará automaticamente o `.zip`, extrairá visualizações, retenção média (APV %), tempo de exibição, CTR %, inscritos e duração, realizando o casamento inteligente com os vídeos gerados no canal.*

---

## 2. Fluxo Alternativo: Planilha Manual (`METRICAS_VIDEOS.csv`)

Caso deseje preencher ou ajustar números manualmente:
Abra o arquivo [`METRICAS_VIDEOS.csv`](../../METRICAS_VIDEOS.csv) e localize a linha do vídeo correspondente.
Preencha a coluna `views` com o número total de visualizações obtidas:

```csv
identificador,batch,video_index,titulo,veiculo,hook,...,views,retencao_3s_pct,apv_pct,ctr_pct,curtidas,comentarios,observacoes_sucesso,status_metadata
batch_1_video_1,batch_1,1,BMW M5 V10 E60: A Sinfonia e a Dor de Cabeça...,BMW M5 V10 E60,E se eu te disser que...,125000,82.5,88.0,14.0,8900,450,Explodiu de comentários pelo motor V10 S85,VALIDO
```

Campos opcionais recomendados para maior precisão do algoritmo:
- **`retencao_3s_pct`**: Porcentagem de retenção nos primeiros 3 segundos (mede a eficácia do gancho/hook).
- **`apv_pct`**: *Average Percentage Viewed* (Retenção média ao longo de todo o vídeo).
- **`ctr_pct`**: Taxa de escolha no feed de Shorts (*Viewed vs Swiped Away*).
- **`observacoes_sucesso`**: Suas anotações qualitativas sobre o que mais gerou engajamento.

> [!NOTE]
> Os metadados dos pesos com os quais o roteiro foi desenvolvido (`peso_hook`, `peso_tech`, `peso_antihype`, `cadencia_wpm`) são preservados individualmente por vídeo para correlacionar o estilo de escrita com os picos de retenção.

---

## 3. Sincronizando via Interface Gráfica Web

Pela interface Web Streamlit:
1. Abra a aplicação com `iniciar.bat` ou `streamlit run src/app.py`.
2. Acesse a aba **"🧠 Memória Algorítmica & Feedback (.md)"** $\to$ **"📦 Ingestão Automática de Analytics do YouTube"**.
3. Clique em **"🚀 Processar Export do YouTube (.zip)"** ou arraste o `.zip` diretamente para o campo de upload.

---

## 4. O que a IA Faz Automaticamente

1. **Classificação em Tiers:**
   - 🏆 **Tier S (Super Viral):** APV $\ge 85\%$ e Retenção 3s $\ge 75\%$
   - 🥇 **Tier A (Excelente):** APV $\ge 70\%$ e Retenção 3s $\ge 65\%$
   - 🥈 **Tier B (Sólido):** APV $\ge 55\%$ e Retenção 3s $\ge 50\%$
   - 🥉 **Tier C (Abaixo da Média):** APV $\lt 50\%$
   - ⚠️ **Tier D (Queda no Gancho):** Retenção 3s $\lt 30\%$
2. **Correlação Estatística:** A IA compara os pesos dos vídeos Tier S/A contra vídeos de menor retenção e descobre o que gerou o destaque.
3. **Calibração de Próximos Roteiros:** O vetor de pesos em [`data/algorithm_memory/ALGORITHM_MEMORY.md`](../../data/algorithm_memory/ALGORITHM_MEMORY.md) é atualizado, fazendo as novas gerações convergirem para a fórmula de alta retenção sem jamais repetir os temas.
