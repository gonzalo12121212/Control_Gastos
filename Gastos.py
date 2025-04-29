import os
import json
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from tkcalendar import DateEntry
from datetime import datetime
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import pandas as pd

CONFIG_FILE = 'config.json'
DB_FILE = 'gastos.db'

def load_config():
    default = {'salary': 0.0,
               'categories': ['comida','servicios','transporte','ocio']}
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE,'w') as f:
            json.dump(default,f,indent=4)
        return default
    with open(CONFIG_FILE,'r') as f:
        return json.load(f)

def save_config(cfg):
    with open(CONFIG_FILE,'w') as f:
        json.dump(cfg,f,indent=4)

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS transacciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            categoria TEXT,
            tipo TEXT,
            monto REAL
        )
    ''')
    conn.commit()
    conn.close()

def fetch_all():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query('SELECT * FROM transacciones ORDER BY id', conn)
    conn.close()
    return df

def add_record(fecha,categoria,tipo,monto):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('INSERT INTO transacciones (fecha,categoria,tipo,monto) VALUES (?,?,?,?)',
              (fecha,categoria,tipo,monto))
    conn.commit()
    conn.close()

class CustomInput(tk.Toplevel):
    def __init__(self, parent, title, label, initial='', width=450):
        super().__init__(parent)
        self.title(title)
        ttk.Label(self, text=label).pack(padx=10,pady=(10,0))
        self.entry = ttk.Entry(self, width=40)
        self.entry.pack(padx=10,pady=5)
        self.entry.insert(0, initial)
        ttk.Button(self, text="OK", command=self._on_ok).pack(pady=(0,10))
        self.geometry(f"{width}x120")
        self.entry.focus()
        self.result = None
        self.transient(parent)
        self.grab_set()
        parent.wait_window(self)

    def _on_ok(self):
        self.result = self.entry.get().strip()
        self.destroy()

class GastosApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Gestor de Gastos Completo')
        self.geometry('1000x650')
        self.config_data = load_config()
        init_db()
        self._create_menu()
        self._create_toolbar()
        self._create_filters()
        self._create_treeview()
        self._create_chart_area()
        self._create_status_bar()
        self._refresh_table()
        self._check_month_alert()

    def _create_menu(self):
        menubar = tk.Menu(self)
        file = tk.Menu(menubar, tearoff=0)
        file.add_command(label='Exportar a Excel',command=self.export_excel)
        file.add_command(label='Exportar a PDF',command=self.export_pdf)
        file.add_separator()
        file.add_command(label='Salir',command=self.destroy)
        menubar.add_cascade(label='Archivo',menu=file)

        cfg = tk.Menu(menubar, tearoff=0)
        cfg.add_command(label='Configurar Salario',command=self._config_salary)
        cfg.add_command(label='Administrar Categorías',command=self._manage_categories)
        menubar.add_cascade(label='Configuración',menu=cfg)

        rep = tk.Menu(menubar, tearoff=0)
        rep.add_command(label='Resumen General',command=self.view_summary)
        rep.add_command(label='Gráfico Gastos x Categoría',command=self.plot_pie)
        menubar.add_cascade(label='Reportes',menu=rep)

        self.config(menu=menubar)

    def _create_toolbar(self):
        tb = ttk.Frame(self,padding=5)
        ttk.Button(tb,text='➕ Agregar',command=self._on_add).pack(side='left',padx=2)
        ttk.Button(tb,text='✏️ Modificar',command=self._on_edit).pack(side='left',padx=2)
        ttk.Button(tb,text='🗑️ Eliminar',command=self._on_delete).pack(side='left',padx=2)
        tb.pack(fill='x')

    def _create_filters(self):
        frm = ttk.Frame(self,padding=5)
        ttk.Label(frm,text='Desde:').pack(side='left')
        self.from_date = DateEntry(frm,width=12);self.from_date.pack(side='left',padx=5)
        ttk.Label(frm,text='Hasta:').pack(side='left')
        self.to_date = DateEntry(frm,width=12);self.to_date.pack(side='left',padx=5)
        ttk.Button(frm,text='Filtrar',command=self._on_filter).pack(side='left',padx=5)
        frm.pack(fill='x')

    def _create_treeview(self):
        cols = ('id','fecha','categoria','tipo','monto')
        self.tree = ttk.Treeview(self,columns=cols,show='headings')
        w={'id':40,'fecha':180,'categoria':120,'tipo':80,'monto':120}
        for c in cols:
            self.tree.heading(c,text=c.title(),command=lambda c=c:self._sort_by(c))
            self.tree.column(c,anchor='center',width=w[c],minwidth=w[c])
        self.tree.pack(expand=True,fill='both',pady=5)

    def _create_chart_area(self):
        self.fig,self.ax = plt.subplots(figsize=(4,3))
        self.canvas = FigureCanvasTkAgg(self.fig,master=self)
        self.canvas.get_tk_widget().pack(side='right',fill='both',expand=True)

    def _create_status_bar(self):
        self.status = ttk.Label(self,text=f"Salario: {self.config_data['salary']:.2f}",anchor='e')
        self.status.pack(fill='x',side='bottom')

    def _update_status(self):
        self.status.config(text=f"Salario: {self.config_data['salary']:.2f}")

    def _refresh_table(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        df = fetch_all()
        for _,r in df.iterrows(): self.tree.insert('','end',values=tuple(r))

    def _on_add(self):
        dlg = AddDialog(self)
        if dlg.result: add_record(*dlg.result); self._refresh_table()

    def _on_edit(self):
        sel = self.tree.selection()
        if not sel: messagebox.showwarning('Aviso','Selecciona un registro'); return
        vals = self.tree.item(sel[0])['values']
        dlg = EditDialog(self,vals)
        if dlg.result:
            conn=sqlite3.connect(DB_FILE);c=conn.cursor()
            c.execute('UPDATE transacciones SET fecha=?,categoria=?,tipo=?,monto=? WHERE id=?',
                      (*dlg.result,vals[0]));conn.commit();conn.close()
            self._refresh_table()

    def _on_delete(self):
        sel = self.tree.selection()
        if not sel: messagebox.showwarning('Aviso','Selecciona un registro'); return
        idx = self.tree.item(sel[0])['values'][0]
        conn=sqlite3.connect(DB_FILE);c=conn.cursor()
        c.execute('DELETE FROM transacciones WHERE id=?',(idx,))
        conn.commit();conn.close();self._refresh_table()

    def _on_filter(self):
        start=self.from_date.get_date().strftime('%Y-%m-%d')
        end=self.to_date.get_date().strftime('%Y-%m-%d')
        conn=sqlite3.connect(DB_FILE)
        df=pd.read_sql_query(f"SELECT * FROM transacciones WHERE fecha BETWEEN '{start}' AND '{end} 23:59:59'",conn)
        conn.close();self._refresh_table()
        messagebox.showinfo('Filtrado',f'Mostrando {len(df)} registros')

    def _sort_by(self,col):
        items=[(self.tree.set(k,col),k) for k in self.tree.get_children('')]
        try: items.sort(key=lambda t:float(t[0]))
        except: items.sort(key=lambda t:t[0])
        for i,(_,k) in enumerate(items): self.tree.move(k,'',i)

    def view_summary(self):
        df=fetch_all();ing=df[df.tipo=='ingreso'].monto.sum();gas=df[df.tipo=='gasto'].monto.sum()
        messagebox.showinfo('Resumen General',f'Ingresos: {ing:.2f}\nGastos: {gas:.2f}\nSaldo: {ing-gas:.2f}')

    def plot_pie(self):
        df=fetch_all();grp=df[df.tipo=='gasto'].groupby('categoria').monto.sum()
        self.ax.clear();self.ax.pie(grp,labels=grp.index,autopct='%1.1f%%');self.fig.tight_layout()
        self.canvas.draw()

    def export_excel(self):
        df=fetch_all();file=filedialog.asksaveasfilename(defaultextension='.xlsx')
        if file:df.to_excel(file,index=False);messagebox.showinfo('Exportar','Guardado en Excel')

    def export_pdf(self):
        df=fetch_all();file=filedialog.asksaveasfilename(defaultextension='.pdf')
        if file:
            from reportlab.platypus import SimpleDocTemplate,Table,TableStyle
            from reportlab.lib import colors
            doc=SimpleDocTemplate(file)
            data=[df.columns.tolist()]+df.values.tolist()
            tbl=Table(data)
            tbl.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.grey),('GRID',(0,0),(-1,-1),1,colors.black)]))
            doc.build([tbl]);messagebox.showinfo('Exportar','Guardado en PDF')

    def _config_salary(self):
        dlg=CustomInput(self,'Configurar Salario','Salario mensual:',str(self.config_data['salary']),width=400)
        if dlg.result is not None:
            try:
                val=float(dlg.result);self.config_data['salary']=val;save_config(self.config_data);self._update_status()
            except ValueError:messagebox.showerror('Error','Salario inválido')

    def _manage_categories(self):
        cats=CustomInput(self,'Administrar Categorías','Separadas por coma:',','.join(self.config_data['categories']),width=400)
        if cats.result is not None:
            self.config_data['categories']=[c.strip() for c in cats.result.split(',')]
            save_config(self.config_data)

    def _check_month_alert(self):
        df=fetch_all();mes=datetime.now().strftime('%Y-%m')
        gasto=df[df.fecha.str.startswith(mes) & (df.tipo=='gasto')].monto.sum()
        if gasto>self.config_data['salary']:messagebox.showwarning('Alerta','¡Has excedido tu presupuesto mensual!')

class AddDialog(simpledialog.Dialog):
    def body(self,master):
        ttk.Label(master,text='Categoría:').grid(row=0,column=0)
        self.cat=ttk.Combobox(master,values=self.master.config_data['categories']);self.cat.grid(row=0,column=1)
        ttk.Label(master,text='Tipo:').grid(row=1,column=0)
        self.tipo=ttk.Combobox(master,values=['ingreso','gasto']);self.tipo.grid(row=1,column=1)
        ttk.Label(master,text='Monto:').grid(row=2,column=0)
        self.monto=ttk.Entry(master);self.monto.grid(row=2,column=1)
        return self.cat
    def apply(self):
        fecha=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.result=(fecha,self.cat.get(),self.tipo.get(),float(self.monto.get()))

class EditDialog(AddDialog):
    def __init__(self,parent,record):
        self.record=record;super().__init__(parent,title='Editar Registro')
    def body(self,master):
        super().body(master)
        self.cat.set(self.record[2]);self.tipo.set(self.record[3]);self.monto.insert(0,str(self.record[4]))

if __name__=='__main__':
    app=GastosApp();app.mainloop()
