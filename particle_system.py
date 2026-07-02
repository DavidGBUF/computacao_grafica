"""
Computação Gráfica — Sistema de Partículas
============================================
Simulação de fogos de artifício com múltiplos efeitos:
  • Emissores com lançamento vertical
  • Explosões radiais com distribuição gaussiana
  • Gravidade, arrasto e vento
  • Ciclo de vida (nascimento → atualização → morte)
  • Cor com gradiente temporal e fade-out (alpha)
  • Rastros (trails) persistentes
  • Faíscas secundárias

Gera um GIF animado (~8 s a 30 fps) e salva como 'particulas.gif'.

Dependências:  pip install numpy Pillow
"""

import math
import random
import struct
import zlib
from dataclasses import dataclass, field
from typing import List, Tuple

import numpy as np

# ──────────────────────── configuração global ────────────────────────

WIDTH, HEIGHT = 800, 600
FPS = 30
DURATION_S = 8
TOTAL_FRAMES = FPS * DURATION_S
GRAVITY = np.array([0.0, 200.0])        # px/s²  (y cresce para baixo)
DRAG = 0.98                              # coef. de arrasto por frame
BG_COLOR = (8, 8, 20)                    # fundo escuro azulado

# ──────────────────────── paletas de cores ───────────────────────────

PALETTES = [
    # (cor_inicio, cor_fim)  — RGB
    ((255, 80, 60),   (255, 200, 50)),   # vermelho → amarelo
    ((50, 180, 255),  (200, 240, 255)),  # azul → ciano
    ((100, 255, 100), (220, 255, 100)),  # verde → verde-claro
    ((255, 100, 255), (255, 200, 220)),  # magenta → rosa
    ((255, 200, 50),  (255, 100, 30)),   # amarelo → laranja
    ((180, 120, 255), (100, 200, 255)),  # roxo → azul-claro
    ((255, 255, 200), (255, 160, 60)),   # branco-quente → laranja
]


# ──────────────────────── partícula ──────────────────────────────────

@dataclass
class Particle:
    pos: np.ndarray             # [x, y]
    vel: np.ndarray             # [vx, vy]  px/s
    color_start: Tuple[int, int, int] = (255, 255, 255)
    color_end:   Tuple[int, int, int] = (255, 100, 30)
    life: float = 1.0           # vida restante (1 → 0)
    max_life: float = 1.0       # vida total em segundos
    size: float = 3.0
    is_trail: bool = False
    is_spark: bool = False
    gravity_scale: float = 1.0

    def alive(self) -> bool:
        return self.life > 0

    def update(self, dt: float):
        # física
        acc = GRAVITY * self.gravity_scale
        self.vel = self.vel + acc * dt
        self.vel *= DRAG
        self.pos = self.pos + self.vel * dt
        # vida
        self.life -= dt / self.max_life
        if self.life < 0:
            self.life = 0

    def current_color_alpha(self) -> Tuple[int, int, int, int]:
        t = 1.0 - self.life          # 0 → 1 ao longo da vida
        r = int(self.color_start[0] + (self.color_end[0] - self.color_start[0]) * t)
        g = int(self.color_start[1] + (self.color_end[1] - self.color_start[1]) * t)
        b = int(self.color_start[2] + (self.color_end[2] - self.color_start[2]) * t)
        # alpha com ease-out
        alpha = int(255 * (self.life ** 0.6))
        return (min(max(r, 0), 255),
                min(max(g, 0), 255),
                min(max(b, 0), 255),
                min(max(alpha, 0), 255))


# ──────────────────────── emissor (firework) ─────────────────────────

