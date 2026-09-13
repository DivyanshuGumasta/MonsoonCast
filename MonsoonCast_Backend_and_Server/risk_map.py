from __future__ import annotations
import json
from pathlib import Path
from typing import Any
RISK_COLORS={'break':'#d73027','onset':'#4575b4','active':'#1a9850','revival':'#91bfdb','normal':'#bdbdbd'}
CELL_HALF_WIDTH_DEG=0.025
def _dominant_risk(probs): return max(probs,key=probs.get),probs[max(probs,key=probs.get)]
def _cell_polygon(lat,lon):
    w=CELL_HALF_WIDTH_DEG
    return {'type':'Polygon','coordinates':[[[lon-w,lat-w],[lon+w,lat-w],[lon+w,lat+w],[lon-w,lat+w],[lon-w,lat-w]]]}
def build_cell_risk_geojson(outlooks,lead_bucket='7d'):
    features=[]
    for o in outlooks:
        probs=o['outlook'].get(lead_bucket)
        if not probs:continue
        label,confidence=_dominant_risk(probs)
        features.append({'type':'Feature','geometry':_cell_polygon(o['latitude'],o['longitude']),'properties':{'grid_key':o['grid_key'],'lead_bucket':lead_bucket,'dominant_risk':label,'confidence':confidence,'color':RISK_COLORS.get(label,RISK_COLORS['normal']),'probabilities':probs}})
    return {'type':'FeatureCollection','lead_bucket':lead_bucket,'features':features}
def aggregate_to_blocks(cell_geojson,block_boundaries_path):
    from shapely.geometry import shape,Point
    blocks=json.loads(block_boundaries_path.read_text(encoding='utf-8'))
    cell_points=[(Point(f['geometry']['coordinates'][0][0][0]+CELL_HALF_WIDTH_DEG,f['geometry']['coordinates'][0][0][1]+CELL_HALF_WIDTH_DEG),f['properties']) for f in cell_geojson['features']]
    out_features=[]
    for block in blocks['features']:
        poly=shape(block['geometry']); inside=[props for pt,props in cell_points if poly.contains(pt)]
        if not inside:continue
        labels=['onset','active','break','revival','normal']; avg_probs={lbl:round(sum(p['probabilities'].get(lbl,0.0) for p in inside)/len(inside),3) for lbl in labels}; dominant,confidence=_dominant_risk(avg_probs)
        out_features.append({'type':'Feature','geometry':block['geometry'],'properties':{**block['properties'],'dominant_risk':dominant,'confidence':confidence,'color':RISK_COLORS.get(dominant,RISK_COLORS['normal']),'probabilities':avg_probs,'n_cells_aggregated':len(inside)}})
    return {'type':'FeatureCollection','features':out_features}
