import struct
CC=['t','f','hi','ls','cc','cs','ne','eq','vc','vs','pl','mi','ge','lt','gt','le']
SZ={0:'b',1:'w',2:'l'}
class R:
    def __init__(s,d,a): s.d=d;s.a=a;s.s=a
    def w(s):
        v=struct.unpack('>H',s.d[s.a:s.a+2])[0];s.a+=2;return v
    def sw(s):
        v=s.w();return v-65536 if v&0x8000 else v
    def l(s):
        v=struct.unpack('>I',s.d[s.a:s.a+4])[0];s.a+=4;return v
def hx(v,w=0): return '$%x'%(v&0xffffffff) if v>=0 else '-$%x'%(-v)
def ea(r,mode,reg,sz):
    if mode==0:return 'd%d'%reg
    if mode==1:return 'a%d'%reg
    if mode==2:return '(a%d)'%reg
    if mode==3:return '(a%d)+'%reg
    if mode==4:return '-(a%d)'%reg
    if mode==5:return '%s(a%d)'%(hx(r.sw()),reg)
    if mode==6:
        e=r.w();dd=e&0xff;dd=dd-256 if dd&128 else dd
        x=('a' if e&0x8000 else 'd')+str((e>>12)&7)+('.l' if e&0x800 else '.w')
        return '%s(a%d,%s)'%(hx(dd),reg,x)
    if mode==7:
        if reg==0:return '%s.w'%hx(r.sw())
        if reg==1:return '%s.l'%hx(r.l())
        if reg==2:
            b=r.a;dd=r.sw();return '%s(pc)'%hx(b+dd)
        if reg==3:
            b=r.a;e=r.w();dd=e&0xff;dd=dd-256 if dd&128 else dd
            x=('a' if e&0x8000 else 'd')+str((e>>12)&7)+('.l' if e&0x800 else '.w')
            return '%s(pc,%s)'%(hx(b+dd),x)
        if reg==4:
            if sz=='l':return '#'+hx(r.l())
            v=r.w();return '#'+hx(v&0xff if sz=='b' else v)
    return '?'
def regs(mask,pre):
    names=[('d%d'%i) for i in range(8)]+[('a%d'%i) for i in range(8)]
    if pre: mask=int(format(mask,'016b')[::-1],2)
    out=[];i=0
    while i<16:
        if mask>>i&1:
            j=i
            while j+1<16 and (mask>>(j+1)&1) and (j+1)//8==i//8:j+=1
            out.append(names[i] if i==j else names[i]+'-'+names[j]);i=j+1
        else:i+=1
    return '/'.join(out)
