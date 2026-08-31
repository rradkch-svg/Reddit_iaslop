# Guia Prático: Personalização de Vozes Neurais e Estilização de Legendas

Este guia ensina como configurar as vozes neurais de narração via Edge-TTS e personalizar as cores, fontes e caixas de realce (*Pill Box*) das legendas dinâmicas para qualquer gênero de conteúdo.

---

## 1. Seleção de Vozes no `AudioEngine`

O módulo `audio.py` utiliza o Microsoft Edge Neural TTS com suporte a carimbos de tempo em nível de palavra (*WordBoundary events*), garantindo sincronia perfeita com os cortes de vídeo.

### Vozes Neurais Recomendadas (Português)

No arquivo `audio.py` ou via parâmetro `voice_name`:
- `pt-BR-AntonioNeural`: Tom firme, sóbrio, autoritário e formal (Ideal para conteúdos científicos, históricos, documentais ou técnicos).
- `pt-BR-FranciscaNeural`: Tom fluido, claro, expressivo e dinâmico (Ideal para storytelling e divulgação científica).
- `pt-BR-ThalitaNeural`: Tom moderno, ágil e jovem (Ideal para curiosidades rápidas e micro-documentários).

### Controle de Velocidade e Dinâmica (`rate="+25%"`)

Para maximizar a retenção e dinamismo dos vídeos verticais (Shorts/Reels/TikTok), o `AudioEngine` opera por padrão a **1.25x (+25%)** de velocidade:

```python
from audio import AudioEngine

# Instanciação com taxa acelerada 1.25x (padrão recomendado)
engine = AudioEngine(voice="pt-BR-AntonioNeural", rate="+25%")
success, words_timing = engine.generate_audio("Texto da narração...", "output.mp3")

# Também é possível alterar dinamicamente na chamada
success, words_timing = engine.generate_audio("Texto...", "output.mp3", rate="+35%")
```

---

## 2. Estilização de Legendas Dinâmicas em `subtitles.py`

O formato `.ass` (Advanced SubStation Alpha) permite posicionar a legenda centralizada na porção inferior da tela com destaque de palavra ativa.

### Paleta de Cores e Formatação

As cores no formato ASS seguem a notação hexadecimal `&H00BBGGRR` (Blue-Green-Red invertido).

No arquivo `subtitles.py`:

```python
# Cor do texto base (Branco puro)
PRIMARY_COLOR = "FFFFFF"

# Cor do texto em destaque quando falado (Amarelo vibrante ou Verde neon)
HIGHLIGHT_COLOR = "FFE500"

# Cor de fundo da caixa de destaque (Pill Box escura translúcida)
PILL_BOX_COLOR = "&H00111111"
```

---

## 3. Ajuste de Tamanho de Fonte e Margens Seguras (*Safe Area*)

No cabeçalho do estilo ASS:

```ini
Style: Main,Montserrat ExtraBold,74,&H00FFFFFF,&H000000FF,&H00000000,&H00111111,-1,0,0,0,100,100,0,0,3,4.0,1.0,2,80,80,380,1
```

- **Tamanho da Fonte (`74`):** Otimizado para legibilidade instantânea em telas verticais de smartphones.
- **Margem Inferior (`380`):** Garante que o texto fique acima do rodapé de comentários e descrição das interfaces móveis (Shorts, Reels, TikTok).
- **Espessura da Borda (`4.0`):** Adiciona contorno para máximo contraste sobre qualquer fundo visual.
