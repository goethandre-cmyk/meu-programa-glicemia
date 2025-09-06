import tkinter as tk
from tkinter import messagebox, ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import os
from logica import (AcompanhamentoDiario, carregar_alimentos, salvar_alimento_csv, 
                     calcular_idade, classificar_glicemia, get_cor_glicemia, 
                     carregar_utilizadores, salvar_utilizador)

# Variáveis globais para a GUI
utilizador_logado = None
role_logado = None
alimentos_globais = []
menu_refeicao_admin = None
menu_refeicao_user = None
var_tipo_filtro = None
var_utilizador_filtro = None
tree_registos = None
frames = {}
label_utilizador = None
acompanhamento = None
var_refeicao_admin = None
var_refeicao_user = None
var_tipo_admin = None
var_tipo_user = None

def atualizar_menus_alimentos():
    global alimentos_globais, menu_refeicao_admin, menu_refeicao_user, var_refeicao_admin, var_refeicao_user
    alimentos_globais = carregar_alimentos()

    if menu_refeicao_admin and alimentos_globais:
        menu = menu_refeicao_admin['menu']
        menu.delete(0, 'end')
        for alimento in alimentos_globais:
            menu.add_command(label=alimento, command=tk._setit(var_refeicao_admin, alimento))
        if alimentos_globais:
            var_refeicao_admin.set(alimentos_globais[0])

    if menu_refeicao_user and alimentos_globais:
        menu = menu_refeicao_user['menu']
        menu.delete(0, 'end')
        for alimento in alimentos_globais:
            menu.add_command(label=alimento, command=tk._setit(var_refeicao_user, alimento))
        if alimentos_globais:
            var_refeicao_user.set(alimentos_globais[0])

def adicionar_alimento_gui():
    janela_alimento = tk.Toplevel()
    janela_alimento.title("Adicionar Novo Alimento")
    
    frame_alimento = tk.Frame(janela_alimento, padx=10, pady=10)
    frame_alimento.pack()
    
    tk.Label(frame_alimento, text="Nome do Alimento:").grid(row=0, column=0, sticky="w")
    entry_nome = tk.Entry(frame_alimento)
    entry_nome.grid(row=0, column=1)

    tk.Label(frame_alimento, text="Tipo (ex: Carboidrato):").grid(row=1, column=0, sticky="w")
    entry_tipo = tk.Entry(frame_alimento)
    entry_tipo.grid(row=1, column=1)
    
    tk.Label(frame_alimento, text="Carboidratos (g):").grid(row=2, column=0, sticky="w")
    entry_carbs = tk.Entry(frame_alimento)
    entry_carbs.grid(row=2, column=1)
    
    tk.Label(frame_alimento, text="Proteínas (g):").grid(row=3, column=0, sticky="w")
    entry_protein = tk.Entry(frame_alimento)
    entry_protein.grid(row=3, column=1)
    
    tk.Label(frame_alimento, text="Gorduras (g):").grid(row=4, column=0, sticky="w")
    entry_fat = tk.Entry(frame_alimento)
    entry_fat.grid(row=4, column=1)
    
    tk.Label(frame_alimento, text="Açúcares Totais (g):").grid(row=5, column=0, sticky="w")
    entry_acucares = tk.Entry(frame_alimento)
    entry_acucares.grid(row=5, column=1)
    
    tk.Label(frame_alimento, text="Gorduras Saturadas (g):").grid(row=6, column=0, sticky="w")
    entry_gord_sat = tk.Entry(frame_alimento)
    entry_gord_sat.grid(row=6, column=1)

    tk.Label(frame_alimento, text="Sódio (mg):").grid(row=7, column=0, sticky="w")
    entry_sodio = tk.Entry(frame_alimento)
    entry_sodio.grid(row=7, column=1)
    
    def salvar_e_fechar():
        nome = entry_nome.get()
        tipo = entry_tipo.get()
        carbs = entry_carbs.get()
        protein = entry_protein.get()
        fat = entry_fat.get()
        acucares = entry_acucares.get()
        gord_sat = entry_gord_sat.get()
        sodio = entry_sodio.get()
        
        if not nome or not tipo:
            messagebox.showerror("Erro", "Nome e tipo são obrigatórios.")
            return

        if salvar_alimento_csv(nome, tipo, carbs, protein, fat, acucares, gord_sat, sodio):
            messagebox.showinfo("Sucesso", f"Alimento '{nome}' adicionado com sucesso.")
            atualizar_menus_alimentos()
            janela_alimento.destroy()
    
    btn_salvar = tk.Button(frame_alimento, text="Salvar Alimento", command=salvar_e_fechar)
    btn_salvar.grid(row=8, column=0, columnspan=2, pady=10)