@dataclass
class Firework:
    """Um foguete que sobe e depois explode."""
    x: float
    launch_vel: float            # vel. vertical inicial (negativa = para cima)
    palette_idx: int
    fuse_time: float             # tempo até a explosão (s)
    exploded: bool = False
    rocket: Particle = field(init=False)
    particles: List[Particle] = field(default_factory=list)
    timer: float = 0.0
    num_explosion: int = 120
    num_sparks: int = 30

    def __post_init__(self):
        c_start, c_end = PALETTES[self.palette_idx % len(PALETTES)]
        self.rocket = Particle(
            pos=np.array([self.x, float(HEIGHT + 10)]),
            vel=np.array([random.uniform(-20, 20), self.launch_vel]),
            color_start=(255, 255, 220),
            color_end=(255, 200, 100),
            max_life=self.fuse_time + 0.5,
            life=1.0,
            size=4.0,
            gravity_scale=0.5,
        )

    def update(self, dt: float):
        self.timer += dt

        if not self.exploded:
            self.rocket.update(dt)
            # rastro do foguete
            if random.random() < 0.7:
                trail = Particle(
                    pos=self.rocket.pos.copy() + np.random.uniform(-2, 2, 2),
                    vel=np.array([random.uniform(-15, 15),
                                  random.uniform(20, 60)]),
                    color_start=(255, 220, 150),
                    color_end=(255, 100, 30),
                    max_life=random.uniform(0.3, 0.6),
                    life=1.0,
                    size=random.uniform(1.5, 2.5),
                    is_trail=True,
                    gravity_scale=0.3,
                )
                self.particles.append(trail)

            # hora de explodir?
            if self.timer >= self.fuse_time:
                self._explode()

        # atualiza partículas existentes
        for p in self.particles:
            p.update(dt)
            # faíscas secundárias
            if p.is_spark and random.random() < 0.15:
                mini = Particle(
                    pos=p.pos.copy(),
                    vel=p.vel * 0.2 + np.random.uniform(-10, 10, 2),
                    color_start=p.color_start,
                    color_end=p.color_end,
                    max_life=random.uniform(0.1, 0.25),
                    life=1.0,
                    size=1.0,
                    is_trail=True,
                    gravity_scale=0.5,
                )
                self.particles.append(mini)

        # remove mortas
        self.particles = [p for p in self.particles if p.alive()]

    def _explode(self):
        self.exploded = True
        self.rocket.life = 0
        cx, cy = self.rocket.pos
        c_start, c_end = PALETTES[self.palette_idx % len(PALETTES)]

        # partículas principais — distribuição esférica
        for _ in range(self.num_explosion):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.gauss(180, 60)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed
            life = random.uniform(0.8, 2.0)
            # variação de cor
            shift = random.randint(-30, 30)
            cs = tuple(min(max(c + shift, 0), 255) for c in c_start)
            ce = tuple(min(max(c + shift, 0), 255) for c in c_end)
            p = Particle(
                pos=np.array([cx, cy]) + np.random.uniform(-3, 3, 2),
                vel=np.array([vx, vy]),
                color_start=cs,
                color_end=ce,
                max_life=life,
                life=1.0,
                size=random.uniform(2.0, 4.0),
                gravity_scale=random.uniform(0.6, 1.2),
            )
            self.particles.append(p)

        # faíscas extras (mais brilhantes, mais rápidas)
        for _ in range(self.num_sparks):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.gauss(250, 80)
            p = Particle(
                pos=np.array([cx, cy]),
                vel=np.array([math.cos(angle) * speed, math.sin(angle) * speed]),
                color_start=(255, 255, 240),
                color_end=c_end,
                max_life=random.uniform(0.4, 0.9),
                life=1.0,
                size=random.uniform(1.5, 2.5),
                is_spark=True,
                gravity_scale=0.8,
            )
            self.particles.append(p)

    def done(self) -> bool:
        return self.exploded and len(self.particles) == 0


# ──────────────────────── renderização em buffer RGBA ─────────────────

