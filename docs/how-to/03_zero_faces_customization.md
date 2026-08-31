# Guia Prático: Customização de Políticas Visuais e Varredura de Trechos

Este guia detalha como funciona a restrição de conformidade visual (*Clean Footage & Zero-Faces Policy*) e como personalizar as regras de aceitação de trechos no `ReviewerAgent` e `BRollEngine` para qualquer domínio de conteúdo.

---

## 1. Princípio da Política de Imagens Limpas (Zero-Faces Policy)

Em vídeos curtos de alta retenção voltados à explicação técnica, científica ou conceitual, a presença de apresentadores (*talking heads*), vlogs casuais ou pessoas conversando fragmenta o foco do espectador e reduz o tempo médio de visualização.

O pipeline impõe duas camadas complementares de verificação:
1. **Pré-filtro de Títulos ($O(1)$):** Descarta vídeos com termos proibidos em metadados antes do download (ex: "vlog", "review", "podcast", "unboxing").
2. **Inspeção Multimodal por Frame:** Analisa um quadro representativo de cada recorte de vídeo via Gemini Vision (timeout 60s).

---

## 2. Varredura Multi-Trecho Inteligente (*Segment Scanning*)

Vídeos de terceiros na web costumam conter introduções longas com pessoas falando nos primeiros segundos, mas possuem tomadas nítidas e demonstrações visuais excelentes na porção intermediária.

O `BRollEngine` não descarta o arquivo imediatamente. Em vez disso, após validar a duração real do arquivo baixado com `ffprobe`, ele calcula múltiplos pontos temporais estratégicos:

$$
S = \left\{ 0.20 \times D,\, 0.45 \times D,\, 0.65 \times D,\, 0.85 \times D \right\}
$$

Onde $D$ é a duração real do arquivo em segundos validada por `ffprobe`.

Para cada ponto temporal $s \in S$, o sistema:
1. Recorta um segmento de duração $T_{\text{cena}}$, garantindo que $s + T_{\text{cena}} \le D$.
2. Extrai o quadro central para auditoria com o `ReviewerAgent`.
3. Se a nota for $\ge 7.0$ e o veredicto atestar ausência de rostos e alta pertinência temática, o trecho é imediatamente aprovado e gravado.

---

## 3. Como Customizar as Regras de Avaliação no `ReviewerAgent`

No arquivo `agents.py`, você pode ajustar o prompt do sistema para atender às regras do seu domínio (ex: laboratórios, astronomia, tecnologia, natureza):

```python
self.system_instruction = (
    "Você é o Auditor Chefe de Qualidade Visual e Pertinência Temática.\n"
    "Sua missão é inspecionar o quadro (frame) de um recorte específico de vídeo e APROVAR ou REPROVAR.\n\n"
    "REGRAS DE REPROVAÇÃO IMEDIATA (aprovado = false, score = 1.0):\n"
    "1. PROIBIDO ROSTOS HUMANOS: Qualquer pessoa, rosto humano visível, apresentador ou talking head DEVE SER REPROVADO.\n"
    "2. Gameplay de videogame ou filmagens com elementos de interface não relacionados.\n"
    "3. Objetos ou cenários descorrelacionados do tema principal da cena.\n"
    "4. Imagens estáticas borradas, com ruído excessivo ou poluição visual de textos promocionais.\n\n"
    "REGRAS DE APROVAÇÃO (aprovado = true, score >= 7.0):\n"
    "1. Filmagem nítida em alta definição focada 100% no objeto, fenômeno, mecanismo ou cenário do tema.\n"
    "2. Demonstração limpa de alta qualidade técnica sem pessoas visíveis."
)
```
