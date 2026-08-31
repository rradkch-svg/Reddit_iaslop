# Algorithmic Memory, Big Data Feedback & Two-Stage Narrative Synthesis

This document details the architecture of the **Algorithmic Memory System (`ALGORITHM_MEMORY.md`)**, the **Two-Stage Mechanical Synthesis Engine (`DissertationAgent` $\to$ `DirectorAgent`)**, the **Automotive Phonetic Pronunciation Matrix**, and the **Ultra-HD Visual Pipeline Upgrade**.

---

## 1. Problem Formulation & Theoretical Motivation

Automated content generation often suffers from four systemic failure modes:
1. **Sensationalist Hallucination (Hype Dilution):** Replacing rigorous mechanical explanations with generic buzzwords (*"o monstro divino que destruiu a física"*), degrading viewer retention.
2. **Phonetic Corruption:** Standard text-to-speech engines mispronounce foreign automotive brand names, chassis codes, and engineering terms (*"Koenigsegg", "Twin-Turbo", "Porsche", "Downforce"*).
3. **Low-Resolution Video Streams:** Overly restrictive video downloader format rules download 360p or 480p fallback streams instead of native 4K/1440p/1080p60 VP9/AV1 streams.
4. **Algorithmic Amnesia:** Generators repeat topics or fail to converge toward the pacing, hook style, and density characteristics that yielded superior retention in past publications.

---

## 2. Two-Stage Synthesis Architecture (*Dissertation $\to$ High-Retention Distillation*)

To ensure rich, rigorous content within a 60-to-120-second dynamic format, narrative generation is decomposed into two distinct phases:

```
┌─────────────────────────────────────────────────────────────┐
│ FASE 1: DissertationAgent (Monografia de Engenharia Pura)   │
│ - Análise termodinâmica, taxas de compressão e RPM          │
│ - Aerodinâmica real (downforce kg, Cd, dutos Venturi)       │
│ - Desafio físico intransponível e triunfo da metalurgia    │
│ - 300 a 500 palavras de densidade técnica pura             │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ FASE 2: DirectorAgent (Destilação de Alta Retenção 1.25x)   │
│ - 0s a 3s: Hook magnético (Palavra de chamariz + paradoxo)  │
│ - 3s a 90s: Explicação mecânica veloz sem adjetivos vazios  │
│ - 14 a 22 tomadas rápidas com queries de busca em 4K        │
│ - Síntese concisa de 160 a 260 palavras a 1.25x             │
└─────────────────────────────────────────────────────────────┘
```

#### Phase 1: Pure Engineering Dissertation
The `DissertationAgent` produces an exhaustive technical monograph. It details engine architecture, aspiration pressure, power output, torque curves, aerodynamic downforce at specific velocities, and lap times. Sensationalist adjectives are strictly prohibited.

#### Phase 2: High-Retention Distillation
The `DirectorAgent` consumes the technical dissertation and distills it into an engaging 60-to-120-second script at 1.25x speed (160 to 260 words). The beginning contains a magnetic 3-second hook (curiosity gap), while the middle delivers mechanical substance without sensationalist filler.

---

---

## 3. Algorithmic Memory & Temporal Exposure Normalization Model

A major statistical challenge in automated video publishing is **Exposure Age Bias**: older videos accumulate views over 20 to 30 days, while freshly published videos (1 to 3 days old) appear to have lower raw view counts despite experiencing viral velocity.

To eliminate this bias, the `AlgorithmMemorySystem` processes daily timeseries exports from YouTube Studio Analytics (`Chart data.csv` and `Table data.csv`), extracting:
- $V$: Total Views in the 28-day window
- $T_{\text{pub}}$: Video Publication Timestamp
- $\Delta t_{\text{exp}} = \max\left(1.0,\, (T_{\text{ref}} - T_{\text{pub}}).\text{days} + 1.0\right)$: Active Exposure Lifespan in Days
- $\text{VPD} = \frac{V}{\Delta t_{\text{exp}}}$: Daily Views Velocity (Views Per Day)
- $V_{\text{norm, 28d}} = V \cdot \left(1.0 + \gamma \cdot \ln\left(\frac{28.0}{\Delta t_{\text{exp}}}\right)\right)$: 28-Day Projected Volume Benchmark ($\gamma \approx 1.2$)
- $\text{APV}$: Average Percentage Viewed (Time-Invariant Intrinsic Retention)
- $\text{CTR}$: Impressions Click-Through Rate / Choice Rate