def dis1(d,a):
    r=R(d,a);op=r.w();t=op>>12;rg=(op>>9)&7;md=(op>>3)&7;rr=op&7
    def bad():return 'dc.w $%04x'%op
    if op==0x4e71:m='nop'
    elif op==0x4e75:m='rts'
    elif op==0x4e73:m='rte'
    elif op==0x4e77:m='rtr'
    elif op==0x4e76:m='trapv'
    elif op==0x4e70:m='reset'
    elif op==0x4afc:m='illegal'
    elif t==0:
        if op&0x138==0x108:
            sz='l' if op&0x40 else 'w';m='movep.%s %s'%(sz,'%s(a%d),d%d'%(hx(r.sw()),rr,rg) if not op&0x80 else 'd%d,%s(a%d)'%(rg,hx(r.sw()),rr))
        elif op&0x100:
            n=['btst','bchg','bclr','bset'][(op>>6)&3];m='%s d%d,%s'%(n,rg,ea(r,md,rr,'b'))
        elif rg==4:
            n=['btst','bchg','bclr','bset'][(op>>6)&3];b=r.w()&0xff;m='%s #%d,%s'%(n,b,ea(r,md,rr,'b'))
        else:
            n=['ori','andi','subi','addi','','eori','cmpi',''][rg]
            if (op>>6)&3==3 or not n:m=bad()
            else:
                sz=SZ[(op>>6)&3]
                if md==7 and rr==4 and sz!='l' and rg in(0,1,5):
                    v=r.w();m='%s #%s,%s'%(n,hx(v),'sr' if sz=='w' else 'ccr')
                else:
                    im=ea(r,7,4,sz);m='%s.%s %s,%s'%(n,sz,im,ea(r,md,rr,sz))
    elif t in(1,2,3):
        sz={1:'b',3:'w',2:'l'}[t];s=ea(r,md,rr,sz);dm=(op>>6)&7
        m=('movea.%s %s,a%d'%(sz,s,rg)) if dm==1 else 'move.%s %s,%s'%(sz,s,ea(r,dm,rg,sz))
    elif t==4:
        if op&0x1c0==0x1c0:m='lea %s,a%d'%(ea(r,md,rr,'l'),rg)
        elif op&0x1c0==0x180:m='chk %s,d%d'%(ea(r,md,rr,'w'),rg)
        elif op&0xfb80==0x4880 and md!=0:
            sz='l' if op&0x40 else 'w';mask=r.w()
            if op&0x400:m='movem.%s %s,%s'%(sz,ea(r,md,rr,sz),regs(mask,0))
            else:m='movem.%s %s,%s'%(sz,regs(mask,md==4),ea(r,md,rr,sz))
        elif op&0xfff8==0x4880:m='ext.w d%d'%rr
        elif op&0xfff8==0x48c0:m='ext.l d%d'%rr
        elif op&0xfff8==0x4840:m='swap d%d'%rr
        elif op&0xffc0==0x4840:m='pea %s'%ea(r,md,rr,'l')
        elif op&0xfff0==0x4e40:m='trap #%d'%(op&15)
        elif op&0xfff8==0x4e50:m='link a%d,#%s'%(rr,hx(r.sw()))
        elif op&0xfff8==0x4e58:m='unlk a%d'%rr
        elif op&0xfff8==0x4e60:m='move a%d,usp'%rr
        elif op&0xfff8==0x4e68:m='move usp,a%d'%rr
        elif op&0xffc0==0x4e80:m='jsr %s'%ea(r,md,rr,'l')
        elif op&0xffc0==0x4ec0:m='jmp %s'%ea(r,md,rr,'l')
        elif op&0xffc0==0x40c0:m='move sr,%s'%ea(r,md,rr,'w')
        elif op&0xffc0==0x44c0:m='move %s,ccr'%ea(r,md,rr,'w')
        elif op&0xffc0==0x46c0:m='move %s,sr'%ea(r,md,rr,'w')
        elif op&0xffc0==0x4ac0:m='tas %s'%ea(r,md,rr,'b')
        elif op==0x4e72:m='stop #%s'%hx(r.w())
        elif (op>>8)&15 in(0,2,4,6,10) and (op>>6)&3!=3:
            n={0:'negx',2:'clr',4:'neg',6:'not',10:'tst'}[(op>>8)&15];sz=SZ[(op>>6)&3];m='%s.%s %s'%(n,sz,ea(r,md,rr,sz))
        else:m=bad()
    elif t==5:
        if (op>>6)&3==3:
            c=CC[(op>>8)&15]
            if md==1:
                b=r.a;dd=r.sw();m='db%s d%d,%s'%(c,rr,hx(b+dd))
            else:m='s%s %s'%(c,ea(r,md,rr,'b'))
        else:
            sz=SZ[(op>>6)&3];q=rg or 8;m='%s.%s #%d,%s'%('subq' if op&0x100 else 'addq',sz,q,ea(r,md,rr,sz))
    elif t==6:
        c=(op>>8)&15;dp=op&0xff;b=r.a
        if dp==0:dd=r.sw();suf='.w'
        else:dd=dp-256 if dp&128 else dp;suf='.s'
        n='bra' if c==0 else 'bsr' if c==1 else 'b'+CC[c]
        m='%s%s %s'%(n,suf,hx(b+dd))
    elif t==7:
        v=op&0xff;v=v-256 if v&128 else v;m='moveq #%s,d%d'%(hx(v) if v<0 else hx(v),rg)
    elif t in(8,12,9,11,13):
        if t==8:n='or';mu='divu';ms='divs'
        elif t==12:n='and';mu='mulu';ms='muls'
        elif t==9:n='sub'
        elif t==13:n='add'
        else:n='cmp'
        o3=(op>>6)&7
        if t in(8,12) and o3==3:m='%s %s,d%d'%(mu,ea(r,md,rr,'w'),rg)
        elif t in(8,12) and o3==7:m='%s %s,d%d'%(ms,ea(r,md,rr,'w'),rg)
        elif t==8 and o3==4 and md<2:m='sbcd %s'%(('d%d,d%d'%(rr,rg)) if md==0 else '-(a%d),-(a%d)'%(rr,rg))
        elif t==12 and o3 in(5,6,4) and md<2 and o3!=4 or (t==12 and o3==4 and md<2):
            m='exg %s'%({5:'d%d,d%d',6:'a%d,d%d' if False else 'd%d,a%d',4:'d%d,d%d'}[o3] % (rg,rr) if o3!=6 else 'a%d,a%d'%(rg,rr)) if o3!=4 else 'abcd'
        elif t in(9,13,11) and o3 in(3,7):
            sz='w' if o3==3 else 'l';nn={9:'suba',13:'adda',11:'cmpa'}[t];m='%s.%s %s,a%d'%(nn,sz,ea(r,md,rr,sz),rg)
        elif t==11 and o3>=4:
            sz=SZ[o3-4];
            if md==1:m='cmpm.%s (a%d)+,(a%d)+'%(sz,rr,rg)
            else:m='eor.%s d%d,%s'%(sz,rg,ea(r,md,rr,sz))
        elif t in(9,13) and o3>=4 and md<2:
            sz=SZ[o3-4];m='%sx.%s %s'%(n,sz,('d%d,d%d'%(rr,rg)) if md==0 else '-(a%d),-(a%d)'%(rr,rg))
        else:
            sz=SZ[o3&3] if o3<3 else SZ[o3-4]
            if o3<3:m='%s.%s %s,d%d'%(n,sz,ea(r,md,rr,sz),rg)
            else:m='%s.%s d%d,%s'%(n,sz,rg,ea(r,md,rr,sz))
    elif t==14:
        if (op>>6)&3==3:
            n=['as','ls','rox','ro'][(op>>9)&3]+('l' if op&0x100 else 'r');m='%s.w %s'%(n,ea(r,md,rr,'w'))
        else:
            sz=SZ[(op>>6)&3];n=['as','ls','rox','ro'][(op>>3)&3]+('l' if op&0x100 else 'r')
            cnt=('d%d'%rg) if op&0x20 else '#%d'%(rg or 8);m='%s.%s %s,d%d'%(n,sz,cnt,rr)
    else:m=bad()
    return r.a,m
def dis(d,s,e):
    a=s;out=[]
    while a<e:
        try:n,m=dis1(d,a)
        except Exception:n,m=a+2,'dc.w ?'
        out.append('%06x: %-24s %s'%(a,d[a:n].hex(),m));a=n
    return '\n'.join(out)
