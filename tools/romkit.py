"""romkit — 68000 系アーケード ROM の改造を組み立てる共通の道具（hknroms/gradius3 の g3build.py を一般化したもの）

使い方の例:
    import romkit, asm68
    rom = romkit.Rom.from_title()                 # title.json と環境変数 ROMBASE から純正ROMを読む
    rom.put('main', 0x3fd9a, code, 'mycode')        # 空き領域（0x00 か 0xff だけの所）にだけ書ける
    rom.put('main', 0x4c2, b'\\x00\\x03\\xff\\xc0', 'ptr', expect=bytes.fromhex('0000052e'))  # 元のバイトを確かめて書き換え
    lab, n = rom.asm('main', 0x3fd9a, src, 'mycode')  # アセンブルして置く
    romkit.lane_fix(rom.img('main'), even0, odd0, [(0x3ffe0, 0x3fff0)])  # 偶数・奇数バイトの合計を元に戻す
    rom.write('out/')                              # 偶数・奇数に分けて書き出す

- どこに何を書いたかを覚え、重なったら止める（overlap）。
- 純正と1バイトも変えていない領域を、うっかり「空き」扱いしない（元が 0x00/0xff 一色のときだけ空き）。
- ROM の中身はリポジトリに入れない。純正ROMは会話に添付してもらい、ROMBASE に置く。
"""
import os, sys, json, struct, zlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def il(even: bytes, odd: bytes) -> bytearray:
    """偶数バイトと奇数バイトのファイルを交互に並べて1本にする"""
    assert len(even) == len(odd), 'even/odd の長さが違う'
    return bytearray(x for p in zip(even, odd) for x in p)


def split(buf: bytes):
    """1本を偶数バイト・奇数バイトに分ける"""
    return bytes(buf[0::2]), bytes(buf[1::2])


def crc(b: bytes) -> str:
    return '%08x' % zlib.crc32(b)


def lane_sums(buf: bytes):
    """(偶数バイトの合計, 奇数バイトの合計)。多くの基板の起動時 ROM チェックはこの形"""
    return sum(buf[0::2]), sum(buf[1::2])


def lane_fix(buf: bytearray, want_even: int, want_odd: int, ranges, start=0x80):
    """ranges（[(lo, hi), ...]、hi は含まない）のバイトを調整して、偶数・奇数の合計を want に合わせる。
    調整に使うバイトは start（既定 0x80）から始めて ±255 の範囲で動かす。足りなければ AssertionError"""
    fill = [a for lo, hi in ranges for a in range(lo, hi)]
    for a in fill: buf[a] = start
    for lane, want in ((0, want_even), (1, want_odd)):
        diff = want - sum(buf[lane::2])
        for a in (a for a in fill if a % 2 == lane):
            step = max(-buf[a], min(255 - buf[a], diff)); buf[a] += step; diff -= step
        assert diff == 0, f'調整用のバイトが足りない（lane {lane}, 残り {diff}）。ranges を広げる'
    return buf


class Rom:
    def __init__(self, images: dict, names: dict = None):
        """images = {'main': bytes(インターリーブ済み), ...}、names = {'main': [(even名, odd名), ...]}"""
        self.cur = {k: bytearray(v) for k, v in images.items()}
        self.orig = {k: bytes(v) for k, v in images.items()}
        self.names = names or {}
        self.used = []        # (cpu, start, end, tag)

    @classmethod
    def from_title(cls, base=None, title=None):
        """title.json の cpus.*.pairs を、ROMBASE（既定 ./rom）から読む。1組のときはそのまま、複数組は順に連結"""
        t = json.load(open(title or os.path.join(REPO, 'title.json'), encoding='utf-8'))
        base = base or os.environ.get('ROMBASE', os.path.join(REPO, 'rom'))
        images, names = {}, {}
        for cpu, c in t['cpus'].items():
            buf = bytearray()
            for e, o in c['pairs']:
                buf += il(open(os.path.join(base, e), 'rb').read(), open(os.path.join(base, o), 'rb').read())
            images[cpu] = buf; names[cpu] = [tuple(p) for p in c['pairs']]
        return cls(images, names)

    def img(self, cpu): return self.cur[cpu]

    def is_free(self, cpu, addr, n):
        cur = self.orig[cpu][addr:addr + n]
        return len(set(cur)) == 1 and cur[0] in (0, 0xff)

    def put(self, cpu, addr, data, tag='', expect=None, free_ok=False):
        o = self.orig[cpu]
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

    def asm(self, cpu, org, src, tag='', labels=None, expect=None, free_ok=False):
        import asm68
        b, lab = asm68.assemble(src, org, labels)
        self.put(cpu, org, b, tag, expect=expect, free_ok=free_ok)
        return lab, len(b)

    def report(self):
        """書いた場所の一覧（アドレス順）"""
        return '\n'.join(f'{c:5s} {s:06x}-{e:06x} {e - s:5d}B {t}' for c, s, e, t in sorted(self.used))

    def write(self, outdir):
        """偶数・奇数に分け、元のファイル名で書き出す。CRC の一覧を返す"""
        os.makedirs(outdir, exist_ok=True)
        out = {}
        for cpu, buf in self.cur.items():
            off = 0
            if not self.names.get(cpu): continue
            for e, o in self.names.get(cpu, []):
                size = len(buf) // len(self.names[cpu])
                ev, od = split(buf[off:off + size]); off += size
                for name, data in ((e, ev), (o, od)):
                    open(os.path.join(outdir, name), 'wb').write(data); out[name] = crc(data)
        return out


if __name__ == '__main__':   # 自己テスト: python3 tools/romkit.py
    even = bytes([0x00] * 32 + [0x40] * 32); odd = bytes([0x00] * 32 + [0x40] * 32)   # 前半は空き(0x00)、後半は中身
    r = Rom({'main': il(even, odd)}, {'main': [('e.bin', 'o.bin')]})
    e0, o0 = lane_sums(r.img('main'))
    r.put('main', 0x10, b'\x4e\x75', 'rts')
    try: r.put('main', 0x11, b'\x00', 'overlap'); raise SystemExit('重なりを検出できていない')
    except AssertionError: pass
    lane_fix(r.img('main'), e0, o0, [(0x70, 0x80)])
    assert lane_sums(r.img('main')) == (e0, o0)
    lab, n = r.asm('main', 0x20, 'start:\n        moveq   #1,d0\n        rts\n', 'asm')
    print(r.report()); print('romkit OK')
