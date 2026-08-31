# Explicação: Varredura Temporal de Trechos e Enquadramento Dinâmico 9:16

Este documento explora a teoria e os algoritmos por trás da extração de segmentos específicos em arquivos de vídeo brutos da internet, a prevenção de estouros de duração e a conversão de formato horizontal (16:9) para vertical (9:16).

---

## 1. O Desafio da Distribuição Temporal em Vídeos da Internet

Vídeos de divulgação, tutoriais ou documentários na web tipicamente seguem uma estrutura heterogênea:
- **0% a 20% do tempo:** Vinhetas institucionais, introduções, saudações de apresentadores (*talking heads*) e pedidos de engajamento.
- **20% a 80% do tempo:** Demonstração pura do conceito, tomadas do objeto de estudo em alta ação, experimentos e filmagens limpas.
- **80% a 100% do tempo:** Conclusões e créditos finais.

Se um algoritmo recortar o vídeo cegamente nos primeiros segundos, ele invariavelmente capturará a introdução com pessoas ou telas estáticas.

---

## 2. O Algoritmo de Varredura Multi-Trecho (*Segment Scanning*)

Em vez de descartar um arquivo de mídia completo por causa de uma introdução inadequada, o `BRollEngine` divide o domínio temporal do vídeo em pontos de amostragem:

$$
S = \left\{ s_1, s_2, s_3, s_4 \right\} = \left\{ 0.20 \times D,\, 0.45 \times D,\, 0.65 \times D,\, 0.85 \times D \right\}
$$

Onde $D$ representa a duração real do arquivo bruto em segundos, extraída diretamente via `ffprobe`.

Para prevenir erros de decodificação (`AVERROR_EOF` / saída `3199971767`), a duração efetiva do corte $T_{\text{corte}}$ é matematicamente limitada pela duração restante do arquivo:

$$
T_{\text{corte}} = \min\left( T_{\text{alvo}},\, \max(1.0,\, D - s_i) \right)
$$

Para cada ponto temporal $s_i \in S$, o sistema:
1. Recorta um segmento de duração $T_{\text{corte}}$ a partir de $s_i$.
2. Aplica o enquadramento vertical 9:16 via *Pan & Scan* com interpolação Lanczos.
3. Extrai um frame central para auditoria do `ReviewerAgent`.
4. Se o trecho for aprovado (sem pessoas e com alta relevância temática), a busca para aquela cena é concluída com sucesso.

---

## 3. Teoria do Pan & Scan Vertical e Interpolação Lanczos

A conversão de uma fonte horizontal ($W_{\text{in}} \times H_{\text{in}} = 1920 \times 1080$) para o formato vertical nativo ($1080 \times 1920$) exige corte e redimensionamento proporcional.

Para evitar distorção de aspecto (*anamorphic stretch*), o fator de escala $k$ é definido por:

$$
k = \max\left( \frac{1080}{W_{\text{in}}},\, \frac{1920}{H_{\text{in}}} \right)
$$

A matriz de corte centralizada garante que a área de interesse permaneça no centro focal:

$$
X_{\text{offset}} = \frac{k \cdot W_{\text{in}} - 1080}{2}, \quad Y_{\text{offset}} = \frac{k \cdot H_{\text{in}} - 1920}{2}
$$

A interpolação **Lanczos** (3 lobes) preserva arestas nítidas, texturas finas e detalhes visuais em alta frequência, eliminando o aspecto borrado de redimensionamentos bilineares tradicionais.
