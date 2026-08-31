# Especificação de Estilo de Legenda: Dynamic Word-by-Word Karaoke Highlight (Estilo Hormozi)

## 1. Visão Geral (Overview)
- **Nome do Estilo:** Legenda Dinâmica Estilo Karaokê / Active Word Highlight (comumente chamado de "Estilo Hormozi").
- **Objetivo:** Maximizar a retenção visual e cadência de leitura em vídeos curtos verticais (TikTok, Reels, Shorts), sincronizando o destaque visual exato da palavra falada com o áudio em tempo real.

---

## 2. Tipografia e Formatação
- **Caixa:** Totalmente em caixa alta (ALL CAPS).
- **Família Tipográfica:** Sem serifa, peso extra-bold/black (Ex.: *Montserrat ExtraBold/Black*, *The Bold Font*, *Futura Bold*, *Impact*).
- **Cor do Texto Base:** Branco puro (`#FFFFFF`).
- **Contorno / Sombra:** Contorno preto sólido (Stroke: 2px a 4px) ou sombra projetada nítida (`drop-shadow`) para contraste universal contra qualquer fundo.
- **Tamanho do Bloco (Pacing):** Blocos curtos de 1 a 4 palavras por tela. O texto não se acumula em parágrafos longos.

---

## 3. Mecânica do Destaque (Active Word Highlight)
- **Elemento Chave:** Caixa de fundo colorida (Pill / Rounded Box) aplicada individualmente e exclusivamente sobre a palavra ativa no milissegundo em que ela é pronunciada.
- **Sincronização:** Baseada em carimbos de data/hora por palavra (*word-level timestamps* / STT como Whisper).
- **Palavra Ativa (Spoken Word):**
  - **Fundo (Background):** Caixa retangular preenchida com cantos arredondados (`border-radius: 4px - 8px`, `padding: 4px 10px`).
  - **Cores de Destaque:** Cores saturadas e de alto contraste (ex.: Rosa Choque/Magenta `#E91E63` / `#FF007F`, Amarelo Neon `#FFE500`, Verde Limão `#00FF66`, Vermelho Vibrante `#FF2A2A`).
  - **Texto da Palavra Ativa:** Permanece branco (`#FFFFFF`) ou muda para preto (`#000000`) dependendo da cor do fundo para garantir contraste.
- **Palavras Inativas:** Mantêm fundo transparente, texto branco e contorno preto padrão.
- **Transição:** Imediata (corte seco / discrete step), sem fade longo, acompanhando o ritmo exato da fala.

---

## 4. Posicionamento e Layout
- **Alinhamento:** Centralizado horizontalmente (`center-aligned`).
- **Posição Vertical:** Terço inferior ou centro-baixo (região do peito do interlocutor, aproximadamente 60% a 75% da altura da tela vertical 9:16), evitando a área de sobreposição das interfaces nativas do TikTok/Instagram (botões de curtir, comentários e descrição inferior).