def mostrar_frame(nome_frame):
    for frame in frames.values():
        frame.grid_forget()
    frames[nome_frame].grid(row=0, column=0, sticky="nsew")

def mostrar_ecran_registo(janela):
    global role_logado
    if role_logado == 'admin':
        atualizar_menu_selecao_utilizador()
        mostrar_frame("registo_admin")
    else:
        mostrar_frame("registo_user")

def mostrar_menu_principal(janela):
    for widget in frames["menu"].winfo_children():
        widget.destroy()
    
    menu_widgets = tk.Frame(frames["menu"])
    menu_widgets.pack(expand=True)
    
    menu_widgets.grid_rowconfigure(0, weight=1)
    menu_widgets.grid_rowconfigure(1, weight=1)
    menu_widgets.grid_rowconfigure(2, weight=1)
    menu_widgets.grid_rowconfigure(3, weight=1)
    menu_widgets.grid_columnconfigure(0, weight=1)
    
    tk.Label(menu_widgets, text="Escolha uma opção:", font=("Arial", 16)).grid(row=0, column=0, pady=20)
    
    btn_registo = tk.Button(menu_widgets, text="Novo Registo", font=("Arial", 12), command=lambda: mostrar_ecran_registo(janela))
    btn_registo.grid(row=1, column=0, sticky="ew", padx=50, pady=5)

    btn_consulta = tk.Button(menu_widgets, text="Consultar Registos", font=("Arial", 12), command=lambda: [mostrar_frame("consulta"), var_utilizador_filtro.set("Todos"), atualizar_menu_utilizadores(), mostrar_registos_gui()])
    btn_consulta.grid(row=2, column=0, sticky="ew", padx=50, pady=5)
    
    if role_logado == 'admin':
        btn_gerir_utilizadores = tk.Button(menu_widgets, text="Gestão Administrativa", font=("Arial", 12), command=lambda: mostrar_frame("admin_gerenciamento"))
        btn_gerir_utilizadores.grid(row=3, column=0, sticky="ew", padx=50, pady=5)
        
    btn_sair = tk.Button(menu_widgets, text="Sair", font=("Arial", 12), command=janela.quit)
    btn_sair.grid(row=4, column=0, sticky="ew", padx=50, pady=5)

    mostrar_frame("menu")

def login_gui(janela, entry_login_user, entry_login_pass):
    global utilizador_logado, role_logado
    username = entry_login_user.get()
    password = entry_login_pass.get()
    
    utilizadores = carregar_utilizadores()
    if username in utilizadores and utilizadores[username]['password'] == password:
        utilizador_logado = username
        role_logado = utilizadores[username]['role']
        messagebox.showinfo("Sucesso", f"Bem-vindo, {username.capitalize()}!")
        label_utilizador.config(text=f"Utilizador: {utilizador_logado.capitalize()}")
        mostrar_menu_principal(janela)
    else:
        messagebox.showerror("Erro", "Nome de utilizador ou senha incorretos.")

def criar_conta_gui(entry_login_user, entry_login_pass):
    username = entry_login_user.get()
    password = entry_login_pass.get()
    
    if not username or not password:
        messagebox.showerror("Erro", "O nome de utilizador e a senha não podem estar vazios.")
        return

    if salvar_utilizador(username, password, 'user', 'Não informado', 'Não informado'):
        messagebox.showinfo("Sucesso", "Conta criada com sucesso! Faça login para continuar.")
        entry_login_user.delete(0, tk.END)
        entry_login_pass.delete(0, tk.END)

