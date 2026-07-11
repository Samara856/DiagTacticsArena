# audio.py
import math
import array
import pygame

class SFX:
    def __init__(self):
        self.enabled = True
        self.ready = False
        self.snd_click = None
        self.snd_drop = None
        self.snd_win = None

    def init(self):
        if self.ready:
            return
        try:
            pygame.mixer.pre_init(44100, -16, 1, 512)
            pygame.mixer.init()
        except Exception:
            self.enabled = False
            self.ready = True
            return

        self.snd_click = self._tone(freq=740, ms=60, vol=0.25)
        self.snd_drop  = self._tone(freq=460, ms=110, vol=0.30)
        self.snd_win   = self._chord([(660, 160), (880, 160), (990, 220)], vol=0.28)

        self.ready = True

    def _tone(self, freq=440, ms=120, vol=0.3, sample_rate=44100):
        n = int(sample_rate * (ms / 1000.0))
        buf = array.array("h")
        attack = int(0.08 * n)
        decay = int(0.20 * n)
        for i in range(n):
            t = i / sample_rate
            s = math.sin(2 * math.pi * freq * t)
            # simple envelope
            if i < attack:
                env = i / max(1, attack)
            elif i > n - decay:
                env = (n - i) / max(1, decay)
            else:
                env = 1.0
            val = int(32767 * vol * env * s)
            buf.append(val)
        return pygame.mixer.Sound(buffer=buf.tobytes())

    def _chord(self, notes, vol=0.28, sample_rate=44100):
        # returns list of sounds
        return [self._tone(f, ms, vol=vol, sample_rate=sample_rate) for f, ms in notes]

    def click(self):
        if not self.enabled:
            return
        self.init()
        if self.snd_click:
            self.snd_click.play()

    def drop(self):
        if not self.enabled:
            return
        self.init()
        if self.snd_drop:
            self.snd_drop.play()

    def win(self):
        if not self.enabled:
            return
        self.init()
        if self.snd_win:
            for s in self.snd_win:
                s.play()