def render_frame(fireworks: List[Firework], frame_idx: int) -> np.ndarray:
    """Renderiza um frame como array RGBA uint8 (HEIGHT, WIDTH, 4)."""
    # fundo com leve gradiente vertical
    buf = np.zeros((HEIGHT, WIDTH, 4), dtype=np.uint8)
    for y in range(HEIGHT):
        t = y / HEIGHT
        r = int(BG_COLOR[0] * (1 - t * 0.3))
        g = int(BG_COLOR[1] * (1 - t * 0.3))
        b = int(BG_COLOR[2] + 15 * t)
        buf[y, :, 0] = r
        buf[y, :, 1] = g
        buf[y, :, 2] = min(b, 255)
        buf[y, :, 3] = 255

    # desenha partículas (ordem: trails primeiro, depois principais)
    all_particles: List[Particle] = []
    for fw in fireworks:
        if not fw.exploded and fw.rocket.alive():
            all_particles.append(fw.rocket)
        all_particles.extend(fw.particles)

    # ordena: trails/sparks primeiro (ficam atrás)
    all_particles.sort(key=lambda p: (0 if p.is_trail else 1))

    for p in all_particles:
        px, py = int(p.pos[0]), int(p.pos[1])
        if px < -10 or px >= WIDTH + 10 or py < -10 or py >= HEIGHT + 10:
            continue

        r, g, b, a = p.current_color_alpha()
        radius = max(1, int(p.size * (0.4 + 0.8 * p.life)))
        af = a / 255.0

        # glow externo (halo suave) — raio maior, intensidade menor
        glow_radius = radius + 2
        for dy in range(-glow_radius - 1, glow_radius + 2):
            for dx in range(-glow_radius - 1, glow_radius + 2):
                dist = math.sqrt(dx * dx + dy * dy)
                if dist > glow_radius + 0.5:
                    continue
                ix, iy = px + dx, py + dy
                if 0 <= ix < WIDTH and 0 <= iy < HEIGHT:
                    # intensidade gaussiana — núcleo brilhante + halo
                    sigma = max(radius * 0.45, 0.5)
                    core = math.exp(-0.5 * (dist / sigma) ** 2) * af
                    halo = math.exp(-0.5 * (dist / (sigma * 2.5)) ** 2) * af * 0.3
                    intensity = min(core + halo, 1.0)
                    # blend aditivo (clamp a 255)
                    buf[iy, ix, 0] = min(int(buf[iy, ix, 0] + r * intensity), 255)
                    buf[iy, ix, 1] = min(int(buf[iy, ix, 1] + g * intensity), 255)
                    buf[iy, ix, 2] = min(int(buf[iy, ix, 2] + b * intensity), 255)

    return buf


# ──────────────────────── gerador de GIF (puro Python) ───────────────

def _write_gif(frames_rgb: List[np.ndarray], filename: str, fps: int = 30):
    """Escreve GIF animado usando Pillow."""
    from PIL import Image

    images = []
    for frame in frames_rgb:
        img = Image.fromarray(frame[:, :, :3], 'RGB')
        images.append(img.quantize(colors=256, method=2, dither=1))

    delay = int(1000 / fps)
    images[0].save(
        filename,
        save_all=True,
        append_images=images[1:],
        duration=delay,
        loop=0,
        optimize=False,
    )


# ──────────────────────── título / HUD sobreposto ────────────────────

def draw_text_overlay(buf: np.ndarray, frame_idx: int):
    """Desenha textos simples usando bitmap (sem dependência de fontes).
    Desenha um retângulo com texto minimalista no topo."""
    # barra superior semi-transparente
    bar_h = 36
    for y in range(bar_h):
        for x in range(WIDTH):
            # blend multiplicativo
            buf[y, x, 0] = int(buf[y, x, 0] * 0.3)
            buf[y, x, 1] = int(buf[y, x, 1] * 0.3)
            buf[y, x, 2] = int(buf[y, x, 2] * 0.3)

    # Texto bitmap simples: "SISTEMA DE PARTICULAS"
    # Cada caractere é 5×7 pixels
    FONT = _get_bitmap_font()
    text = "SISTEMA DE PARTICULAS"
    char_w, char_h = 6, 8
    total_w = len(text) * char_w
    start_x = (WIDTH - total_w) // 2
    start_y = (bar_h - char_h) // 2

    for i, ch in enumerate(text):
        if ch not in FONT:
            continue
        glyph = FONT[ch]
        for gy in range(min(7, len(glyph))):
            row = glyph[gy]
            for gx in range(5):
                if row & (1 << (4 - gx)):
                    px = start_x + i * char_w + gx
                    py = start_y + gy
                    if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                        buf[py, px, 0] = 220
                        buf[py, px, 1] = 230
                        buf[py, px, 2] = 255
                        buf[py, px, 3] = 255

    # Contador de partículas no canto inferior
    return buf


