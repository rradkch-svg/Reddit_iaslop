# Explicação: Filosofia do Sistema Multi-Agentes com Auditoria Multimodal

Este documento discute os fundamentos teóricos, as decisões de arquitetura de software e os princípios que orientam o pipeline autônomo de geração de conteúdo em vídeo.

---

## 1. Por que um Sistema Multi-Agentes Especializados?

A criação automatizada de vídeos explicativos de alta retenção não pode ser tratada como uma única chamada monolítica de LLM. Tarefas distintas exigem objetivos conflitantes e critérios de avaliação independentes:

- **Divergência Criativa vs. Rigor Crítico:** O agente propositor (`ProposerAgent`) deve maximizar a curiosidade e explorar ideias não óbvias em qualquer nicho, enquanto o avaliador (`EvaluatorAgent`) atua como um filtro rigoroso, reprovando temas genéricos ou sem densidade explicativa.
- **Roteirização Narrativa vs. Direção de Arte:** O roteirista cria a progressão psicológica da narrativa e o ritmo do áudio, enquanto a direção técnica traduz cada frase falada em tomadas visuais e termos de busca estritamente direcionados.
- **O Problema da Alucinação Visual de Metadados:** Modelos de linguagem de texto não conseguem inspecionar o conteúdo visual real de um arquivo de vídeo da internet apenas pelo seu título. O auditor visual (`ReviewerAgent`) introduz a etapa de **Verificação Empírica por Visão Computacional Multimodal**, inspecionando quadros reais antes de autorizar a inclusão na linha do tempo.

---

## 2. A Camada de Auditoria Empírica Multimodal

A arquitetura adota o protocolo de **Verificação Obrigatória de Evidências**.

Quando uma busca retorna candidatos para uma cena, o sistema executa a auditoria em duas fases:

### Fase 1: Pré-Filtro Heurístico em Tempo Real ($O(1)$)
Descarta instantaneamente vídeos com termos proibidos em metadados (como gameplays, vlogs, podcasts ou temas descorrelacionados) sem onerar a cota de visão computacional da API.

### Fase 2: Inspeção de Visão Computacional com Gemini Vision
Extrai um quadro representativo do recorte e submete a uma avaliação de pertinência e validação da política de imagens limpas sem pessoas.

A função de decisão do auditor é descrita formalmente por:

$$
\text{Veredicto}(\text{Frame}, \text{Tema}) =
\begin{cases}
\text{Reprovado}, & \text{se } \text{DetectaPessoa}(\text{Frame}) = \text{true} \\
\text{Reprovado}, & \text{se } \text{Pertinencia}(\text{Frame}, \text{Tema}) \lt 7.0 \\
\text{Aprovado}, & \text{caso contrario}
\end{cases}
$$

Dessa forma, o pipeline garante consistência visual absoluta sem depender de confiança cega em títulos ou descrições textuais de terceiros.
