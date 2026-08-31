# Referência da API: Deduplicação Heurística de Contexto e Títulos (`deduplication.py`)

Especificação técnica do motor de deduplicação semântica, taxonomia de engenharia automotiva e padronização de títulos com teto estrito de 100 caracteres.

---

## 1. Funções de Formatação e Sanitização

### `sanitize_and_cap_title(title: str, max_length: int = 100) -> str`

Garante que o título do vídeo satisfaça dois invariantes fundamentais:
1. **Comprimento Máximo:** Nunca excede `max_length` caracteres (padrão 100), realizando quebra elegante na última palavra completa sem cortar caracteres no meio.
2. **Remoção de Clichês:** Remove expressamente sufixos como `| Segredos da Engenharia`, `- Segredos da Engenharia`, `| AutoTech` e emojis decorativos iniciais.

```python
sanitize_and_cap_title("Ferrari F40: A Bruta Engenharia dos Turbos Duplos | Segredos da Engenharia")
# Retorno: "Ferrari F40: A Bruta Engenharia dos Turbos Duplos"
```

---

## 2. Extração e Taxonomia de Domínios Mecânicos

### `extract_canonical_entity(text: str) -> str`

Extrai a entidade veicular central (marca, modelo, chassi e geração), normalizando variações de nomenclatura (ex: "BMW M3 CSL E46", "Porsche 911 GT3 RS", "Toyota Supra 2JZ").

### `classify_technical_domains(text: str) -> List[str]`

Classifica o texto em um ou mais dos 9 domínios mecânicos canônicos:
- `AERODINAMICA_DOWNFORCE`: Asa ativa, DRS, efeito solo, difusores, venturi.
- `SOBREALIMENTACAO_TURBO`: Turbo, biturbo, supercharger, intercooler, water-spray, mivec.
- `MOTORIZACAO_COMBUSTAO`: V10, V12, V8, flat-plane, 9000 rpm, virabrequim, bloco de ferro.
- `TRANSMISSAO_DRIVETRAIN`: PDK, dupla embreagem, sequencial, launch control.
- `CHASSI_MATERIAIS_LEVES`: Fibra de carbono, monocoque, alívio de peso, rigidez.
- `SUSPENSAO_DINAMICA`: Suspensão ativa, magnética, multilink, geometria.
- `TRACAO_VETORIZACAO`: ATTESA, Quattro, AWD, vetorização de torque, LSD.
- `FRENAGEM_TERMICA`: Carbono-cerâmica, dissipação de calor, calipers.
- `HISTORICO_RACING_LEMANS`: Le Mans, Nürburgring, Grupo B, homologação.

---

## 3. Classe `ContextualTopicAuditor`

Realiza auditoria em 4 dimensões sobrepostas entre o tema candidato e a base histórica de vídeos produzidos:

```python
auditor = ContextualTopicAuditor(vehicle_sim_threshold=0.70, text_sim_threshold=0.65)
is_dup, conf, reason = auditor.evaluate_candidate(candidate_topic, existing_items)
```

### Regras de Bloqueio Heurístico:
1. **Mesmo Veículo + Mesmo Domínio Mecânico:** Bloqueia automaticamente, mesmo que os títulos usem palavras completamente distintas (ex: "Porsche 911 GT3 RS: Downforce" vs "Como a asa ativa do 911 GT3 RS funciona").
2. **Mesmo Veículo + Alta Sobreposição de Conceitos Mecânicos ($\ge 3$ Stems):** Bloqueia refraseamento de tema idêntico.
3. **Veículos Diferentes com Mesmo Princípio Físico:** Aprovado como 100% inédito (ex: Valkyrie Venturi vs GT3 RS Asa).