def _get_bitmap_font():
    """Fonte bitmap 5×7 para caracteres maiúsculos + espaço."""
    return {
        'A': [0b01110, 0b10001, 0b10001, 0b11111, 0b10001, 0b10001, 0b10001],
        'B': [0b11110, 0b10001, 0b10001, 0b11110, 0b10001, 0b10001, 0b11110],
        'C': [0b01110, 0b10001, 0b10000, 0b10000, 0b10000, 0b10001, 0b01110],
        'D': [0b11110, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b11110],
        'E': [0b11111, 0b10000, 0b10000, 0b11110, 0b10000, 0b10000, 0b11111],
        'F': [0b11111, 0b10000, 0b10000, 0b11110, 0b10000, 0b10000, 0b10000],
        'G': [0b01110, 0b10001, 0b10000, 0b10111, 0b10001, 0b10001, 0b01110],
        'H': [0b10001, 0b10001, 0b10001, 0b11111, 0b10001, 0b10001, 0b10001],
        'I': [0b01110, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b01110],
        'J': [0b00111, 0b00010, 0b00010, 0b00010, 0b00010, 0b10010, 0b01100],
        'K': [0b10001, 0b10010, 0b10100, 0b11000, 0b10100, 0b10010, 0b10001],
        'L': [0b10000, 0b10000, 0b10000, 0b10000, 0b10000, 0b10000, 0b11111],
        'M': [0b10001, 0b11011, 0b10101, 0b10101, 0b10001, 0b10001, 0b10001],
        'N': [0b10001, 0b11001, 0b10101, 0b10011, 0b10001, 0b10001, 0b10001],
        'O': [0b01110, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01110],
        'P': [0b11110, 0b10001, 0b10001, 0b11110, 0b10000, 0b10000, 0b10000],
        'Q': [0b01110, 0b10001, 0b10001, 0b10001, 0b10101, 0b01110, 0b00001],
        'R': [0b11110, 0b10001, 0b10001, 0b11110, 0b10100, 0b10010, 0b10001],
        'S': [0b01110, 0b10001, 0b10000, 0b01110, 0b00001, 0b10001, 0b01110],
        'T': [0b11111, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100],
        'U': [0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01110],
        'V': [0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01010, 0b00100],
        'W': [0b10001, 0b10001, 0b10001, 0b10101, 0b10101, 0b11011, 0b10001],
        'X': [0b10001, 0b10001, 0b01010, 0b00100, 0b01010, 0b10001, 0b10001],
        'Y': [0b10001, 0b10001, 0b01010, 0b00100, 0b00100, 0b00100, 0b00100],
        'Z': [0b11111, 0b00001, 0b00010, 0b00100, 0b01000, 0b10000, 0b11111],
        ' ': [0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b00000],
        '0': [0b01110, 0b10001, 0b10011, 0b10101, 0b11001, 0b10001, 0b01110],
        '1': [0b00100, 0b01100, 0b00100, 0b00100, 0b00100, 0b00100, 0b01110],
        '2': [0b01110, 0b10001, 0b00001, 0b00110, 0b01000, 0b10000, 0b11111],
        '3': [0b01110, 0b10001, 0b00001, 0b00110, 0b00001, 0b10001, 0b01110],
        '4': [0b00010, 0b00110, 0b01010, 0b10010, 0b11111, 0b00010, 0b00010],
        '5': [0b11111, 0b10000, 0b11110, 0b00001, 0b00001, 0b10001, 0b01110],
        '6': [0b01110, 0b10000, 0b10000, 0b11110, 0b10001, 0b10001, 0b01110],
        '7': [0b11111, 0b00001, 0b00010, 0b00100, 0b01000, 0b01000, 0b01000],
        '8': [0b01110, 0b10001, 0b10001, 0b01110, 0b10001, 0b10001, 0b01110],
        '9': [0b01110, 0b10001, 0b10001, 0b01111, 0b00001, 0b00001, 0b01110],
        ':': [0b00000, 0b00100, 0b00000, 0b00000, 0b00100, 0b00000, 0b00000],
    }