### Exposure-Aware Performance Tiering

Videos are evaluated using a multi-factor classification algorithm that immediately recognizes viral burst velocities on day 1 without penalizing recent uploads:

$$
\text{Tier} = \begin{cases}
\text{INCUBATING} & \text{se } \Delta t_{\text{exp}} \le 1.0 \text{ e } V \lt 10 \text{ (YouTube Sandbox)} \\
D & \text{se } R_{3s} \lt 30\% \text{ ou } \text{APV} \lt 20\% \text{ (Gancho fraco / Rejeição)} \\
S & \text{se } \text{VPD} \ge 250 \text{ ou } V_{\text{norm, 28d}} \ge 3000 \text{ ou } V \ge 5000 \\
A & \text{se } \text{VPD} \ge 75 \text{ ou } V_{\text{norm, 28d}} \ge 1000 \text{ ou } \text{APV} \ge 65\% \\
B & \text{se } \text{VPD} \ge 15 \text{ ou } V_{\text{norm, 28d}} \ge 200 \text{ ou } \text{APV} \ge 40\% \\
C & \text{se } \Delta t_{\text{exp}} \ge 3.0 \text{ e } \text{VPD} \lt 15 \\
\end{cases}
$$

### Velocity-Weighted Auxiliary Weights Calibration

When recalibrating the AI generation guidance vector $\mathbf{w}$, the statistical contribution of each top-performing video $r \in \text{TopTier}$ is weighted by its **Daily Velocity (VPD)** and **Retention (APV %)** rather than raw historical views:

$$
\omega_{r} = \text{VPD}_{r} \cdot \left(1.0 + \frac{\text{APV}_{r}}{100.0}\right)
$$

$$
\mathbf{w}_{\text{active}} = \frac{\sum_{r \in \text{TopTier}} \omega_{r} \cdot \mathbf{w}_{r}}{\sum_{r \in \text{TopTier}} \omega_{r}}
$$

This guarantees that a breakout video published yesterday immediately impacts the prompt engineering and pacing cadence of the very next batch generated by the studio!

---

## 4. Master Automotive Phonetic Lexicon

The `AutomotivePronunciationEngine` converts foreign brands and technical terminology into Portuguese phonetic approximations before audio synthesis.

| Original Term | Display Subtitle | Phonetic Audio Stream |
| :--- | :--- | :--- |
| **Porsche** | Porsche | `Pór-xê` |
| **Koenigsegg** | Koenigsegg | `Kônig-zég` |
| **McLaren** | McLaren | `Méc-Láren` |
| **Lamborghini** | Lamborghini | `Lam-bor-guíni` |
| **Twin-Turbo** | Twin-Turbo | `tuin târbo` |
| **Supercharger** | Supercharger | `súper-tchárdjer` |
| **Downforce** | Downforce | `dáun-fórce` |
| **Wastegate** | Wastegate | `uêiste-guêiti` |
| **Horsepower** | Horsepower | `hórce-páuer` |
| **Redline** | Redline | `réd-láini` |

### Word-Boundary Timing Alignment

To maintain word alignment in ASS subtitles, the original clean text and the phonetically altered audio stream are mapped using proportional character and token alignment. Subtitles display the pristine original spelling while the neural voice speaks the phonetics.

---

## 5. High-Resolution Visual Composition Pipeline

### Native 4K/1440p/1080p Stream Selection
The downloader format selector avoids restrictive container filters and selects highest resolution streams:

```text
bestvideo[height<=2160]+bestaudio/bestvideo[height<=1440]+bestaudio/bestvideo[height<=1080]+bestaudio/best
```

### Lanczos Resampling & Adaptive Unsharp Masking
Downloaded clips are scaled and cropped to 9:16 (1080x1920) using Lanczos-windowed Sinc interpolation paired with adaptive luma/chroma sharpening:

```text
scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos+accurate_rnd,crop=1080:1920:(in_w-1080)/2:(in_h-1920)/2,setsar=1,unsharp=lx=5:ly=5:la=0.8:cx=3:cy=3:ca=0.4
```

Final encoding operates at CRF 16 with preset `faster`, generating clean 60fps vertical video without compression artifacts.
