import pandas as pd
import sys
import datetime 

mf_map = {
    'samsung': r'\dimmSamsung',
    'kingston': r'\dimmUnknown',
    'hynix': r'\dimmHynix',
    'micron': r'\dimmMicron',
}
# maps the DIMM_DB ID to the ID that we use in the paper
id_map = {
    ('kingston', '11') : '0',
    ('kingston', '14') : '1',
    ('kingston', '15') : '2',
    ('kingston', '16') : '3',
    ('micron', '18') : '0',
    ('micron', '19') : '1',
    ('micron', '20') : '2',
    ('micron', '21') : '3',
    ('micron', '22') : '4',
    ('micron', '24') : '5',
    ('micron', '25') : '6',
    ('micron', '26') : '7',
    ('micron', '27') : '8',
    ('micron', '432') : '9',
    ('samsung', '1') : '0',
    ('samsung', '2') : '1',
    ('samsung', '13') : '2',
    ('samsung', '17') : '3',
    ('samsung', '36') : '4',
    ('samsung', '4') : '5',
    ('samsung', '5') : '6',
    ('samsung', '6') : '7',
    ('samsung', '7') : '8',
    ('samsung', '9') : '9',
    ('samsung', '28') : '10',
    ('samsung', '29') : '11',
    ('samsung', '3') : '12',
    ('samsung', '8') : '13',
    ('samsung', '12') : '14',
    ('samsung', '538') : '15',
    ('samsung', '34') : '16',
    ('samsung', '35') : '17',
    ('samsung', '431') : '18',
    ('samsung', '540') : '19',
    ('hynix', '10') : '0',
    ('hynix', '30') : '1',
    ('hynix', '31') : '2',
    ('hynix', '32') : '3',
    ('hynix', '33') : '4',
    ('hynix', '539') : '5'
}
dm_map = {
    '11': 'kingston',
    '14': 'kingston',
    '15': 'kingston',
    '16': 'kingston',
    '18': 'micron',
    '19': 'micron',
    '20': 'micron',
    '21': 'micron',
    '22': 'micron',
    '24': 'micron',
    '25': 'micron',
    '26': 'micron',
    '27': 'micron',
    '432': 'micron',
    '1': 'samsung',
    '2': 'samsung',
    '13': 'samsung',
    '17': 'samsung',
    '36': 'samsung',
    '4': 'samsung',
    '5': 'samsung',
    '6': 'samsung',
    '7': 'samsung',
    '9': 'samsung',
    '28': 'samsung',
    '29': 'samsung',
    '3': 'samsung',
    '8': 'samsung',
    '12': 'samsung',
    '538': 'samsung',
    '34': 'samsung',
    '35': 'samsung',
    '431': 'samsung',
    '540': 'samsung',
    '10': 'hynix',
    '30': 'hynix',
    '31': 'hynix',
    '32': 'hynix',
    '33': 'hynix',
    '539': 'hynix'
}


def id_to_tex(dimm_id : str, manufacturer : str = None):
    if manufacturer is None:
        manufacturer = dm_map[dimm_id]

    mf_abbv = ''
    latex_code = ''
    for mf, mfs in mf_map.items():
        if mf in manufacturer.lower().strip():
            mf_abbv = mf
            latex_code = mfs
            break
    # print('mf_abbv: ', mf_abbv)
    # print('manufacturer: ', manufacturer.lower().strip())
    # print('latex_code: ', mfs)
    
    if (mf_abbv, dimm_id) in id_map:
        return latex_code + '{' f"{id_map[(mf_abbv, dimm_id)]}" + '}'

    print("ERROR: Not found!")


def pp_timeformat(dt):
    t_str = str(datetime.timedelta(seconds=dt))
    res_str = f""
    h,m,s = [int(x) for x in t_str.split(":")]
    if h: 
        res_str += f"\\SI{{{h:>3}}}{{\\hour}} "
    if m:
        res_str += f"\\SI{{{m:>2}}}{{\\minute}} "
    if s:
        res_str += f"\\SI{{{s:>2}}}{{\\second}} "
    return f"{res_str:>50}"

def short_pp_timeformat(dt):
    m, s = divmod(dt, 60)
    h, m = divmod(m, 60)
    res_str = f""
    use_sec = True 
    if h: 
        res_str += f" {h:>3}h"
        use_sec = False 
    if m:
        if not use_sec and s > 30:
            m+=1
        res_str += f" {m:>2}m"
    if s and use_sec:
        res_str += f" {s:>2}s"
    return f"{res_str:>13}"

with open(sys.argv[1]) as f:
    data = pd.read_csv(f)


strings = []

for dimm,v in data.groupby(['dimm_id']):
    dimm = str(dimm)
    export_str = f"{id_to_tex(dimm):>17} &"
    for expl, vv in v.groupby('expl_name'):
        try:
            mean_ttf = short_pp_timeformat(int(vv['mean_ttf'].values[0]))
        except ValueError:
            mean_ttf = "--"
            expl_flips = "--"
            export_str += f"{expl_flips:>10} & {mean_ttf:>14} &  "
            continue

        expl_flips = int(vv['tot_expl_flips'].values[0])
        mean_ttf += "*" if expl_flips == 1 else " "
        export_str += f"{expl_flips:>10} & {mean_ttf:>14} &  "
   
        
    exp_list = list(export_str)  
    exp_list[-3:] = f"\\\\"
    export_str = ''.join(exp_list)
    strings.append(export_str)

for sstr in sorted(strings):
    print(sstr)
