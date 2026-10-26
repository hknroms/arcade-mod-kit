"""romkit — アーケード ROM の改造を組み立てる共通の道具（CPU は問わない。hknroms/gradius3 の g3build.py を一般化したもの）

ROM の並べ方（title.json の cpus.<名前>.groups）:
  - 1本で1つの CPU 空間（Z80・6809・6502 など 8bit 機に多い）      → [["prog.bin"]]
  - 2本を1バイトずつ交互（68000 など 16bit 機の偶数・奇数）        → [["even.bin", "odd.bin"]]
  - 4本を1バイトずつ交互（32bit 機）                                → [["b0.bin", "b1.bin", "b2.bin", "b3.bin"]]
  - 16bit 単位で交互に並べる基板は  {"files": [...], "width": 2}
  - 複数の組は順に後ろへつなぐ（バンク・上位の ROM）                → [["a0","a1"], ["b0","b1"]]
  旧形式の "pairs": [[even, odd], ...] もそのまま読める。

使い方の例:
    import romkit
    rom = romkit.Rom.from_title()                     # title.json と環境変数 ROMBASE から純正ROMを読む
    rom.put('main', 0x3fd9a, code, 'mycode')            # 空き（元が 0x00 か 0xff 一色）の所にだけ書ける
    rom.put('main', 0x4c2, new, 'ptr', expect=old)      # 元のバイトを確かめて書き換え（版違いの ROM への当て間違いを防ぐ）
    lab, n = rom.asm('main', 0x3fd9a, src, 'mycode')    # アセンブルして置く（CPU ごとのアセンブラ。68000 は asm68）
    s0 = romkit.lane_sums(rom.orig['main'], 2)          # 改造前の、レーンごとの合計
    romkit.lane_fix(rom.img('main'), s0, [(0x3ffe0, 0x3fff0)], 2)   # 合計を元に戻す（8bit 機は lanes=1）
    rom.write('out/')                                  # 元のファイル名・並べ方で書き出す

- どこに何を書いたかを覚え、重なったら止める。report() で一覧。
- ROM の中身はリポジトリに入れない。純正ROMは会話に添付してもらい、ROMBASE に置く。
"""
import os, sys, json, zlib, importlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# CPU の種類 → アセンブラのモジュール（tools/ に置く。assemble(src, org, labels) -> (bytes, labels) の形）
ASSEMBLERS = {'68000': 'asm68', '68010': 'asm68', '68020': 'asm68', '68ec020': 'asm68'}


def crc(b: bytes) -> str:
    return '%08x' % zlib.crc32(b)


def interleave(files, width=1) -> bytearray:
    """複数の ROM を width バイトずつ交互に並べて1本にする（files が1本ならそのまま）"""
    if len(files) == 1: return bytearray(files[0])
    n = len(files[0]); assert all(len(f) == n for f in files), 'ROM の長さがそろっていない'
    out = bytearray()
    for i in range(0, n, width):
        for f in files: out += f[i:i + width]
    return out


def deinterleave(buf: bytes, count, width=1):
    """interleave の逆。count 本に分ける"""
    if count == 1: return [bytes(buf)]
    step = count * width
    return [b''.join(buf[i + k * width:i + k * width + width] for i in range(0, len(buf), step)) for k in range(count)]


# 互換: 2本（偶数・奇数）
def il(even: bytes, odd: bytes) -> bytearray: return interleave([even, odd])
def split(buf: bytes): return tuple(deinterleave(buf, 2))


def lane_sums(buf: bytes, lanes=2):
    """レーンごと（lanes 本の ROM ごと）のバイトの合計。多くの基板の起動時 ROM チェックはこの形（8bit 機は lanes=1）"""
    return [sum(buf[k::lanes]) for k in range(lanes)]


def lane_fix(buf: bytearray, want, ranges, lanes=2, start=0x80):
    """ranges（[(lo, hi), ...]、hi は含まない）のバイトを調整して、各レーンの合計を want（リスト）に合わせる。
    調整に使うバイトは start（既定 0x80）から始めて 0〜255 の範囲で動かす。足りなければ AssertionError。
    16bit・32bit の合計で比べる基板や、CRC で比べる基板は別の直し方が要る（docs/knowhow/03）"""
    if isinstance(want, int): want = [want]
    fill = [a for lo, hi in ranges for a in range(lo, hi)]
    for a in fill: buf[a] = start
    for lane in range(lanes):
        diff = want[lane] - sum(buf[lane::lanes])
        for a in (a for a in fill if a % lanes == lane):
            step = max(-buf[a], min(255 - buf[a], diff)); buf[a] += step; diff -= step
        assert diff == 0, f'調整用のバイトが足りない（lane {lane}, 残り {diff}）。ranges を広げる'
    return buf


def _groups(c):
    """title.json の cpu の定義 → [(ファイル名のリスト, width), ...]"""
    gs = c.get('groups') or c.get('pairs') or []
    out = []
    for g in gs:
        if isinstance(g, dict): out.append((list(g['files']), int(g.get('width', 1))))
        else: out.append((list(g), 1))
    return out


