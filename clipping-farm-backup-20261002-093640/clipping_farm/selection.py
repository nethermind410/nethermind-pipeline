"""Selection and temporal diversity filter."""
def select(candidates, limit=10, overlap_ratio=0.35):
    chosen=[]
    for c in sorted(candidates,key=lambda x:x.scores.get("total",0),reverse=True):
        if c.scores.get("standalone",0) < .5: continue
        duplicate=False
        for x in chosen:
            overlap=max(0,min(c.end,x.end)-max(c.start,x.start))
            shorter=max(0.001,min(c.end-c.start,x.end-x.start))
            if overlap/shorter >= overlap_ratio:
                duplicate=True; break
        if not duplicate: chosen.append(c)
        if len(chosen)>=limit: break
    return chosen