def criar_utilizador_admin_gui(entry_novo_user, entry_nova_senha, entry_nova_data_nasc, var_novo_sexo, var_nova_role):
    username = entry_novo_user.get()
    password = entry_nova_senha.get()
    data_nascimento = entry_nova_data_nasc.get()
    sexo = var_novo_sexo.get()
    role = var_nova_role.get()

    if not username or not password or not data_nascimento:
        messagebox.showerror("Erro", "Todos os campos são obrigatórios.")
        return
    
    if salvar_utilizador(username, password, role, data_nascimento, sexo):
        messagebox.showinfo("Sucesso", f"Utilizador '{username}' criado com sucesso!")
        entry_novo_user.delete(0, tk.END)
        entry_nova_senha.delete(0, tk.END)
        entry_nova_data_nasc.delete(0, tk.END)

def adicionar_registo_admin_gui(entry_valor_admin, entry_descricao_admin, var_utilizador_registo, var_tipo_admin, var_refeicao_admin):
    try:
        utilizador_selecionado = var_utilizador_registo.get()
        if not utilizador_selecionado:
            messagebox.showerror("Erro", "Selecione um utilizador.")
            return

        utilizadores = carregar_utilizadores()
        dados_utilizador = utilizadores[utilizador_selecionado]
        data_nascimento = dados_utilizador['data_nascimento']
        sexo = dados_utilizador['sexo']
        
        idade = calcular_idade(data_nascimento)

        valor = float(entry_valor_admin.get())
        tipo_selecionado = var_tipo_admin.get().lower()
        descricao = entry_descricao_admin.get()
        refeicao = var_refeicao_admin.get()
        
        classificacao = classificar_glicemia(valor, idade)
        mensagem = acompanhamento.adicionar_registo(tipo_selecionado, valor, descricao, utilizador_selecionado, data_nascimento, sexo, refeicao)
        
        messagebox.showinfo("Sucesso", f"{mensagem}\nClassificação: {classificacao}")
        
        entry_valor_admin.delete(0, tk.END)
        entry_descricao_admin.delete(0, tk.END)
        
        atualizar_menu_selecao_utilizador()
        atualizar_menu_utilizadores()

    except ValueError:
        messagebox.showerror("Erro", "Valores inválidos. Verifique se a glicemia é um número.")

def atualizar_menu_selecao_utilizador():
    utilizadores = carregar_utilizadores()
    lista_de_utilizadores = sorted(list(utilizadores.keys()))
    menu = frames["registo_admin"]._menu_utilizador_registo["menu"]
    menu.delete(0, "end")
    for utilizador in lista_de_utilizadores:
        menu.add_command(label=utilizador, command=tk._setit(frames["registo_admin"].var_utilizador_registo, utilizador))
    if lista_de_utilizadores:
        frames["registo_admin"].var_utilizador_registo.set(lista_de_utilizadores[0])
    else:
        frames["registo_admin"].var_utilizador_registo.set("")

def adicionar_registo_user_gui(entry_valor_user, entry_descricao_user, var_tipo_user, var_refeicao_user):
    global utilizador_logado
    
    if utilizador_logado is None:
        messagebox.showerror("Erro", "Não há utilizador logado.")
        return

    try:
        utilizadores = carregar_utilizadores()
        dados_utilizador = utilizadores[utilizador_logado]
        data_nascimento = dados_utilizador['data_nascimento']
        sexo = dados_utilizador['sexo']
        
        idade = calcular_idade(data_nascimento)

        valor = float(entry_valor_user.get())
        tipo_selecionado = var_tipo_user.get().lower()
        descricao = entry_descricao_user.get()
        refeicao = var_refeicao_user.get()
        
        if not tipo_selecionado:
            messagebox.showerror("Erro", "O tipo de medição é obrigatório.")
            return

        classificacao = classificar_glicemia(valor, idade)
        mensagem = acompanhamento.adicionar_registo(tipo_selecionado, valor, descricao, utilizador_logado, data_nascimento, sexo, refeicao)
        
        messagebox.showinfo("Sucesso", f"{mensagem}\nClassificação: {classificacao}")
        
        entry_valor_user.delete(0, tk.END)
        entry_descricao_user.delete(0, tk.END)
        
        atualizar_menu_utilizadores()

    except ValueError:
        messagebox.showerror("Erro", "Valores inválidos. Verifique se a glicemia é um número.")