# ──────────────────────── HUD de informações ─────────────────────────

def draw_hud(buf: np.ndarray, frame_idx: int, total_particles: int):
    """Desenha informações do HUD na parte inferior."""
    FONT = _get_bitmap_font()
    char_w, char_h = 6, 8

    # Texto: "PARTICULAS: XXXX"
    text = f"PARTICULAS: {total_particles}"
    start_x = 12
    start_y = HEIGHT - 18

    # Fundo semi-transparente
    for y in range(start_y - 3, min(start_y + char_h + 3, HEIGHT)):
        for x in range(start_x - 4, min(start_x + len(text) * char_w + 4, WIDTH)):
            if 0 <= x < WIDTH and 0 <= y < HEIGHT:
                buf[y, x, 0] = int(buf[y, x, 0] * 0.4)
                buf[y, x, 1] = int(buf[y, x, 1] * 0.4)
                buf[y, x, 2] = int(buf[y, x, 2] * 0.4)

    for i, ch in enumerate(text):
        if ch not in FONT:
            continue
        glyph = FONT[ch]
        for gy in range(min(7, len(glyph))):
            row = glyph[gy]
            for gx in range(5):
                if row & (1 << (4 - gx)):
                    px = start_x + i * char_w + gx
                    py = start_y + gy
                    if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                        buf[py, px, 0] = 180
                        buf[py, px, 1] = 200
                        buf[py, px, 2] = 220

    # Frame counter
    text2 = f"FRAME: {frame_idx:03d}"
    start_x2 = WIDTH - len(text2) * char_w - 12
    start_y2 = HEIGHT - 18

    for y in range(start_y2 - 3, min(start_y2 + char_h + 3, HEIGHT)):
        for x in range(start_x2 - 4, min(start_x2 + len(text2) * char_w + 4, WIDTH)):
            if 0 <= x < WIDTH and 0 <= y < HEIGHT:
                buf[y, x, 0] = int(buf[y, x, 0] * 0.4)
                buf[y, x, 1] = int(buf[y, x, 1] * 0.4)
                buf[y, x, 2] = int(buf[y, x, 2] * 0.4)

    for i, ch in enumerate(text2):
        if ch not in FONT:
            continue
        glyph = FONT[ch]
        for gy in range(min(7, len(glyph))):
            row = glyph[gy]
            for gx in range(5):
                if row & (1 << (4 - gx)):
                    px = start_x2 + i * char_w + gx
                    py = start_y2 + gy
                    if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                        buf[py, px, 0] = 180
                        buf[py, px, 1] = 200
                        buf[py, px, 2] = 220


# ──────────────────────── loop principal ─────────────────────────────

