# to be executed as Jupyter notebook
get_ipython().system('pip install plotly --upgrade')

from plotly import __version__
from plotly.offline import download_plotlyjs, init_notebook_mode, iplot
import json
import plotly.graph_objs as go

print(__version__)  # requires version >= 1.9.0


init_notebook_mode()  # run at the start of every ipython notebook to use plotly.offline this injects the plotly.js source files into the notebook

sce_t = []
sce_y = []
fi_t = []
fi_y = []
n9_t = []
n9_y = []
ex_t = []
ex_y = []
ex_text = []
st_t = []
st_y = []
st_text = []

with open('C:\\Users\\kshileev\\desktop\\logs\\json_new.log') as f:
    for line in f:
        j = json.loads(line)
        timestamp = j['@timestamp']
        if j.get('status', 'None') == 'Start':
            st_t += [timestamp]
            st_y += [10]
            st_text += [j['name']]
        if 'n_ports' in j:
            sce_t += [timestamp]
            sce_y += [j['n_ports']]
        if 'ucsm' in j['name'] and 'n_vlans' in j:
            fi_t += [timestamp]
            fi_y += [j['n_vlans']]
        if 'nexus' in j['name'] and 'n_vlans' in j:
            if 'service' not in j:
                n9_t += [timestamp]
                n9_y += [j['n_vlans']]
        if 'EXCEPTION' in j:
            ex_t += [timestamp]
            ex_y += [1]
            ex_text += [j['EXCEPTION']]

sce = go.Scatter(x=sce_t, y=sce_y, text=['th net-sub-port']*len(sce_t), name='load', mode='markers')
fi = go.Scatter(x=fi_t, y=fi_y, text=['vlans']*len(fi_t), name='FI', mode='markers')
n9 = go.Scatter(x=n9_t, y=n9_y, text=['vlans']*len(n9_t), name='N9K', mode='markers')
ex = go.Scatter(x=ex_t, y=ex_y, text=ex_text, name='Exceptions={0}'.format(len(ex_t)), mode='markers')
st = go.Scatter(x=st_t, y=st_y, text=st_text, name='Starts={0}'.format(len(st_t)), mode='markers')

data = [st, ex, sce, fi, n9]

iplot(data)
