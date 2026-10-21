# Frame of each sheet in grade, from grid2's per-half lines (see frameingrade.py for the idea), and the neighbour table.
import sys, json, numpy as np
sys.path.insert(0,__file__.rsplit('/',1)[0]); import grid2 as G
SP=sys.argv[1]; M=G.M
def interp(pos,x):
    g=sorted(pos,key=lambda k:abs(pos[k]-x))[:2]; g0,g1=sorted(g); return g0+(x-pos[g0])*(g1-g0)/(pos[g1]-pos[g0]), min(abs(pos[k]-x) for k in pos)
res={}; spac={}
for sheet in G.ids:
    if not G.masks[sheet]['polygon']: continue
    gr=G.grid(sheet,SP); ok,notes=G.gate(gr); V,H,xm=gr['V'],gr['H'],gr['fold']; p=np.array(G.masks[sheet]['polygon'])/G.S; TL,TM,TR,BR,BM,BL=p
    out={}; far=0
    ys=np.linspace(TL[1]+500,BL[1]-500,5)
    for side,(P,Q_) in (('W',(TL,BL)),('E',(TR,BR))):
        v=[]
        for y in ys:
            xe=np.interp(y,[P[1],Q_[1]],[P[0],Q_[0]]); gx,dist=interp({g:b0+b1*y for g,(b0,b1,*_) in V.items()},xe); v.append(gx); far=max(far,dist*M/1000)
        out[side]=(float(np.mean(v)),float(np.std(v)))
    for side,(P,Q_) in (('N',(TL,TR)),('S',(BL,BR))):
        v=[]
        for x in np.linspace(P[0]+400,Q_[0]-400,6):
            h='L' if x<xm else 'R'; ye=np.interp(x,[P[0],Q_[0]],[P[1],Q_[1]]); pos={g:hv[h][0]+hv[h][1]*x for g,hv in H.items() if h in hv}
            gy,dist=interp(pos,ye); v.append(gy); far=max(far,dist*M/1000)
        out[side]=(float(np.mean(v)),float(np.std(v)))
    res[sheet]=dict(edges=out,gate=ok,notes=notes,farthest_line_km=far)
    # spacings per half and tilts
    gs=sorted(H); sp={h:[((H[b][h][0]+H[b][h][1]*(xm+(-500 if h=='L' else 500)))-(H[a][h][0]+H[a][h][1]*(xm+(-500 if h=='L' else 500))))*M/1000 for a,b in zip(gs,gs[1:]) if h in H[a] and h in H[b]] for h in ('L','R')}
    tilts={h:[round(float(np.degrees(np.arctan(H[g][h][1]))),2) for g in gs if h in H[g]] for h in ('L','R')}
    vs=sorted(V); vsp=[((V[b][0]+V[b][1]*TL[1])-(V[a][0]+V[a][1]*TL[1]))*M/1000 for a,b in zip(vs,vs[1:])],[((V[b][0]+V[b][1]*BL[1])-(V[a][0]+V[a][1]*BL[1]))*M/1000 for a,b in zip(vs,vs[1:])]
    print(f"{sheet:13s} gate {'PASS' if ok else 'FAIL'} H spacing L {np.round(sp['L'],2).tolist()} R {np.round(sp['R'],2).tolist()} tilts L {tilts['L']} R {tilts['R']} | V spacing top {np.round(vsp[0],2).tolist()} bottom {np.round(vsp[1],2).tolist()} tilts {[round(float(np.degrees(np.arctan(V[g][1]))),2) for g in vs]} | farthest line from an edge {far:.1f} km")
GRID={'viet-tri':(0,0),'ha-noi':(1,0),'bac-giang':(2,0),'an-chau':(3,0),'hoa-binh':(0,1),'hung-yen':(1,1),'hai-phong':(2,1),'quang-yen':(3,1),'ninh-binh':(1,2),'bui-chu':(2,2),'vinh-bac-viet':(3,2)}
by={v:k for k,v in GRID.items()}; print('\nshared edges, grade gap -> km (+ gap, - overlap); g = both sheets pass the gate')
rows=[]
for (c,r),k in by.items():
    for dc,dr,ea,eb,scale in ((1,0,'E','W',93.4),(0,1,'S','N',100.0)):
        b=by.get((c+dc,r+dr))
        if b and k in res and b in res:
            dg=(res[b]['edges'][eb][0]-res[k]['edges'][ea][0]) if dc else (res[k]['edges'][ea][0]-res[b]['edges'][eb][0])
            g='g' if res[k]['gate'] and res[b]['gate'] else ' '; rows.append((k,b,dg*scale)); print(f"  {g} {k:12s} {'|' if dc else '/'} {b:12s} {dg*scale:+6.2f} km")
json.dump({k:{'edges':{s:list(v) for s,v in o['edges'].items()},'gate':o['gate'],'notes':o['notes']} for k,o in res.items()},open(f'{G.HERE}/frame_in_grade2.json','w'),indent=1)
