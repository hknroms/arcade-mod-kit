"""BPS パッチの作成・適用（純正ROM→改造ROM の差分。差分以外の純正データは含まない）"""
import zlib, struct

def _vlq(n):
    out = bytearray()
    while True:
        x = n & 0x7f; n >>= 7
        if n == 0: out.append(0x80 | x); return bytes(out)
        out.append(x); n -= 1

def create(src: bytes, tgt: bytes) -> bytes:
    assert len(src) == len(tgt)
    p = bytearray(b'BPS1') + _vlq(len(src)) + _vlq(len(tgt)) + _vlq(0)
    i, n = 0, len(tgt)
    while i < n:
        j = i
        if src[i] == tgt[i]:
            while j < n and src[j] == tgt[j]: j += 1
            # 短い一致は直書きに混ぜる（パッチを小さく）
            if j - i >= 8 or j == n:
                p += _vlq(((j - i - 1) << 2) | 0); i = j; continue
        # 差分区間: 8バイト以上の一致が来るまで直書き
        j = i
        while j < n:
            if src[j] == tgt[j]:
                k = j
                while k < n and src[k] == tgt[k] and k - j < 8: k += 1
                if k - j >= 8 or k == n: break
                j = k
            else:
                j += 1
        p += _vlq(((j - i - 1) << 2) | 1) + tgt[i:j]; i = j
    p += struct.pack('<II', zlib.crc32(src), zlib.crc32(tgt))
    p += struct.pack('<I', zlib.crc32(bytes(p)))
    return bytes(p)

def apply(src: bytes, patch: bytes) -> bytes:
    assert patch[:4] == b'BPS1'
    pos = 4
    def rd():
        nonlocal pos
        d, s = 0, 1
        while True:
            x = patch[pos]; pos += 1
            d += (x & 0x7f) * s
            if x & 0x80: return d
            s <<= 7; d += s
    ss, ts, ms = rd(), rd(), rd(); pos += ms
    assert zlib.crc32(patch[:-4]) == struct.unpack('<I', patch[-4:])[0]
    assert zlib.crc32(src) == struct.unpack('<I', patch[-12:-8])[0], 'source CRC mismatch'
    out = bytearray(); sr = tr = 0
    end = len(patch) - 12
    while pos < end:
        d = rd(); cmd = d & 3; ln = (d >> 2) + 1
        if cmd == 0: out += src[len(out):len(out) + ln]
        elif cmd == 1: out += patch[pos:pos + ln]; pos += ln
        else:
            o = rd(); o = -(o >> 1) if o & 1 else o >> 1
            if cmd == 2:
                sr += o; out += src[sr:sr + ln]; sr += ln
            else:
                tr += o
                for _ in range(ln): out.append(out[tr]); tr += 1
    assert zlib.crc32(out) == struct.unpack('<I', patch[-8:-4])[0], 'target CRC mismatch'
    return bytes(out)
