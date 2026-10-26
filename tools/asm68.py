"""Mini 68000 assembler (subset) for arcade ROM patches (from hknroms/gradius3).
Syntax follows d68.py's disassembly output ($hex, #imm, d16(aN), $x.l, label refs).
assemble(src, org) -> bytes.  Two passes; labels via 'name:'.
"""
import re, struct

CC = {'t':0,'f':1,'hi':2,'ls':3,'cc':4,'hs':4,'cs':5,'lo':5,'ne':6,'eq':7,'vc':8,'vs':9,'pl':10,'mi':11,'ge':12,'lt':13,'gt':14,'le':15}
SZ = {'b':0,'w':1,'l':2}

class AsmError(Exception): pass

def num(tok, labels, pc=None):
    tok = tok.strip()
    # expression: sum/difference of terms
    terms = re.findall(r'[+-]?\s*[^+-]+', tok.replace(' ', ''))
    # handle leading '-$' etc.; split carefully
    total = 0
    for t in re.findall(r'([+-]?)([^+-]+)', tok.replace(' ', '')):
        sign, v = t
        if v.startswith('$'): val = int(v[1:], 16)
        elif v.startswith('0x'): val = int(v, 16)
        elif v.startswith('%'): val = int(v[1:], 2)
        elif re.fullmatch(r'\d+', v): val = int(v)
        elif v == '*': val = pc
        elif v in labels: val = labels[v]
        else:
            raise KeyError(v)
        total += -val if sign == '-' else val
    return total

