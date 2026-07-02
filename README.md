# 🎆 Computação Gráfica: Sistema de Partículas

Simulação de **fogos de artifício** implementada em Python puro, demonstrando os conceitos fundamentais de **Sistemas de Partículas** em Computação Gráfica.

> 🤖 *Projeto gerado integralmente com [Claude Opus](https://www.anthropic.com/claude) (Anthropic) — modelo de IA avançado para programação.*

---

## 📸 Preview

| Frame ~1s | Frame ~3.5s | Frame ~5s |
|:---------:|:-----------:|:---------:|
| Lançamento dos primeiros foguetes | Múltiplas explosões simultâneas | Cascata de partículas com fade |

> Execute o script para gerar a animação completa em **GIF** e **MP4**.

---

## 📖 Fundamentação Teórica

### O que é um Sistema de Partículas?

Um **Sistema de Partículas** é uma técnica de Computação Gráfica introduzida por **William T. Reeves** em 1983 no artigo *"Particle Systems — A Technique for Modeling a Class of Fuzzy Objects"* (SIGGRAPH '83). A técnica foi pioneiramente utilizada na cena da "Gênesis" do filme *Star Trek II: The Wrath of Khan*.

Diferente de modelagem geométrica tradicional (malhas poligonais, superfícies NURBS), sistemas de partículas representam objetos como **coleções de elementos pontuais** que evoluem no tempo segundo regras físicas e estocásticas. São ideais para modelar fenômenos naturais como:

- 🔥 Fogo e explosões
- 💨 Fumaça e nuvens
- 🌊 Água (sprays, cachoeiras)
- ✨ Faíscas e fogos de artifício
- 🌟 Campos estelares

### Conceitos Fundamentais

#### 1. Emissor (*Emitter*)
O ponto de origem das partículas. Define **onde**, **quando** e **como** as partículas nascem. Nesta simulação, cada foguete é um emissor que lança partículas ao explodir.

```
Emissor → [posição, taxa de emissão, direção, dispersão]
```

#### 2. Ciclo de Vida (*Lifecycle*)
Cada partícula passa por três fases:

```
Nascimento → Atualização → Morte
  (spawn)     (update)    (kill)
```

- **Nascimento**: posição, velocidade e cor iniciais são definidas (com componente aleatória)
- **Atualização**: a cada frame, aplica-se física (gravidade, arrasto) e atualiza-se a aparência
- **Morte**: quando `life ≤ 0`, a partícula é removida do sistema

#### 3. Dinâmica / Física
As partículas obedecem equações de movimento simplificadas:

```
posição(t+dt) = posição(t) + velocidade(t) · dt
velocidade(t+dt) = [velocidade(t) + aceleração · dt] × arrasto
```

Onde:
- **Aceleração** = gravidade (`g = 200 px/s²`, eixo Y para baixo)
- **Arrasto** (*drag*) = `0.98` por frame (simula resistência do ar)

#### 4. Aparência Visual
Cada partícula possui atributos visuais que variam ao longo da vida:

| Atributo | Comportamento |
|----------|--------------|
| **Cor** | Interpola linearmente de `cor_início` → `cor_fim` |
| **Alpha (opacidade)** | Fade-out com curva ease-out: `α = life^0.6` |
| **Tamanho** | Reduz gradualmente: `size × (0.4 + 0.8 × life)` |
| **Brilho (glow)** | Blend aditivo com intensidade gaussiana dupla |

#### 5. Blend Aditivo e Glow
Para simular o brilho luminoso, cada partícula é renderizada como um **disco gaussiano** com blend aditivo:

```
I(d) = núcleo(d) + halo(d)
núcleo(d) = exp(-0.5 × (d/σ)²) × α
halo(d)   = exp(-0.5 × (d/2.5σ)²) × α × 0.3

pixel_final = min(pixel_atual + cor × I(d), 255)
```

O blend aditivo (`+` ao invés de substituição) faz com que partículas sobrepostas criem áreas mais brilhantes, simulando acúmulo de luz.

#### 6. Estocasticidade
Elementos aleatórios são essenciais para um visual natural:

- **Velocidade de explosão**: distribuição gaussiana (`μ=180, σ=60` px/s)
- **Ângulo de dispersão**: uniforme em `[0, 2π]`
- **Tempo de vida**: uniforme em `[0.8, 2.0]` s
- **Variação de cor**: shift aleatório de `±30` nos canais RGB
- **Escala de gravidade**: uniforme em `[0.6, 1.2]` por partícula

---

## 🏗️ Arquitetura da Simulação

### Estrutura de Classes

```
┌─────────────────────────────────┐
│           main()                │
│  • Agenda de lançamentos        │
│  • Loop de simulação (240 fps)  │
│  • Renderização + exportação    │
└──────────┬──────────────────────┘
           │ gerencia
           ▼
┌─────────────────────────────────┐
│        Firework (Emissor)       │
│  • Foguete (partícula única)    │
│  • Lista de partículas[]        │
│  • Explosão radial              │
│  • Faíscas secundárias          │
└──────────┬──────────────────────┘
           │ contém N×
           ▼
┌─────────────────────────────────┐
│      Particle (Partícula)       │
│  • pos, vel (numpy arrays)      │
│  • cor_início, cor_fim          │
│  • life, max_life, size         │
│  • gravity_scale                │
│  • is_trail, is_spark           │
└─────────────────────────────────┘
```

### Pipeline de Renderização

```
Para cada frame:
  1. Preencher fundo (gradiente vertical)
  2. Coletar todas as partículas ativas
  3. Ordenar por camada (trails → partículas principais)
  4. Para cada partícula:
     a. Calcular cor + alpha interpolados
     b. Desenhar disco gaussiano com blend aditivo
  5. Sobrepor HUD (título, contador, frame)
  6. Armazenar frame no buffer
```

### Tipos de Partículas

| Tipo | Descrição | Vida (s) | Tamanho | Gravidade |
|------|-----------|----------|---------|-----------|
| **Foguete** | Sobe verticalmente antes de explodir | ~1.0–1.5 | 4.0 | 0.5× |
| **Rastro** (*trail*) | Emitido pelo foguete durante a subida | 0.3–0.6 | 1.5–2.5 | 0.3× |
| **Explosão** | Partícula principal da explosão | 0.8–2.0 | 2.0–4.0 | 0.6–1.2× |
| **Faísca** (*spark*) | Partícula rápida e brilhante | 0.4–0.9 | 1.5–2.5 | 0.8× |
| **Mini-faísca** | Emitida por faíscas (terciária) | 0.1–0.25 | 1.0 | 0.5× |

### Paletas de Cores

A simulação utiliza 7 paletas pré-definidas, cada uma com transição de cor ao longo da vida:

| # | Transição | Efeito Visual |
|---|-----------|---------------|
| 0 | 🔴 Vermelho → 🟡 Amarelo | Fogo clássico |
| 1 | 🔵 Azul → 🩵 Ciano | Gelo/elétrico |
| 2 | 🟢 Verde → Verde-claro | Natureza |
| 3 | 🟣 Magenta → 🩷 Rosa | Festivo |
| 4 | 🟡 Amarelo → 🟠 Laranja | Dourado |
| 5 | 🟣 Roxo → 🔵 Azul-claro | Galáxia |
| 6 | ⬜ Branco-quente → 🟠 Laranja | Incandescente |

---

## 🚀 Como Executar

### Pré-requisitos

- **Python 3.8+**
- **NumPy** — cálculos vetoriais
- **Pillow** — manipulação de imagens e geração do GIF
- **FFmpeg** — codificação do vídeo MP4 (opcional, mas recomendado)

### Instalação

```bash
# Clonar o repositório
git clone https://github.com/SEU_USUARIO/computacao-grafica-sistema-de-particulas.git
cd computacao-grafica-sistema-de-particulas

# Instalar dependências Python
pip install numpy Pillow

# Verificar FFmpeg (opcional — para saída MP4)
ffmpeg -version
```

### Execução

```bash
python3 particle_system.py
```

O script exibirá uma barra de progresso durante a renderização:

```
============================================================
  Computação Gráfica — Sistema de Partículas
  Gerando simulação de fogos de artifício...
  Resolução: 800×600  |  30 fps  |  8s
============================================================
  [██████████████████████████████████████████████████] 100.0%  frame 240/240  partículas:   758

  Salvando frames PNG...
  Codificando MP4 com ffmpeg...
  ✓ MP4 salvo em: particulas.mp4
  Codificando GIF...
  ✓ GIF salvo em: particulas.gif
  ✓ Frames temporários removidos
============================================================
```

### Saídas

| Arquivo | Formato | Tamanho | Qualidade |
|---------|---------|---------|-----------|
| `particulas.mp4` | H.264 (CRF 18) | ~1 MB | ⭐⭐⭐ Alta (cores 24-bit) |
| `particulas.gif` | GIF animado | ~3.5 MB | ⭐⭐ Média (256 cores) |

---

## ⚙️ Parâmetros Configuráveis

Os parâmetros globais podem ser ajustados no topo do arquivo `particle_system.py`:

```python
WIDTH, HEIGHT = 800, 600     # Resolução do vídeo
FPS = 30                      # Frames por segundo
DURATION_S = 8                # Duração total (segundos)
GRAVITY = np.array([0, 200])  # Vetor gravidade (px/s²)
DRAG = 0.98                   # Coeficiente de arrasto (0–1)
BG_COLOR = (8, 8, 20)         # Cor de fundo (RGB)
```

Para adicionar novos fogos, edite a lista `schedule` na função `main()`:

```python
# (tempo_s, posição_x, velocidade_lançamento, índice_paleta, tempo_fusível)
(2.0, 400, -430, 0, 1.0),
```

---

## 📂 Estrutura do Projeto

```
computacao-grafica-sistema-de-particulas/
├── particle_system.py   # Código-fonte principal
├── particulas.mp4       # Vídeo gerado (H.264)
├── particulas.gif       # GIF animado gerado
├── .gitignore
└── README.md            # Este arquivo
```

---

## 📚 Referências

1. **Reeves, W. T.** (1983). *"Particle Systems — A Technique for Modeling a Class of Fuzzy Objects."* ACM SIGGRAPH Computer Graphics, 17(3), 359–375.
2. **Sims, K.** (1990). *"Particle Animation and Rendering Using Data Parallel Computation."* ACM SIGGRAPH Computer Graphics, 24(4), 405–413.
3. **Lander, J.** (1998). *"The Ocean Spray in Your Face."* Game Developer Magazine — Uma introdução prática a sistemas de partículas para jogos.
4. **Nguyen, H.** (2007). *"GPU Gems 3 — Chapter 23: High-Speed, Off-Screen Particles."* NVIDIA Developer.

---

## 🛠️ Tecnologias Utilizadas

| Tecnologia | Uso |
|------------|-----|
| Python 3 | Linguagem principal |
| NumPy | Vetores de posição/velocidade e operações matemáticas |
| Pillow (PIL) | Manipulação de imagens e geração do GIF |
| FFmpeg | Codificação do vídeo MP4 (H.264) |
| **Claude Opus** | IA utilizada para gerar 100% do código e documentação |

---

## 📄 Licença

Este projeto é de uso livre para fins educacionais e acadêmicos.

---

<p align="center">
  <em>Feito com 🎆 e <a href="https://www.anthropic.com/claude">Claude Opus</a> (Anthropic)</em>
</p>