def main():
    print("=" * 60)
    print("  Computação Gráfica — Sistema de Partículas")
    print("  Gerando simulação de fogos de artifício...")
    print(f"  Resolução: {WIDTH}×{HEIGHT}  |  {FPS} fps  |  {DURATION_S}s")
    print("=" * 60)

    random.seed(42)
    np.random.seed(42)

    # agenda de lançamentos  (tempo_s, x, vel_lancamento, paleta, fuse)
    schedule = [
        (0.2,  400, -420, 0, 1.0),
        (0.8,  250, -380, 1, 1.1),
        (1.0,  580, -400, 2, 0.9),
        (1.8,  350, -450, 3, 1.0),
        (2.2,  650, -390, 4, 1.1),
        (2.5,  150, -410, 5, 0.8),
        (3.0,  400, -430, 6, 1.0),
        (3.3,  550, -400, 0, 0.9),
        (3.8,  200, -420, 2, 1.0),
        (4.2,  450, -440, 1, 1.1),
        (4.5,  300, -390, 4, 0.9),
        (4.8,  600, -410, 3, 1.0),
        (5.2,  350, -450, 5, 0.8),
        (5.5,  500, -400, 6, 1.0),
        (5.8,  180, -420, 0, 0.9),
        (6.2,  420, -430, 2, 1.0),
        (6.5,  280, -410, 4, 1.1),
        (6.8,  620, -440, 1, 0.9),
        (7.0,  400, -460, 3, 0.8),
    ]

    fireworks: List[Firework] = []
    schedule_idx = 0
    dt = 1.0 / FPS
    frames = []

    for frame_i in range(TOTAL_FRAMES):
        current_time = frame_i * dt

        # lançar novos fogos conforme agenda
        while schedule_idx < len(schedule) and schedule[schedule_idx][0] <= current_time:
            t, x, vel, pal, fuse = schedule[schedule_idx]
            fw = Firework(
                x=x,
                launch_vel=vel,
                palette_idx=pal,
                fuse_time=fuse,
                num_explosion=random.randint(100, 160),
                num_sparks=random.randint(20, 40),
            )
            fireworks.append(fw)
            schedule_idx += 1

        # atualizar física
        for fw in fireworks:
            fw.update(dt)

        # remover fogos terminados
        fireworks = [fw for fw in fireworks if not fw.done()]

        # renderizar
        buf = render_frame(fireworks, frame_i)

        # overlay de texto
        draw_text_overlay(buf, frame_i)

        # contar partículas
        total_p = sum(
            len(fw.particles) + (1 if not fw.exploded and fw.rocket.alive() else 0)
            for fw in fireworks
        )
        draw_hud(buf, frame_i, total_p)

        frames.append(buf)

        # progresso
        pct = (frame_i + 1) / TOTAL_FRAMES * 100
        bar = "█" * int(pct / 2) + "░" * (50 - int(pct / 2))
        print(f"\r  [{bar}] {pct:5.1f}%  frame {frame_i + 1}/{TOTAL_FRAMES}"
              f"  partículas: {total_p:5d}", end="", flush=True)

    print("\n")

    base_dir = "/home/david/projects/computacao_grafica"

    # ── Salvar frames como PNG para ffmpeg ──
    import os
    import subprocess

    frames_dir = os.path.join(base_dir, "_frames")
    os.makedirs(frames_dir, exist_ok=True)

    print("  Salvando frames PNG...")
    from PIL import Image as PILImage
    for i, frame in enumerate(frames):
        img = PILImage.fromarray(frame[:, :, :3])
        img.save(os.path.join(frames_dir, f"frame_{i:04d}.png"))

    # ── Gerar MP4 via ffmpeg ──
    mp4_path = os.path.join(base_dir, "particulas.mp4")
    print("  Codificando MP4 com ffmpeg...")
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-framerate", str(FPS),
        "-i", os.path.join(frames_dir, "frame_%04d.png"),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "18",
        "-preset", "medium",
        mp4_path,
    ]
    subprocess.run(ffmpeg_cmd, capture_output=True, check=True)
    print(f"  ✓ MP4 salvo em: {mp4_path}")

    # ── Gerar GIF também ──
    print("  Codificando GIF...")
    gif_path = os.path.join(base_dir, "particulas.gif")
    _write_gif(frames, gif_path, fps=FPS)
    print(f"  ✓ GIF salvo em: {gif_path}")

    # ── Limpar frames temporários ──
    import shutil
    shutil.rmtree(frames_dir, ignore_errors=True)
    print("  ✓ Frames temporários removidos")

    print("=" * 60)


if __name__ == "__main__":
    main()