def mostrar_registos_gui():
    for item in tree_registos.get_children():
        tree_registos.delete(item)

    tipo_selecionado = var_tipo_filtro.get()
    
    if role_logado == 'admin':
        utilizador_selecionado = var_utilizador_filtro.get()
    else:
        utilizador_selecionado = utilizador_logado

    registos_filtrados = acompanhamento.mostrar_registos(tipo_selecionado, utilizador_selecionado)
    
    if not registos_filtrados:
        tree_registos.insert("", "end", values=("Nenhum registo encontrado.", "", "", "", "", "", ""))
        return

    for reg in registos_filtrados:
        cor = get_cor_glicemia(reg.valor, calcular_idade(reg.data_nascimento))
        tree_registos.insert("", "end", values=(
            reg.data.strftime("%d-%m-%Y %H:%M:%S"),
            reg.utilizador.capitalize(),
            reg.tipo.capitalize(),
            reg.valor,
            reg.descricao,
            reg.refeicao,
            classificar_glicemia(reg.valor, calcular_idade(reg.data_nascimento))
        ), tags=(cor,))

    tree_registos.tag_configure('green', foreground='green')
    tree_registos.tag_configure('orange', foreground='orange')
    tree_registos.tag_configure('red', foreground='red')
    
def salvar_registos_gui():
    mensagem = acompanhamento.salvar_para_csv()
    messagebox.showinfo("Salvar", mensagem)

def carregar_registos_gui():
    acompanhamento.registos = acompanhamento.carregar_de_csv()
    messagebox.showinfo("Carregar", "Registos carregados com sucesso.")
    atualizar_menu_utilizadores()
    mostrar_registos_gui()

def limpar_registos_gui():
    confirmar = messagebox.askyesno("Confirmar Limpeza", "Tem certeza que deseja apagar todos os registos? Esta ação não pode ser desfeita.")
    if confirmar:
        mensagem = acompanhamento.limpar_registos()
        messagebox.showinfo("Limpeza", mensagem)
        atualizar_menu_utilizadores()

def get_utilizadores_registos():
    utilizadores_unicos = set()
    for reg in acompanhamento.registos:
        utilizadores_unicos.add(reg.utilizador)
    return ["Todos"] + sorted(list(utilizadores_unicos))

def atualizar_menu_utilizadores():
    if role_logado == 'admin':
        menu = frames["consulta"]._menu_utilizador_filtro["menu"]
        menu.delete(0, "end")
        novos_utilizadores = get_utilizadores_registos()
        for utilizador in novos_utilizadores:
            menu.add_command(label=utilizador, command=tk._setit(var_utilizador_filtro, utilizador))
        if var_utilizador_filtro.get() not in novos_utilizadores:
            var_utilizador_filtro.set("Todos")

def mostrar_grafico_glicemia():
    tipo_selecionado = var_tipo_filtro.get()
    
    if role_logado == 'admin':
        utilizador_selecionado = var_utilizador_filtro.get()
    else:
        utilizador_selecionado = utilizador_logado

    registos = acompanhamento.mostrar_registos(tipo_selecionado, utilizador_selecionado)

    if not registos:
        messagebox.showinfo("Gráfico", "Não há dados para gerar o gráfico.")
        return

    datas = [reg.data for reg in registos]
    valores = [reg.valor for reg in registos]
    
    janela_grafico = tk.Toplevel()
    janela_grafico.title("Gráfico de Glicemia")
    
    figura, ax = plt.subplots(figsize=(8, 6), facecolor='white')
    ax.plot(datas, valores, marker='o', linestyle='-')
    ax.set_title('Evolução dos Níveis de Glicemia')
    ax.set_xlabel('Data')
    ax.set_ylabel('Valor de Glicemia')
    ax.grid(True)
    figura.autofmt_xdate()

    canvas = FigureCanvasTkAgg(figura, master=janela_grafico)
    canvas.draw()
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    janela_grafico.mainloop()

