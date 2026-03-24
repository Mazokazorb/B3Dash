import json
import os
import yfinance as yf
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, DataTable, Static, Label
from textual.containers import Vertical, Horizontal
from plyer import notification

STORAGE_PATH = os.path.expanduser("~/.b3dash_portfolio.json")

class B3Dash(App):
    CSS = """
    Screen { background: #1a1b26; }
    #header_area { height: 7; border: tall #7aa2f7; margin: 1; padding: 0 1; }
    #main_body { layout: horizontal; height: 1fr; }
    #portfolio_panel { width: 70%; border-right: solid #414868; padding: 1; }
    #info_panel { width: 30%; align: center middle; padding: 2; }
    .total-display { background: #414868; color: #9ece6a; text-align: center; text-style: bold; height: 3; content-align: center middle; margin-top: 1; }
    .price-box { background: #24283b; border: double #7aa2f7; padding: 1; text-align: center; height: auto; }
    DataTable { height: 1fr; border: solid #414868; width: 100%; }
    .editing { border: tall #bb9af7 !important; background: #2f334d; }
    """

    BINDINGS = [
        ("q", "quit", "Sair"),
        ("a", "add_item", "Adicionar"),
        ("r", "refresh", "Atualizar"),
        ("x", "delete_item", "Remover"),
        ("c", "clear_all", "Limpar Tudo")
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="header_area"):
            yield Label("BUSCAR: TICKER, QTD, ALVO | CLIQUE NA QTD/ALVO PARA EDITAR", id="input_label")
            yield Input(placeholder="Ex: PETR4, 100, 45.50", id="cmd_input")
            yield Static("Patrimônio Total: R$ 0.00", id="total_summary", classes="total-display")
        with Horizontal(id="main_body"):
            with Vertical(id="portfolio_panel"):
                yield DataTable(id="main_table")
            with Vertical(id="info_panel"):
                yield Static("Aguardando busca...", id="ticker_details", classes="price-box")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#main_table", DataTable)
        self.col_status = table.add_column("S", width=3)
        self.col_ticker = table.add_column("Ativo")
        self.col_qtd = table.add_column("Quantidade")
        self.col_price = table.add_column("Preço")
        self.col_total = table.add_column("Total (R$)")
        self.col_alvo = table.add_column("Alvo (R$)")
        
        table.cursor_type = "cell"
        self.editing_coord = None
        self.load_data()
        self.set_interval(60, self.action_refresh)

    def parse_num(self, value) -> float:
        try:
            return float(str(value).replace("R$", "").replace(",", ".").strip())
        except:
            return 0.0

    def update_summary(self):
        table = self.query_one("#main_table")
        grand_total = 0.0
        for row_key in table.rows:
            r = table.get_row(row_key)
            qtd = int(self.parse_num(r[2]))
            preco = self.parse_num(r[3])
            linha_total = qtd * preco
            table.update_cell(row_key, self.col_total, f"{linha_total:.2f}")
            grand_total += linha_total
        self.query_one("#total_summary").update(f"Patrimônio Total: R$ {grand_total:.2f}")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        input_widget = self.query_one("#cmd_input")
        label_widget = self.query_one("#input_label")
        
        if self.editing_coord:
            table = self.query_one("#main_table")
            if event.value:
                clean_val = int(self.parse_num(event.value)) if self.editing_coord.column == 2 else self.parse_num(event.value)
                table.update_cell_at(self.editing_coord, str(clean_val))
                self.update_summary()
                self.save_data()
            
            self.editing_coord = None
            input_widget.remove_class("editing")
            input_widget.value = ""
            label_widget.update("BUSCAR: TICKER, QTD, ALVO")
            return

        try:
            raw = event.value.upper().replace(" ", "").split(",")
            ticker = raw[0]
            if not ticker: return
            qtd = int(self.parse_num(raw[1])) if len(raw) > 1 else 0
            alvo = self.parse_num(raw[2]) if len(raw) > 2 else 0.0
            
            yf_ticker = ticker if "-" in ticker else f"{ticker}.SA"
            price = float(yf.Ticker(yf_ticker).fast_info['last_price'])

            self.last_search = ["⚪", ticker, str(qtd), f"{price:.2f}", f"{price*qtd:.2f}", f"{alvo:.2f}"]
            self.query_one("#ticker_details").update(f"[b]{ticker}[/]\nPreço: R$ {price:.2f}\nTotal: R$ {price*qtd:.2f}")
            input_widget.value = ""
        except:
            self.query_one("#ticker_details").update("[red]Erro na busca.")

    def on_data_table_cell_selected(self, event: DataTable.CellSelected) -> None:
        col = event.coordinate.column
        if col in [2, 5]: 
            self.editing_coord = event.coordinate
            input_widget = self.query_one("#cmd_input")
            label_widget = self.query_one("#input_label")
            
            field = "QUANTIDADE" if col == 2 else "ALVO"
            label_widget.update(f"[b][magenta]EDITANDO {field}:[/][/] Digite o novo valor e Enter")
            input_widget.add_class("editing")
            input_widget.value = str(event.value)
            input_widget.focus()

    def action_add_item(self):
        if hasattr(self, 'last_search'):
            self.query_one("#main_table").add_row(*self.last_search)
            self.update_summary()
            self.save_data()
            self.notify("Adicionado!")

    def action_delete_item(self):
        table = self.query_one("#main_table")
        if table.cursor_coordinate:
            row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
            table.remove_row(row_key)
            self.update_summary()
            self.save_data()

    def action_refresh(self):
        table = self.query_one("#main_table")
        rows = {k: table.get_row(k) for k in table.rows}
        if not rows: return
        tickers = [r[1] if "-" in r[1] else f"{r[1]}.SA" for r in rows.values()]
        try:
            prices = yf.download(tickers, period="1d", interval="1m", group_by='ticker', progress=False)
            for k, r in rows.items():
                t_yf = r[1] if "-" in r[1] else f"{r[1]}.SA"
                if len(tickers) == 1:
                    new_p = float(prices['Close'].iloc[-1])
                else:
                    new_p = float(prices[t_yf]['Close'].iloc[-1])
                
                status = "[green]●[/]" if new_p > self.parse_num(r[3]) else ("[red]●[/]" if new_p < self.parse_num(r[3]) else "⚪")
                qtd = int(self.parse_num(r[2]))
                table.update_row(k, status, r[1], str(qtd), f"{new_p:.2f}", f"{new_p*qtd:.2f}", r[5])
            self.update_summary()
            self.save_data()
        except: pass

    def action_clear_all(self):
        self.query_one("#main_table").clear()
        if os.path.exists(STORAGE_PATH): os.remove(STORAGE_PATH)
        self.update_summary()

    def save_data(self):
        table = self.query_one("#main_table")
        data = [list(table.get_row(k)) for k in table.rows]
        with open(STORAGE_PATH, "w") as f:
            json.dump(data, f)

    def load_data(self):
        if os.path.exists(STORAGE_PATH):
            try:
                with open(STORAGE_PATH, "r") as f:
                    for row in json.load(f):
                        self.query_one("#main_table").add_row(*row)
                self.call_after_refresh(self.update_summary)
            except: pass

if __name__ == "__main__":
    B3Dash().run()