class Rom:
    def __init__(self, images: dict, layout: dict = None, arch: dict = None):
        """images = {'main': bytes(並べた後), ...}
        layout = {'main': [(ファイル名のリスト, width), ...]}（write() で元の形に戻すのに使う）
        arch = {'main': '68000', 'sound': 'z80', ...}"""
        self.cur = {k: bytearray(v) for k, v in images.items()}
        self.orig = {k: bytes(v) for k, v in images.items()}
        self.layout = layout or {}
        self.arch = arch or {}
        self.used = []        # (cpu, start, end, tag)

    @classmethod
    def from_title(cls, base=None, title=None):
        t = json.load(open(title or os.path.join(REPO, 'title.json'), encoding='utf-8'))
        base = base or os.environ.get('ROMBASE', os.path.join(REPO, 'rom'))
        images, layout, arch = {}, {}, {}
        for cpu, c in t['cpus'].items():
            if cpu.startswith('_'): continue
            buf = bytearray(); lay = _groups(c)
            for files, width in lay:
                buf += interleave([open(os.path.join(base, f), 'rb').read() for f in files], width)
            images[cpu] = buf; layout[cpu] = lay; arch[cpu] = str(c.get('arch', '')).lower()
        return cls(images, layout, arch)

    def img(self, cpu): return self.cur[cpu]

    def is_free(self, cpu, addr, n):
        cur = self.orig[cpu][addr:addr + n]
        return len(set(cur)) == 1 and cur[0] in (0, 0xff)

    def put(self, cpu, addr, data, tag='', expect=None, free_ok=False):
        o = self.orig[cpu]
        assert addr + len(data) <= len(o), f'{cpu}:{addr:x}+{len(data)} が ROM の外 ({tag})'
        cur = bytes(o[addr:addr + len(data)])
        if expect is not None:
            assert cur == bytes(expect), f'{cpu}:{addr:x} 元のバイトが違う {cur.hex()} != {bytes(expect).hex()} ({tag})'
        elif not free_ok:
            assert self.is_free(cpu, addr, len(data)), f'{cpu}:{addr:x} は空きではない ({tag}) {cur[:8].hex()}'
        for (c, s, e, t) in self.used:
            if c == cpu and s < addr + len(data) and addr < e:
                raise AssertionError(f'重なり {cpu}:{addr:x}+{len(data)} と {t} ({tag})')
        self.used.append((cpu, addr, addr + len(data), tag))
        self.cur[cpu][addr:addr + len(data)] = data

    def asm(self, cpu, org, src, tag='', labels=None, expect=None, free_ok=False, arch=None):
        """CPU に合ったアセンブラでアセンブルして置く。アセンブラが無い CPU は、外で作ったバイト列を put() で置く"""
        a = (arch or self.arch.get(cpu) or '68000').lower()
        mod = ASSEMBLERS.get(a) or ('asm_' + a)
        try: m = importlib.import_module(mod)
        except ImportError: raise SystemExit(f'{a} のアセンブラ（tools/{mod}.py）がありません。docs/knowhow/09-cpus.md を参照')
        b, lab = m.assemble(src, org, labels)
        self.put(cpu, org, b, tag, expect=expect, free_ok=free_ok)
        return lab, len(b)

    def report(self):
        """書いた場所の一覧（アドレス順）"""
        return '\n'.join(f'{c:6s} {s:06x}-{e:06x} {e - s:5d}B {t}' for c, s, e, t in sorted(self.used))

    def write(self, outdir):
        """元のファイル名・並べ方で書き出す。{ファイル名: CRC} を返す"""
        os.makedirs(outdir, exist_ok=True)
        out = {}
        for cpu, buf in self.cur.items():
            off = 0
            for files, width in self.layout.get(cpu, []):
                size = len(buf) // len(self.layout[cpu])
                for name, data in zip(files, deinterleave(buf[off:off + size], len(files), width)):
                    open(os.path.join(outdir, name), 'wb').write(data); out[name] = crc(data)
                off += size
        return out


if __name__ == '__main__':   # 自己テスト: python3 tools/romkit.py
    import tempfile
    # 16bit（2本）
    even = bytes([0x00] * 32 + [0x40] * 32); odd = bytes([0x00] * 32 + [0x40] * 32)   # 前半は空き(0x00)、後半は中身
    r = Rom({'main': il(even, odd)}, {'main': [(['e.bin', 'o.bin'], 1)]}, {'main': '68000'})
    s0 = lane_sums(r.img('main'))
    r.put('main', 0x10, b'\x4e\x75', 'rts')
    try: r.put('main', 0x11, b'\x00', 'overlap'); raise SystemExit('重なりを検出できていない')
    except AssertionError: pass
    lane_fix(r.img('main'), s0, [(0x70, 0x80)])
    assert lane_sums(r.img('main')) == s0
    r.asm('main', 0x20, 'start:\n        moveq   #1,d0\n        rts\n', 'asm')
    # 8bit（1本）と 32bit（4本）・16bit 単位の並べ方の往復
    z = Rom({'snd': bytearray([0] * 16 + [0x40] * 48)}, {'snd': [(['s.bin'], 1)]}, {'snd': 'z80'})
    z0 = lane_sums(z.img('snd'), 1)
    z.put('snd', 0x08, b'\xc9', 'ret'); lane_fix(z.img('snd'), z0, [(0x30, 0x34)], lanes=1)
    assert lane_sums(z.img('snd'), 1) == z0
    four = [bytes([k] * 8) for k in range(4)]
    assert deinterleave(interleave(four), 4) == four
    w2 = [bytes(range(8)), bytes(range(8, 16))]
    assert deinterleave(interleave(w2, 2), 2, 2) == w2
    with tempfile.TemporaryDirectory() as d: print(r.write(d), z.write(d))
    print(r.report()); print('romkit OK')