def criar_gui():
    global acompanhamento, label_utilizador, var_tipo_filtro, var_utilizador_filtro, tree_registos, menu_refeicao_admin, menu_refeicao_user, var_refeicao_admin, var_refeicao_user, var_tipo_admin, var_tipo_user

    acompanhamento = AcompanhamentoDiario()
    janela = tk.Tk()
    janela.title("Acompanhamento de Glicemia")
    janela.geometry("800x600")

    label_utilizador = tk.Label(janela, text="", font=("Arial", 10, "bold"))
    label_utilizador.place(x=780, y=5, anchor="ne")

    # Inicialização de frames
    frame_login = tk.Frame(janela)
    frame_login.grid(row=0, column=0, sticky="nsew")
    frames["login"] = frame_login
    frame_menu = tk.Frame(janela)
    frame_menu.grid(row=0, column=0, sticky="nsew")
    frames["menu"] = frame_menu
    frame_registo_admin = tk.Frame(janela)
    frame_registo_admin.grid(row=0, column=0, sticky="nsew")
    frames["registo_admin"] = frame_registo_admin
    frame_registo_user = tk.Frame(janela)
    frame_registo_user.grid(row=0, column=0, sticky="nsew")
    frames["registo_user"] = frame_registo_user
    frame_consulta = tk.Frame(janela)
    frame_consulta.grid(row=0, column=0, sticky="nsew")
    frames["consulta"] = frame_consulta
    frame_admin_gerenciamento = tk.Frame(janela)
    frame_admin_gerenciamento.grid(row=0, column=0, sticky="nsew")
    frames["admin_gerenciamento"] = frame_admin_gerenciamento

    # Widgets do Frame de Login
    login_widgets = tk.Frame(frame_login)
    login_widgets.pack(expand=True)
    tk.Label(login_widgets, text="Login", font=("Arial", 16)).grid(row=0, column=0, columnspan=2, pady=10)
    tk.Label(login_widgets, text="Utilizador:").grid(row=1, column=0, padx=10, pady=5, sticky="w")
    entry_login_user = tk.Entry(login_widgets)
    entry_login_user.grid(row=1, column=1, padx=10, pady=5)
    tk.Label(login_widgets, text="Senha:").grid(row=2, column=0, padx=10, pady=5, sticky="w")
    entry_login_pass = tk.Entry(login_widgets, show="*")
    entry_login_pass.grid(row=2, column=1, padx=10, pady=5)
    tk.Button(login_widgets, text="Login", command=lambda: login_gui(janela, entry_login_user, entry_login_pass)).grid(row=3, column=0, pady=10)
    tk.Button(login_widgets, text="Criar Conta", command=lambda: criar_conta_gui(entry_login_user, entry_login_pass)).grid(row=3, column=1, pady=10)

    # Widgets do Frame de Gestão Administrativa
    gerir_widgets = tk.Frame(frame_admin_gerenciamento)
    gerir_widgets.pack(expand=True)
    tk.Label(gerir_widgets, text="Gestão Administrativa", font=("Arial", 16)).grid(row=0, column=0, columnspan=2, pady=10)
    tk.Label(gerir_widgets, text="Gerir Utilizadores", font=("Arial", 12, "bold")).grid(row=1, column=0, columnspan=2, pady=5)
    tk.Label(gerir_widgets, text="Utilizador:").grid(row=2, column=0, padx=10, pady=5, sticky="w")
    entry_novo_user = tk.Entry(gerir_widgets)
    entry_novo_user.grid(row=2, column=1, padx=10, pady=5)
    tk.Label(gerir_widgets, text="Senha:").grid(row=3, column=0, padx=10, pady=5, sticky="w")
    entry_nova_senha = tk.Entry(gerir_widgets, show="*")
    entry_nova_senha.grid(row=3, column=1, padx=10, pady=5)
    tk.Label(gerir_widgets, text="Função:").grid(row=4, column=0, padx=10, pady=5, sticky="w")
    opcoes_role = ["user", "admin"]
    var_nova_role = tk.StringVar(janela)
    var_nova_role.set(opcoes_role[0])
    menu_nova_role = tk.OptionMenu(gerir_widgets, var_nova_role, *opcoes_role)
    menu_nova_role.grid(row=4, column=1, padx=10, pady=5, sticky="ew")
    tk.Label(gerir_widgets, text="Data de Nasc. (dd/mm/aaaa):").grid(row=5, column=0, padx=10, pady=5, sticky="w")
    entry_nova_data_nasc = tk.Entry(gerir_widgets)
    entry_nova_data_nasc.grid(row=5, column=1, padx=10, pady=5)
    tk.Label(gerir_widgets, text="Sexo:").grid(row=6, column=0, padx=10, pady=5, sticky="w")
    opcoes_sexo = ["Masculino", "Feminino"]
    var_novo_sexo = tk.StringVar(janela)
    var_novo_sexo.set(opcoes_sexo[0])
    menu_novo_sexo = tk.OptionMenu(gerir_widgets, var_novo_sexo, *opcoes_sexo)
    menu_novo_sexo.grid(row=6, column=1, padx=10, pady=5, sticky="ew")
    tk.Button(gerir_widgets, text="Criar Utilizador", command=lambda: criar_utilizador_admin_gui(entry_novo_user, entry_nova_senha, entry_nova_data_nasc, var_novo_sexo, var_nova_role)).grid(row=7, column=0, columnspan=2, pady=10)
    tk.Label(gerir_widgets, text="Gerir Alimentos", font=("Arial", 12, "bold")).grid(row=8, column=0, columnspan=2, pady=5)
    btn_adicionar_alimento = tk.Button(gerir_widgets, text="Adicionar Novo Alimento", command=adicionar_alimento_gui)
    btn_adicionar_alimento.grid(row=9, column=0, columnspan=2, pady=10)
    tk.Button(gerir_widgets, text="Voltar ao Menu", command=lambda: mostrar_frame("menu")).grid(row=10, column=0, columnspan=2, pady=10)

    # Widgets do Frame de Novo Registo para Administradores
    registo_admin_widgets = tk.Frame(frame_registo_admin)
    registo_admin_widgets.pack(expand=True)
    tk.Label(registo_admin_widgets, text="Novo Registo (Admin)", font=("Arial", 16)).grid(row=0, column=0, columnspan=2, pady=10)
    tk.Label(registo_admin_widgets, text="Selecionar Utilizador:").grid(row=1, column=0, padx=10, pady=5, sticky="w")
    frame_registo_admin.var_utilizador_registo = tk.StringVar(janela)
    frame_registo_admin._menu_utilizador_registo = tk.OptionMenu(registo_admin_widgets, frame_registo_admin.var_utilizador_registo, "")
    frame_registo_admin._menu_utilizador_registo.grid(row=1, column=1, padx=10, pady=5, sticky="ew")
    tk.Label(registo_admin_widgets, text="Tipo de Medição:").grid(row=2, column=0, padx=10, pady=5, sticky="w")
    opcoes_tipo = ["Glicemia", "Jejum", "Antes do Almoço", "Apos o Almoço", "Antes do Jantar", "Apos o Jantar", "Antes de Dormir", "Apos Exercicio", "Outro"]
    var_tipo_admin = tk.StringVar(janela)
    var_tipo_admin.set(opcoes_tipo[0])
    menu_tipo_admin = tk.OptionMenu(registo_admin_widgets, var_tipo_admin, *opcoes_tipo)
    menu_tipo_admin.grid(row=2, column=1, padx=10, pady=5, sticky="ew")
    tk.Label(registo_admin_widgets, text="Valor da Glicemia (mg/dL):").grid(row=3, column=0, padx=10, pady=5, sticky="w")
    entry_valor_admin = tk.Entry(registo_admin_widgets)
    entry_valor_admin.grid(row=3, column=1, padx=10, pady=5)
    tk.Label(registo_admin_widgets, text="Descrição:").grid(row=4, column=0, padx=10, pady=5, sticky="w")
    entry_descricao_admin = tk.Entry(registo_admin_widgets, width=40)
    entry_descricao_admin.grid(row=4, column=1, padx=10, pady=5)
    tk.Label(registo_admin_widgets, text="Refeição:").grid(row=5, column=0, padx=10, pady=5, sticky="w")
    alimentos = carregar_alimentos()
    var_refeicao_admin = tk.StringVar(janela)
    if alimentos:
        var_refeicao_admin.set(alimentos[0])
        menu_refeicao_admin = tk.OptionMenu(registo_admin_widgets, var_refeicao_admin, *alimentos)
    else:
        var_refeicao_admin.set("Nenhum alimento")
        menu_refeicao_admin = tk.OptionMenu(registo_admin_widgets, var_refeicao_admin, "Nenhum alimento")
    menu_refeicao_admin.grid(row=5, column=1, padx=10, pady=5, sticky="ew")
    btn_frame_registo_admin = tk.Frame(registo_admin_widgets)
    btn_frame_registo_admin.grid(row=6, column=0, columnspan=2, pady=10)
    btn_adicionar_admin = tk.Button(btn_frame_registo_admin, text="Adicionar Registo", command=lambda: adicionar_registo_admin_gui(entry_valor_admin, entry_descricao_admin, frame_registo_admin.var_utilizador_registo, var_tipo_admin, var_refeicao_admin))
    btn_adicionar_admin.grid(row=0, column=0, padx=5)
    tk.Button(btn_frame_registo_admin, text="Voltar", command=lambda: mostrar_frame("menu")).grid(row=0, column=1, padx=5)

    # Widgets do Frame de Novo Registo para Utilizadores Comuns
    registo_user_widgets = tk.Frame(frame_registo_user)
    registo_user_widgets.pack(expand=True)
    tk.Label(registo_user_widgets, text="Novo Registo", font=("Arial", 16)).grid(row=0, column=0, columnspan=2, pady=10)
    tk.Label(registo_user_widgets, text="Tipo de Medição:").grid(row=1, column=0, padx=10, pady=5, sticky="w")
    opcoes_tipo = ["Glicemia", "Jejum", "Antes do Almoço", "Apos o Almoço", "Antes do Jantar", "Apos o Jantar", "Antes de Dormir", "Apos Exercicio", "Outro"]
    var_tipo_user = tk.StringVar(janela)
    var_tipo_user.set(opcoes_tipo[0])
    menu_tipo_user = tk.OptionMenu(registo_user_widgets, var_tipo_user, *opcoes_tipo)
    menu_tipo_user.grid(row=1, column=1, padx=10, pady=5, sticky="ew")
    tk.Label(registo_user_widgets, text="Valor da Glicemia (mg/dL):").grid(row=2, column=0, padx=10, pady=5, sticky="w")
    entry_valor_user = tk.Entry(registo_user_widgets)
    entry_valor_user.grid(row=2, column=1, padx=10, pady=5)
    tk.Label(registo_user_widgets, text="Descrição:").grid(row=3, column=0, padx=10, pady=5, sticky="w")
    entry_descricao_user = tk.Entry(registo_user_widgets, width=40)
    entry_descricao_user.grid(row=3, column=1, padx=10, pady=5)
    tk.Label(registo_user_widgets, text="Refeição:").grid(row=4, column=0, padx=10, pady=5, sticky="w")
    alimentos = carregar_alimentos()
    var_refeicao_user = tk.StringVar(janela)
    if alimentos:
        var_refeicao_user.set(alimentos[0])
        menu_refeicao_user = tk.OptionMenu(registo_user_widgets, var_refeicao_user, *alimentos)
    else:
        var_refeicao_user.set("Nenhum alimento")
        menu_refeicao_user = tk.OptionMenu(registo_user_widgets, var_refeicao_user, "Nenhum alimento")
    menu_refeicao_user.grid(row=4, column=1, padx=10, pady=5, sticky="ew")
    btn_frame_registo_user = tk.Frame(registo_user_widgets)
    btn_frame_registo_user.grid(row=5, column=0, columnspan=2, pady=10)
    btn_adicionar_user = tk.Button(btn_frame_registo_user, text="Adicionar Registo", command=lambda: adicionar_registo_user_gui(entry_valor_user, entry_descricao_user, var_tipo_user, var_refeicao_user))
    btn_adicionar_user.grid(row=0, column=0, padx=5)
    tk.Button(btn_frame_registo_user, text="Voltar", command=lambda: mostrar_frame("menu")).grid(row=0, column=1, padx=5)

    # Widgets do Frame de Consulta de Registos
    consulta_widgets = tk.Frame(frame_consulta)
    consulta_widgets.pack(fill=tk.BOTH, expand=True)
    filtro_frame = tk.Frame(consulta_widgets)
    filtro_frame.pack(fill=tk.X, pady=5)
    tk.Label(filtro_frame, text="Filtrar por:").pack(side=tk.LEFT, padx=5)
    opcoes_filtro_tipo = ["Todos", "Glicemia", "Jejum", "Antes do Almoço", "Apos o Almoço", "Antes do Jantar", "Apos o Jantar", "Antes de Dormir", "Apos Exercicio", "Outro"]
    var_tipo_filtro = tk.StringVar(janela)
    var_tipo_filtro.set(opcoes_filtro_tipo[0])
    menu_filtro_tipo = tk.OptionMenu(filtro_frame, var_tipo_filtro, *opcoes_filtro_tipo)
    menu_filtro_tipo.pack(side=tk.LEFT, padx=5)
    if role_logado == 'admin':
        var_utilizador_filtro = tk.StringVar(janela)
        frames["consulta"]._menu_utilizador_filtro = tk.OptionMenu(filtro_frame, var_utilizador_filtro, "Todos")
        frames["consulta"]._menu_utilizador_filtro.pack(side=tk.LEFT, padx=5)
    btn_consulta_frame = tk.Frame(consulta_widgets)
    btn_consulta_frame.pack(fill=tk.X, pady=5)
    btn_mostrar = tk.Button(btn_consulta_frame, text="Mostrar", command=mostrar_registos_gui)
    btn_mostrar.pack(side=tk.LEFT, padx=5)
    btn_salvar = tk.Button(btn_consulta_frame, text="Salvar", command=salvar_registos_gui)
    btn_salvar.pack(side=tk.LEFT, padx=5)
    btn_carregar = tk.Button(btn_consulta_frame, text="Carregar", command=carregar_registos_gui)
    btn_carregar.pack(side=tk.LEFT, padx=5)
    btn_limpar = tk.Button(btn_consulta_frame, text="Limpar", command=limpar_registos_gui, bg="red", fg="white")
    btn_limpar.pack(side=tk.LEFT, padx=5)
    btn_grafico = tk.Button(btn_consulta_frame, text="Mostrar Gráfico", command=mostrar_grafico_glicemia)
    btn_grafico.pack(side=tk.LEFT, padx=5)
    tk.Button(btn_consulta_frame, text="Voltar ao Menu", command=lambda: mostrar_frame("menu")).pack(side=tk.LEFT, padx=5)
    columns = ('Data', 'Utilizador', 'Tipo', 'Valor', 'Descrição', 'Refeição', 'Classificação')
    tree_registos = ttk.Treeview(consulta_widgets, columns=columns, show='headings')
    tree_registos.heading('Data', text='Data')
    tree_registos.heading('Utilizador', text='Utilizador')
    tree_registos.heading('Tipo', text='Tipo')
    tree_registos.heading('Valor', text='Valor')
    tree_registos.heading('Descrição', text='Descrição')
    tree_registos.heading('Refeição', text='Refeição')
    tree_registos.heading('Classificação', text='Classificação')
    tree_registos.column('Data', width=150)
    tree_registos.column('Utilizador', width=80)
    tree_registos.column('Tipo', width=100)
    tree_registos.column('Valor', width=50)
    tree_registos.column('Descrição', width=150)
    tree_registos.column('Refeição', width=150)
    tree_registos.column('Classificação', width=100)
    tree_registos.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    scrollbar = ttk.Scrollbar(consulta_widgets, orient=tk.VERTICAL, command=tree_registos.yview)
    tree_registos.configure(yscroll=scrollbar.set)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y, before=tree_registos)
    janela.grid_rowconfigure(0, weight=1)
    janela.grid_columnconfigure(0, weight=1)
    atualizar_menus_alimentos()
    mostrar_frame("login")
    janela.mainloop()