class Asm:
    def __init__(self):
        self.labels = {}
    # ---------- operand parsing ----------
    def parse_ea(self, s):
        s = s.strip()
        m = re.fullmatch(r'd([0-7])', s)
        if m: return ('dn', int(m.group(1)))
        m = re.fullmatch(r'(?:a([0-7])|sp)', s)
        if m: return ('an', int(m.group(1)) if m.group(1) else 7)
        m = re.fullmatch(r'\((?:a([0-7])|sp)\)', s)
        if m: return ('ind', int(m.group(1)) if m.group(1) else 7)
        m = re.fullmatch(r'\((?:a([0-7])|sp)\)\+', s)
        if m: return ('post', int(m.group(1)) if m.group(1) else 7)
        m = re.fullmatch(r'-\((?:a([0-7])|sp)\)', s)
        if m: return ('pre', int(m.group(1)) if m.group(1) else 7)
        if s.startswith('#'): return ('imm', s[1:])
        m = re.fullmatch(r'(.*)\((pc)(?:,([ad])([0-7])(?:\.([wl]))?)?\)', s)
        if m:
            if m.group(3): return ('pcidx', m.group(1), (m.group(3), int(m.group(4)), m.group(5) or 'w'))
            return ('pcd', m.group(1))
        m = re.fullmatch(r'(.*)\(a([0-7]|sp),([ad])([0-7])(?:\.([wl]))?\)', s)
        if m:
            an = 7 if m.group(2) == 'sp' else int(m.group(2))
            return ('idx', m.group(1) or '0', an, (m.group(3), int(m.group(4)), m.group(5) or 'w'))
        m = re.fullmatch(r'(.*)\((?:a([0-7])|sp)\)', s)
        if m:
            an = int(m.group(2)) if m.group(2) else 7
            return ('disp', m.group(1) or '0', an)
        m = re.fullmatch(r'(.*)\.(w|l)', s)
        if m: return ('abs', m.group(1), m.group(2))
        return ('abs', s, 'l')

    def enc_ea(self, ea, size, pc_ext, final):
        """returns (mode, reg, ext_bytes). pc_ext = address of next extension word."""
        k = ea[0]
        def N(t, pc=None):
            try: return num(t, self.labels, pc)
            except KeyError:
                if final: raise AsmError('undefined label in %r' % t)
                return 0
        if k == 'dn': return 0, ea[1], b''
        if k == 'an': return 1, ea[1], b''
        if k == 'ind': return 2, ea[1], b''
        if k == 'post': return 3, ea[1], b''
        if k == 'pre': return 4, ea[1], b''
        if k == 'disp': return 5, ea[2], struct.pack('>h', N(ea[1]) if -32768 <= N(ea[1]) < 32768 else (_ for _ in ()).throw(AsmError('disp range')))
        if k == 'idx':
            d8 = N(ea[1]); x = ea[3]
            if not -128 <= d8 < 128: raise AsmError('d8 range')
            w = (0x8000 if x[0]=='a' else 0) | (x[1]<<12) | (0x800 if x[2]=='l' else 0) | (d8 & 0xff)
            return 6, ea[2], struct.pack('>H', w)
        if k == 'abs':
            v = N(ea[1])
            if ea[2] == 'w':
                v &= 0xffffffff
                sv = v if v < 0x8000 else (v - 0x100000000 if v >= 0xffff8000 else None)
                if sv is None: raise AsmError('abs.w range %x' % v)
                return 7, 0, struct.pack('>h', sv)
            return 7, 1, struct.pack('>I', v & 0xffffffff)
        if k == 'pcd':
            d = N(ea[1]) - pc_ext
            if not -32768 <= d < 32768: raise AsmError('pc disp range')
            return 7, 2, struct.pack('>h', d)
        if k == 'pcidx':
            d8 = N(ea[1]) - pc_ext; x = ea[2]
            if not -128 <= d8 < 128: raise AsmError('pc d8 range')
            w = (0x8000 if x[0]=='a' else 0) | (x[1]<<12) | (0x800 if x[2]=='l' else 0) | (d8 & 0xff)
            return 7, 3, struct.pack('>H', w)
        if k == 'imm':
            v = N(ea[1])
            if size == 'l': return 7, 4, struct.pack('>I', v & 0xffffffff)
            if size == 'w': return 7, 4, struct.pack('>H', v & 0xffff)
            return 7, 4, struct.pack('>H', v & 0xff)
        raise AsmError('bad ea')

    # ---------- split operands ----------
    @staticmethod
    def split_ops(s):
        out, depth, cur = [], 0, ''
        for ch in s:
            if ch == '(': depth += 1
            if ch == ')': depth -= 1
            if ch == ',' and depth == 0:
                out.append(cur); cur = ''
            else: cur += ch
        if cur.strip(): out.append(cur)
        return [o.strip() for o in out]

    # ---------- single instruction ----------
    def inst(self, addr, text, final):
        text = text.strip()
        m = re.match(r'(\S+)\s*(.*)', text)
        mn, rest = m.group(1).lower(), m.group(2)
        ops = self.split_ops(rest)
        base, _, suf = mn.partition('.')
        W = lambda v: struct.pack('>H', v & 0xffff)
        E = lambda ea, size, off: self.enc_ea(ea, size, addr + 2 + off, final)
        def N(t):
            try: return num(t, self.labels, addr)
            except KeyError:
                if final: raise AsmError('undefined label %r' % t)
                return 0

        # no-operand
        simple = {'nop':0x4e71,'rts':0x4e75,'rte':0x4e73,'rtr':0x4e77,'reset':0x4e70,'illegal':0x4afc,'trapv':0x4e76}
        if mn in simple: return W(simple[mn])
        if base == 'dc':
            sz = suf or 'w'
            out = b''
            for o in ops:
                if o.startswith('"'): out += o.strip('"').encode('ascii'); continue
                v = N(o)
                out += struct.pack({'b':'>B','w':'>H','l':'>I'}[sz], v & {'b':0xff,'w':0xffff,'l':0xffffffff}[sz])
            if sz == 'b' and len(out) % 2 and False: out += b'\0'
            return out
        if base == 'ds':
            return b'\0' * (N(ops[0]) * {'b':1,'w':2,'l':4}[suf or 'w'])
        # branches
        if base in ('bra','bsr') or (base.startswith('b') and base[1:] in CC and base not in ('bchg','bclr','bset','btst')):
            cc = 0 if base == 'bra' else 1 if base == 'bsr' else CC[base[1:]]
            tgt = N(ops[0]); disp = tgt - (addr + 2)
            if not final:
                return W(0x6000 | cc<<8) if suf == 's' else W(0x6000 | cc<<8) + b'\0\0'
            if suf == 's' or (suf == '' and False):
                if not -128 <= disp <= 127 or disp == 0: raise AsmError('bcc.s range %d at %x: %s' % (disp, addr, text))
                return W(0x6000 | cc<<8 | (disp & 0xff))
            if not -32768 <= disp < 32768: raise AsmError('bcc.w range')
            return W(0x6000 | cc<<8) + struct.pack('>h', disp)
        if base.startswith('db') and base[2:] in CC:
            cc = CC[base[2:]]; dn = int(ops[0][1])
            if not final: return W(0x50c8 | cc<<8 | dn) + b'\0\0'
            return W(0x50c8 | cc<<8 | dn) + struct.pack('>h', N(ops[1]) - (addr + 2))
        if base.startswith('s') and base[1:] in CC and len(ops) == 1 and base not in ('swap','sub'):
            cc = CC[base[1:]]; mo, rg, ex = E(self.parse_ea(ops[0]), 'b', 0)
            return W(0x50c0 | cc<<8 | mo<<3 | rg) + ex
        if base == 'moveq':
            v = N(ops[0][1:]) & 0xff; return W(0x7000 | int(ops[1][1])<<9 | v)
        if base in ('lea','pea','jsr','jmp'):
            if base == 'lea':
                mo, rg, ex = E(self.parse_ea(ops[0]), 'l', 0)
                return W(0x41c0 | int(ops[1][1])<<9 | mo<<3 | rg) + ex
            mo, rg, ex = E(self.parse_ea(ops[0]), 'l', 0)
            op = {'pea':0x4840,'jsr':0x4e80,'jmp':0x4ec0}[base]
            return W(op | mo<<3 | rg) + ex
        if base == 'trap': return W(0x4e40 | N(ops[0][1:]))
        if base == 'link': return W(0x4e50 | int(ops[0][1])) + struct.pack('>h', N(ops[1][1:]))
        if base == 'unlk': return W(0x4e58 | int(ops[0][1]))
        if base == 'swap': return W(0x4840 | int(ops[0][1]))
        if base == 'ext': return W((0x4880 if suf == 'w' else 0x48c0) | int(ops[0][1]))
        if base == 'stop': return W(0x4e72) + W(N(ops[0][1:]))
        # move family
        if base in ('move','movea'):
            s, d = ops
            if d.lower() == 'sr':
                mo, rg, ex = E(self.parse_ea(s), 'w', 0); return W(0x46c0 | mo<<3 | rg) + ex
            if d.lower() == 'ccr':
                mo, rg, ex = E(self.parse_ea(s), 'w', 0); return W(0x44c0 | mo<<3 | rg) + ex
            if s.lower() == 'sr':
                mo, rg, ex = E(self.parse_ea(d), 'w', 0); return W(0x40c0 | mo<<3 | rg) + ex
            if s.lower() == 'usp': return W(0x4e68 | int(d[1]))
            if d.lower() == 'usp': return W(0x4e60 | int(s[1]))
            sz = suf or 'w'
            sea, dea = self.parse_ea(s), self.parse_ea(d)
            smo, srg, sex = E(sea, sz, 0)
            dmo, drg, dex = E(dea, sz, len(sex))
            top = {'b':1,'w':3,'l':2}[sz]
            return W(top<<12 | drg<<9 | dmo<<6 | smo<<3 | srg) + sex + dex
        if base == 'movem':
            sz = suf or 'w'
            def regmask(t, pre):
                mask = 0
                for part in t.split('/'):
                    if '-' in part:
                        a, b = part.split('-'); lo = self._r(a); hi = self._r(b)
                        for i in range(lo, hi+1): mask |= 1<<i
                    else: mask |= 1 << self._r(part)
                if pre: mask = int(format(mask, '016b')[::-1], 2)
                return mask
            if re.match(r'^[ad][0-7]([/-]|$)', ops[0]) and not ops[0].startswith('(') :
                ea = self.parse_ea(ops[1]); mask = regmask(ops[0], ea[0] == 'pre'); dr = 0
            else:
                ea = self.parse_ea(ops[0]); mask = regmask(ops[1], False); dr = 1
            mo, rg, ex = E(ea, sz, 2)
            return W(0x4880 | dr<<10 | (0x40 if sz == 'l' else 0) | mo<<3 | rg) + W(mask) + ex
        if base == 'exg':
            a, b = ops
            if a[0] == 'd' and b[0] == 'd': return W(0xc140 | int(a[1])<<9 | int(b[1]))
            if a[0] == 'a' and b[0] == 'a': return W(0xc148 | int(a[1])<<9 | int(b[1]))
            if a[0] == 'd': return W(0xc188 | int(a[1])<<9 | int(b[1]))
            return W(0xc188 | int(b[1])<<9 | int(a[1]))
        # immediates ALU
        immop = {'ori':0x0000,'andi':0x0200,'subi':0x0400,'addi':0x0600,'eori':0x0a00,'cmpi':0x0c00}
        if base in immop:
            sz = suf or 'w'
            if ops[1].lower() in ('sr','ccr'):
                v = N(ops[0][1:])
                if ops[1].lower() == 'ccr': return W(immop[base] | 0x3c) + W(v & 0xff)
                return W(immop[base] | 0x7c) + W(v & 0xffff)
            iv = self.enc_ea(('imm', ops[0][1:]), sz, 0, final)[2]
            mo, rg, ex = E(self.parse_ea(ops[1]), sz, len(iv))
            return W(immop[base] | SZ[sz]<<6 | mo<<3 | rg) + iv + ex
        if base in ('addq','subq'):
            sz = suf or 'w'; q = N(ops[0][1:])
            if not 1 <= q <= 8: raise AsmError('addq range')
            mo, rg, ex = E(self.parse_ea(ops[1]), sz, 0)
            return W(0x5000 | (q & 7)<<9 | (0x100 if base == 'subq' else 0) | SZ[sz]<<6 | mo<<3 | rg) + ex
        if base in ('clr','neg','not','tst','negx'):
            sz = suf or 'w'
            op = {'negx':0x4000,'clr':0x4200,'neg':0x4400,'not':0x4600,'tst':0x4a00}[base]
            mo, rg, ex = E(self.parse_ea(ops[0]), sz, 0)
            return W(op | SZ[sz]<<6 | mo<<3 | rg) + ex
        if base == 'tas':
            mo, rg, ex = E(self.parse_ea(ops[0]), 'b', 0); return W(0x4ac0 | mo<<3 | rg) + ex
        if base in ('btst','bchg','bclr','bset'):
            t = {'btst':0,'bchg':1,'bclr':2,'bset':3}[base]
            dea = self.parse_ea(ops[1])
            if ops[0].startswith('#'):
                b = N(ops[0][1:])
                mo, rg, ex = E(dea, 'b', 2)
                return W(0x0800 | t<<6 | mo<<3 | rg) + W(b & 0xff) + ex
            mo, rg, ex = E(dea, 'b', 0)
            return W(0x0100 | int(ops[0][1])<<9 | t<<6 | mo<<3 | rg) + ex
        # shifts
        sh = {'as':0,'ls':1,'rox':2,'ro':3}
        if base[:-1] in sh and base[-1] in 'lr':
            t = sh[base[:-1]]; dr = 1 if base[-1] == 'l' else 0
            if len(ops) == 1:
                mo, rg, ex = E(self.parse_ea(ops[0]), 'w', 0)
                return W(0xe0c0 | t<<9 | dr<<8 | mo<<3 | rg) + ex
            sz = suf or 'w'; c = ops[0]
            if c.startswith('#'):
                n = N(c[1:]); w = 0xe000 | (n & 7)<<9
            else: w = 0xe020 | int(c[1])<<9
            return W(w | dr<<8 | SZ[sz]<<6 | t<<3 | int(ops[1][1]))
        if base in ('mulu','muls','divu','divs'):
            mo, rg, ex = E(self.parse_ea(ops[0]), 'w', 0)
            op = {'mulu':0xc0c0,'muls':0xc1c0,'divu':0x80c0,'divs':0x81c0}[base]
            return W(op | int(ops[1][1])<<9 | mo<<3 | rg) + ex
        if base in ('add','sub','and','or','cmp','eor','adda','suba','cmpa'):
            sz = suf or 'w'
            top = {'add':0xd000,'sub':0x9000,'and':0xc000,'or':0x8000,'cmp':0xb000,'eor':0xb000,'adda':0xd000,'suba':0x9000,'cmpa':0xb000}[base]
            sea, dea = self.parse_ea(ops[0]), self.parse_ea(ops[1])
            if base in ('adda','suba','cmpa') or (dea[0] == 'an' and base in ('add','sub','cmp')):
                smo, srg, sex = E(sea, sz, 0)
                return W(top | dea[1]<<9 | (7 if sz == 'l' else 3)<<6 | smo<<3 | srg) + sex
            if base == 'eor' or (dea[0] != 'dn' and base != 'cmp'):
                dmo, drg, dex = E(dea, sz, 0)
                return W(top | sea[1]<<9 | (4+SZ[sz])<<6 | dmo<<3 | drg) + dex
            smo, srg, sex = E(sea, sz, 0)
            return W(top | dea[1]<<9 | SZ[sz]<<6 | smo<<3 | srg) + sex
        raise AsmError('unknown mnemonic %r' % mn)

    def _r(self, t):
        t = t.strip()
        return (8 if t[0] == 'a' else 0) + int(t[1])

    # ---------- whole source ----------
    def assemble(self, src, org):
        lines = []
        for ln in src.splitlines():
            ln = ln.split(';')[0].rstrip()
            if ln.strip(): lines.append(ln)
        # pass 1/2: collect labels with sizes (iterate twice; sizes are stable because forms are explicit)
        for final in (False, True):
            addr = org; out = bytearray(); lab_new = {}
            for ln in lines:
                s = ln.strip()
                m = re.match(r'^([A-Za-z_.][\w.]*)\s*:\s*(.*)$', s)
                if m:
                    lab_new[m.group(1)] = addr; s = m.group(2).strip()
                    if not s: continue
                m = re.match(r'^([A-Za-z_][\w]*)\s*=\s*(.+)$', s)
                if m:
                    self.labels[m.group(1)] = num(m.group(2), self.labels); continue
                if s.lower().startswith('org'):
                    addr = num(s.split(None, 1)[1], self.labels);
                    if not out and addr != org: org = addr
                    continue
                if s.lower() in ('even',):
                    if addr % 2: out += b'\0'; addr += 1
                    continue
                b = self.inst(addr, s, final)
                out += b; addr += len(b)
            self.labels.update(lab_new)
        return bytes(out)

def assemble(src, org, labels=None):
    a = Asm()
    if labels: a.labels.update(labels)
    b = a.assemble(src, org)
    return b, a.labels
