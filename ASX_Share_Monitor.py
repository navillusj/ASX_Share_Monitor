import tkinter as tk
from tkinter import ttk
from tkinter.filedialog import asksaveasfilename
import yfinance as yf
import pandas as pd
import sv_ttk
import os
import threading
import time
import matplotlib.pyplot as plt
import matplotlib.dates as mdates 
from matplotlib.backends.backend_tkagg import (FigureCanvasTkAgg, NavigationToolbar2Tk) 
from concurrent.futures import ThreadPoolExecutor
from matplotlib.dates import DateFormatter, HourLocator, MinuteLocator, MinuteLocator
import datetime
import sys 
from PIL import Image, ImageTk 
import numpy as np 
import pytz 

# --- Configuration and Data Persistence ---
STOCK_FILE = 'my_stocks.txt'
REFRESH_INTERVAL_MS = 30000  # 30 seconds automatic refresh
SPLASH_MIN_DURATION_SECONDS = 7 # Total minimum duration

# Time range mapping: {Display Text: (yfinance period, yfinance interval)}
TIME_RANGES = {
    # Using '1wk' and '1d' for long ranges is intentional to avoid the Locator.MAXTICKS error
    "6 Months": ("6mo", "1wk"),
    "30 Days": ("30d", "1d"),
    "7 Days": ("7d", "1h"),
    "24 Hrs": ("1d", "15m"),
    "6 Hrs": ("1d", "5m"),
    "10 Mins": ("1d", "1m"),
}
DEFAULT_TIME_RANGE = "30 Days"

# Timezone Mapping: Using common Australian time zones
TIMEZONES = ['Australia/Sydney', 'Australia/Brisbane', 'Australia/Perth']
DEFAULT_TIMEZONE = 'Australia/Sydney'
TIMEZONE_FILE = 'timezone.txt'

# --- LOADING STEPS ---
DATA_FETCH_MIN_DURATION = 1.0 # 1 second

LOADING_STEPS = {
    0: "Starting up...",
    20: "Fetching Shares...",
    50: "Fetching Data...", 
    80: "Asking Jordan Belfort for help...",
    100: "Load Complete"
}
# --- END LOADING STEPS ---

def load_stocks():
    """Loads stock tickers from a file, if it exists."""
    if os.path.exists(STOCK_FILE):
        with open(STOCK_FILE, 'r') as f:
            return sorted(list(set(line.strip().upper() for line in f if line.strip())))
    return ['BHP.AX', 'PL8.AX']

def save_stocks(tickers):
    """Saves the current list of stock tickers to a file."""
    unique_tickers = sorted(list(set(t.strip().upper() for t in tickers if t.strip())))
    with open(STOCK_FILE, 'w') as f:
        f.write('\n'.join(unique_tickers))

def load_settings():
    """Loads saved settings or returns defaults."""
    settings = {
        'time_range': DEFAULT_TIME_RANGE,
        'timezone': DEFAULT_TIMEZONE
    }
    if os.path.exists(TIMEZONE_FILE):
        with open(TIMEZONE_FILE, 'r') as f:
            lines = [line.strip().split('=') for line in f if '=' in line]
            for key, value in lines:
                if key == 'time_range' and value in TIME_RANGES:
                    settings['time_range'] = value
                elif key == 'timezone' and value in TIMEZONES:
                    settings['timezone'] = value
    return settings

def save_settings(settings):
    """Saves current settings to file."""
    with open(TIMEZONE_FILE, 'w') as f:
        f.write(f"time_range={settings['time_range']}\n")
        f.write(f"timezone={settings['timezone']}\n")

# --- Custom Matplotlib Toolbar for Naming Convention and Zoom ---
class CustomToolbar(NavigationToolbar2Tk):
    """Custom toolbar for plot saving."""
    def __init__(self, canvas, window, ticker="Monitor"):
        self.ticker = ticker 
        super().__init__(canvas, window)

    def save_figure(self, *args):
        now = datetime.datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        
        if self.ticker != "Monitor":
            base_filename = f"{self.ticker}_{timestamp}.png"
        else:
            base_filename = f"MainMonitor_{timestamp}.png"
            
        filetypes = [
            ('PNG', '*.png'),
            ('JPEG', '*.jpg'),
            ('PDF', '*.pdf'),
            ('All files', '*.*')
        ]
        
        path = asksaveasfilename(
            defaultextension=".png",
            filetypes=filetypes,
            initialfile=base_filename,
            title="Save Plot Image"
        )

        if path:
            self.canvas.figure.savefig(path)

# --- Settings Popup Window (Omitted for brevity, unchanged) ---

class SettingsPopup(tk.Toplevel):
    def __init__(self, master, current_settings, save_callback):
        tk.Toplevel.__init__(self, master)
        self.title("Settings")
        self.geometry("300x200")
        self.transient(master)  
        self.grab_set()         
        self.master = master
        self.current_settings = current_settings
        self.save_callback = save_callback
        
        frame = ttk.Frame(self, padding="10")
        frame.pack(fill='both', expand=True)

        # Default Time Range
        ttk.Label(frame, text="Default Chart Range:").grid(row=0, column=0, padx=5, pady=5, sticky='w')
        self.range_var = tk.StringVar(self, value=self.current_settings['time_range'])
        self.range_combo = ttk.Combobox(
            frame,
            values=list(TIME_RANGES.keys()),
            width=15,
            state="readonly",
            textvariable=self.range_var
        )
        self.range_combo.grid(row=0, column=1, padx=5, pady=5, sticky='ew')

        # Timezone Selection
        ttk.Label(frame, text="Timezone:").grid(row=1, column=0, padx=5, pady=5, sticky='w')
        self.timezone_var = tk.StringVar(self, value=self.current_settings['timezone'])
        self.timezone_combo = ttk.Combobox(
            frame,
            values=TIMEZONES,
            width=15,
            state="readonly",
            textvariable=self.timezone_var
        )
        self.timezone_combo.grid(row=1, column=1, padx=5, pady=5, sticky='ew')

        # Save Button
        save_button = ttk.Button(frame, text="Save and Refresh", command=self.on_save)
        save_button.grid(row=2, column=0, columnspan=2, pady=20)

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.master.wait_window(self)

    def on_save(self):
        new_settings = {
            'time_range': self.range_var.get(),
            'timezone': self.timezone_var.get()
        }
        self.save_callback(new_settings)
        self.on_close()

    def on_close(self):
        self.destroy()
        self.master.grab_release()


# --- Splash Screen Class (Omitted for brevity, unchanged) ---

class SplashScreen(tk.Toplevel):
    def __init__(self, master):
        tk.Toplevel.__init__(self, master)
        self.overrideredirect(True) 
        self.title("Loading...")
        
        self.config(bg='#1e1e1e') 
        
        if getattr(sys, 'frozen', False): 
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.abspath(__file__)) if os.path.dirname(os.path.abspath(__file__)) else '.'
        
        logo_path = os.path.join(base_path, 'logo.png')

        try:
            self.original_image = Image.open(logo_path) 
            resized_image = self.original_image.resize((150, 150), Image.LANCZOS)
            self.tk_image = ImageTk.PhotoImage(resized_image)
            
            logo_label = ttk.Label(self, image=self.tk_image, background='#1e1e1e')
            logo_label.pack(padx=20, pady=20)
            
        except FileNotFoundError:
            logo_label = ttk.Label(self, text="ASX Share Monitor (Logo Missing)", font=('Helvetica', 20, 'bold'), background='#1e1e1e', foreground='white')
            logo_label.pack(padx=20, pady=20)
            
        self.status_text = tk.StringVar(self, value=LOADING_STEPS[0])
        self.status_label = ttk.Label(self, textvariable=self.status_text, font=('Helvetica', 10), background='#1e1e1e', foreground='gray')
        self.status_label.pack(pady=(0, 5))

        self.progress_bar = ttk.Progressbar(self, orient='horizontal', length=200, mode='determinate')
        self.progress_bar.pack(pady=(0, 15), padx=20)
        self.progress_bar['value'] = 0

        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        self.geometry(f'+{x}+{y}')
        
        master.withdraw()

    def update_status(self, step_value, message):
        self.status_text.set(message)
        self.progress_bar['value'] = step_value
        self.update() 

# --- Main Application Class ---

class TabbedStockMonitor(tk.Tk):
    def __init__(self):
        super().__init__()
        
        # --- NEW: Set Window Icon (Requires 'logo.ico' to be bundled) ---
        try:
            if getattr(sys, 'frozen', False):
                icon_path = os.path.join(sys._MEIPASS, 'logo.ico')
            else:
                icon_path = 'logo.ico' 

            if os.path.exists(icon_path):
                 self.iconbitmap(icon_path)
            else:
                 print(f"Icon file not found at: {icon_path}. Using default.")
        except Exception as e:
            print(f"Error setting icon: {e}")
        # --- END NEW: Set Window Icon ---
        
        self.splash = SplashScreen(self)
        self.start_time = time.time()
        
        self.settings = load_settings() 
        
        self.title("ASX Share Monitor")
        self.geometry("800x650") 
        sv_ttk.set_theme("dark")
        
        # --- DEFINE ALL ATTRIBUTES FIRST ---
        self.tickers = load_stocks()
        self.tab_widgets = {}
        self.is_running = True
        self.all_stock_data = {} 
        self.executor = ThreadPoolExecutor(max_workers=5)
        self.data_fetched_event = threading.Event()
        self.current_load_step = 0 
        self.annot = None 
        self.line_visibility = {} 
        self._redraw_job = None
        self.sort_column = 'ticker' 
        self.sort_reverse = False    
        # ----------------------------------------------------

        self.create_widgets()
        self.pack_widgets()
        self.create_main_monitor_tab() 
        self.setup_individual_tabs() 
        
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        
        self.ticker_entry.bind('<Return>', lambda event: self.add_stock())
        
        self.bind('<Configure>', self._on_window_configure)
        
        # --- START INITIAL LOAD ---
        print(f"[{time.strftime('%H:%M:%S')}] STARTUP: Starting initial load sequence.")
        self.after(0, lambda: self.splash.update_status(20, LOADING_STEPS[20]))
        threading.Thread(target=self.initial_load_and_data_fetch, daemon=True).start()
        # --- END INITIAL LOAD ---

    # --- Configure Event Handler ---
    def _on_window_configure(self, event):
        """Handles resizing of the main window."""
        if self.state() == 'normal' and (event.widget == self or event.widget == self.notebook):
            print(f"[{time.strftime('%H:%M:%S')}] EVENT: Window configured/resized. Scheduling redraw.")
            if self._redraw_job:
                self.after_cancel(self._redraw_job)
            
            self._redraw_job = self.after(100, self._perform_redraw)

    def _perform_redraw(self):
        """Redraws the current tab content to re-bind tooltips."""
        selected_tab_text = self.notebook.tab(self.notebook.select(), "text")
        print(f"[{time.strftime('%H:%M:%S')}] REDRAW: Executing redraw for tab: {selected_tab_text}")
        
        if selected_tab_text == "Main Monitor":
            self.update_main_monitor()
        elif selected_tab_text in self.tickers:
            self.fetch_data()
        self._redraw_job = None
    # --- END Configure Event Handler ---

    # --- Initialization and Core Loop ---

    def initial_load_and_data_fetch(self):
        # 1. Start timer for data fetch phase
        fetch_start_time = time.time()
        
        # 2. Start the fetch process (updates to 50%)
        print(f"[{time.strftime('%H:%M:%S')}] LOADING: Initiating data fetch via executor.")
        self.after(0, lambda: self.splash.update_status(50, LOADING_STEPS[50]))
        self._initial_fetch_data() 
        
        # 3. Wait for data fetch completion (blocks thread until data is processed on main thread)
        self.data_fetched_event.wait() 
        print(f"[{time.strftime('%H:%M:%S')}] LOADING: Data processing complete on main thread.")
        
        # 4. Enforce minimum 1-second fetch time (50% to 80%)
        fetch_elapsed = time.time() - fetch_start_time
        fetch_time_to_wait = DATA_FETCH_MIN_DURATION - fetch_elapsed
        if fetch_time_to_wait > 0:
            print(f"[{time.strftime('%H:%M:%S')}] LOADING: Enforcing {fetch_time_to_wait:.2f}s minimum fetch time.")
            time.sleep(fetch_time_to_wait)
        
        # 5. Update status (moves to 80%)
        self.after(0, lambda: self.splash.update_status(80, LOADING_STEPS[80]))

        # 6. Enforce total minimum 7-second duration
        total_elapsed = time.time() - self.start_time
        total_time_to_wait = SPLASH_MIN_DURATION_SECONDS - total_elapsed
        if total_time_to_wait > 0:
            print(f"[{time.strftime('%H:%M:%S')}] LOADING: Enforcing {total_time_to_wait:.2f}s total minimum duration.")
            time.sleep(total_time_to_wait)
        
        # 7. Final status update and check on main thread
        self.after(0, lambda: self.splash.update_status(100, LOADING_STEPS[100]))
        self.after(100, self._check_load_complete)


    def _check_load_complete(self):
        
        self.update_idletasks() 
        
        self.time_range_combo.set(self.settings['time_range']) 
        
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_change)
        self.deiconify() 
        self.splash.destroy()
        self.after(REFRESH_INTERVAL_MS, self.start_refresh) 


    def _initial_fetch_data(self):
        if not self.tickers:
            self.after(0, lambda: self.status_label.config(text="Status: No stocks to monitor.", foreground='white'))
            self.after(0, self.update_main_monitor)
            self.data_fetched_event.set() 
            return
        
        graph_period, graph_interval = TIME_RANGES.get(self.settings['time_range'], TIME_RANGES[DEFAULT_TIME_RANGE])
        hourly_hist_period = "1d"
        hourly_hist_interval = "1m"
        print(f"[{time.strftime('%H:%M:%S')}] FETCH: Initial fetch parameters (Period: {graph_period}, Interval: {graph_interval}).")

        future = self.executor.submit(self._run_fetch, graph_period, graph_interval, hourly_hist_period, hourly_hist_interval)
        
        future.add_done_callback(lambda f: self.after(0, self._handle_initial_fetch_result, f))
        
    def _handle_initial_fetch_result(self, future):
        try:
            new_data = future.result()
            self.all_stock_data.update(new_data)
            print(f"[{time.strftime('%H:%M:%S')}] PROCESS: Data received. Updating UI tabs.")
            self.update_tabs(new_data)
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] ERROR: Critical error during data process: {e}")
            self.after(0, lambda: self.status_label.config(text=f"Status: Critical error during data process.", foreground='red'))
        finally:
            self.data_fetched_event.set() 
            
    def start_refresh(self):
        """Starts the periodic data refresh loop (RECURRING CALLS ONLY)."""
        if self.is_running:
            self.fetch_data()
            self.after(REFRESH_INTERVAL_MS, self.start_refresh)
            
    # --- Widget Setup (Omitted for brevity, unchanged) ---
    def create_widgets(self):
        self.control_frame = ttk.Frame(self)
        self.ticker_entry = ttk.Entry(self.control_frame, width=15)
        self.add_button = ttk.Button(self.control_frame, text="Add ASX Stock", command=self.add_stock)
        self.remove_button = ttk.Button(self.control_frame, text="Remove Tab", command=self.remove_stock)
        self.refresh_button = ttk.Button(self.control_frame, text="Manual Refresh", command=self.fetch_data)
        
        self.range_label = ttk.Label(self.control_frame, text="Chart Range:")
        self.time_range_combo = ttk.Combobox(
            self.control_frame,
            values=list(TIME_RANGES.keys()),
            width=10,
            state="readonly" 
        )
        self.time_range_combo.bind("<<ComboboxSelected>>", lambda e: self.fetch_data())
        
        self.settings_button = ttk.Button(self.control_frame, text="Settings", command=self.open_settings)
        
        self.notebook = ttk.Notebook(self)
        self.status_label = ttk.Label(self, text=f"Status: Ready | Auto-Refresh: {REFRESH_INTERVAL_MS/1000}s", anchor='w', foreground='white')

    def pack_widgets(self):
        self.control_frame.pack(pady=10, padx=10, fill='x')
        
        self.ticker_entry.pack(side='left', padx=(0, 5), fill='x', expand=True)
        self.add_button.pack(side='left', padx=(0, 5))
        self.remove_button.pack(side='left', padx=(0, 10))
        
        self.refresh_button.pack(side='right')
        self.settings_button.pack(side='right', padx=(10, 5)) 
        self.time_range_combo.pack(side='right', padx=(10, 0))
        self.range_label.pack(side='right', padx=(0, 5))
        
        self.notebook.pack(pady=5, padx=10, fill='both', expand=True)
        self.status_label.pack(side='bottom', fill='x', padx=10, pady=(0, 5))

    # --- Settings Handlers ---
    def open_settings(self):
        SettingsPopup(self, self.settings, self.apply_settings)

    def apply_settings(self, new_settings):
        changed_range = new_settings['time_range'] != self.settings['time_range']
        changed_timezone = new_settings['timezone'] != self.settings['timezone']
        
        self.settings = new_settings
        save_settings(self.settings)
        
        self.time_range_combo.set(self.settings['time_range'])
        
        if changed_range or changed_timezone:
            print(f"[{time.strftime('%H:%M:%S')}] SETTINGS: Applied new settings. Triggering data fetch (range changed: {changed_range}, TZ changed: {changed_timezone}).")
            self.fetch_data()

    # --- Treeview Sorting Function ---
    def _treeview_sort_column(self, tree, col, reverse):
        """Sort the Treeview column data."""
        
        data_list = [(tree.set(item, col), item) for item in tree.get_children('')]
        
        # --- Custom Sorting Key Function ---
        def sort_key(item):
            value = item[0]
            
            # Numeric columns
            if col in ['price', 'open', 'daily_change_abs', 'hourly_change_abs']:
                try:
                    # Clean up currency/sign/arrows to get a float
                    return float(value.replace('$', '').replace('+', '').replace(' \u2191', '').replace(' \u2193', '').strip())
                except ValueError:
                    return 0.0 # Handle 'N/A' or 'ERROR' gracefully
            elif col in ['daily_change_pct', 'hourly_change_pct']:
                try:
                    # Clean up percentage/sign/arrows to get a float
                    return float(value.replace('%', '').replace('+', '').replace(' \u2191', '').replace(' \u2193', '').strip())
                except ValueError:
                    return 0.0 # Handle 'N/A' or 'ERROR' gracefully
            else:
                # Default to string sort (ticker, visible)
                return value.lower()

        # Sort the list using the custom key
        data_list.sort(key=sort_key, reverse=reverse)

        # Rearrange items in sorted order
        for index, (val, item) in enumerate(data_list):
            tree.move(item, '', index)

        # Update sort state (used by the next click/update)
        self.sort_reverse = not reverse
        self.sort_column = col

        # Update heading appearance (rebinds to the opposite reverse state)
        tree.heading(col, command=lambda c=col: self._treeview_sort_column(tree, c, self.sort_reverse))

    def on_main_tree_header_click(self, event):
        """
        Handles header click, updates sort state, and forces update_main_monitor 
        to redraw using the new sort state.
        """
        region = self.main_tree.identify_region(event.x, event.y)
        if region != "heading":
            return
        
        column_id = self.main_tree.identify_column(event.x)
        
        # Mapping column IDs to internal names
        col_map = {'#1': 'visible', '#2': 'ticker', '#3': 'price', '#4': 'open', 
                   '#5': 'daily_change_pct', '#6': 'daily_change_abs', 
                   '#7': 'hourly_change_pct', '#8': 'hourly_change_abs'}
        
        col_name = col_map.get(column_id)

        if col_name:
            # FIX: Only update the reverse flag if the same column is clicked
            reverse_flag = not self.sort_reverse if col_name == self.sort_column else False
            
            self.sort_column = col_name
            self.sort_reverse = reverse_flag
            
            # Trigger full update to re-sort the underlying list
            self.update_main_monitor() 


    # --- Plotting and Data Logic ---

    def create_main_monitor_tab(self):
        main_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(main_frame, text="Main Monitor")
        
        graph_container = ttk.Frame(main_frame)
        graph_container.pack(fill='both', expand=True, pady=(0, 5))

        columns = ('visible', 'ticker', 'price', 'open', 'daily_change_pct', 'daily_change_abs', 'hourly_change_pct', 'hourly_change_abs')
        self.main_tree = ttk.Treeview(main_frame, columns=columns, show='headings')
        
        # Define headings and bind initial click handler for sorting
        for col in columns:
            self.main_tree.heading(col, text=col.replace('_', ' ').title(), anchor='center' if col == 'visible' else 'e', 
                                   command=lambda c=col: self._treeview_sort_column(self.main_tree, c, False))
        
        # Reset heading text for display
        self.main_tree.heading('visible', text='CHART', anchor='center')
        self.main_tree.heading('ticker', text='SHARE', anchor='w')
        self.main_tree.heading('price', text='PRICE', anchor='e')
        self.main_tree.heading('open', text='OPEN', anchor='e')
        self.main_tree.heading('daily_change_pct', text='DAILY %', anchor='e')
        self.main_tree.heading('daily_change_abs', text='DAILY $', anchor='e')
        self.main_tree.heading('hourly_change_pct', text='HOURLY %', anchor='e')
        self.main_tree.heading('hourly_change_abs', text='HOURLY $', anchor='e')

        self.main_tree.column('visible', width=40, anchor='center', stretch=tk.NO)
        self.main_tree.column('ticker', width=70, anchor='w')
        self.main_tree.column('price', width=80, anchor='e')
        self.main_tree.column('open', width=80, anchor='e')
        self.main_tree.column('daily_change_pct', width=70, anchor='e')
        self.main_tree.column('daily_change_abs', width=70, anchor='e')
        self.main_tree.column('hourly_change_pct', width=70, anchor='e')
        self.main_tree.column('hourly_change_abs', width=70, anchor='e')
        
        # Bind toggle visibility AND header click sorter
        self.main_tree.bind('<ButtonRelease-1>', self.toggle_chart_visibility)
        self.main_tree.bind('<Button-1>', self.on_main_tree_header_click) 
        
        self.main_tree.pack(side='top', fill='both', expand=False, pady=(0, 10))
        
        bg_color = self._get_safe_bg_color()
        fig, ax = plt.subplots(figsize=(7, 3.5), facecolor=bg_color)
        ax.set_facecolor(bg_color)
        
        canvas = FigureCanvasTkAgg(fig, master=graph_container)
        canvas_widget = canvas.get_tk_widget()
        canvas_widget.pack(side=tk.TOP, fill='both', expand=True)
        
        toolbar = CustomToolbar(canvas, graph_container, ticker="Monitor") 
        toolbar.update()
        toolbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.tab_widgets['Main Monitor'] = {
            'tree': self.main_tree,
            'fig': fig,
            'ax': ax,
            'canvas': canvas
        } 
        
    def toggle_chart_visibility(self, event):
        """Handles click events on the Treeview to toggle chart visibility."""
        item_id = self.main_tree.identify_row(event.y)
        if not item_id:
            return

        col_id = self.main_tree.identify_column(event.x)
        if col_id != '#1': # Check only clicks on the first column ('visible')
            return

        ticker = item_id 

        current_state = self.line_visibility.get(ticker, True)
        self.line_visibility[ticker] = not current_state
        
        print(f"[{time.strftime('%H:%M:%S')}] CHART: Toggled visibility for {ticker} to {self.line_visibility[ticker]}")
        self.update_main_monitor()
        
    def update_main_monitor(self):
        self.main_tree.delete(*self.main_tree.get_children())
        self.main_tree.tag_configure('gain', foreground='green')
        self.main_tree.tag_configure('loss', foreground='red')
        self.main_tree.tag_configure('error', foreground='yellow')
        
        for ticker in self.all_stock_data.keys():
            if ticker not in self.line_visibility:
                self.line_visibility[ticker] = True # Default to visible
        
        sorted_tickers = sorted(self.all_stock_data.keys())
        
        for ticker in sorted_tickers:
            data = self.all_stock_data.get(ticker, {})
            
            is_visible = self.line_visibility.get(ticker, True)
            visible_symbol = "\u2714" if is_visible else "\u2718" # Checkmark / X

            if data.get("error"):
                values = (visible_symbol, ticker, "N/A", "N/A", "N/A", "N/A", "N/A", "N/A")
                tag = 'error'
            else:
                change_abs = data.get('change_abs', 0)
                hourly_change_abs = data.get('hourly_change_abs', 0)
                
                tag = 'gain' if change_abs >= 0 else 'loss'
                
                daily_pct_display, daily_abs_display = self._format_change_data(data.get('daily_change_pct', 0), change_abs)
                hourly_pct_display, hourly_abs_display = self._format_change_data(data.get('hourly_change_pct', 0), hourly_change_abs)

                values = (
                    visible_symbol,
                    ticker,
                    f"${data.get('price', 0):,.2f}",
                    f"${data.get('open_price', 0):,.2f}",
                    daily_pct_display,
                    daily_abs_display,
                    hourly_pct_display,
                    hourly_abs_display
                )
            self.main_tree.insert('', tk.END, values=values, tags=(tag,), iid=ticker)

        # Apply current sort order immediately after populating
        self._treeview_sort_column(self.main_tree, self.sort_column, self.sort_reverse)


        # 2. Update Graph
        main_widgets = self.tab_widgets.get('Main Monitor')
        if main_widgets:
            self._plot_main_monitor(main_widgets['ax'], main_widgets['fig'], main_widgets['canvas'])

    def _format_change_data(self, pct_value, abs_value):
        """Formats change data with arrows and signs."""
        arrow = " \u2191" if pct_value >= 0 else " \u2193" # Up/Down arrow unicode
        
        # Format percentage: +/- X.XX% (with arrow)
        pct_display = f"{pct_value:+.2f}%{arrow}"
        
        # Format absolute: +/- $X.XX (with arrow)
        abs_display = f"${abs_value:+.2f}{arrow}"

        return pct_display, abs_display

    def on_tab_change(self, event):
        selected_tab_text = self.notebook.tab(self.notebook.select(), "text")
        print(f"[{time.strftime('%H:%M:%S')}] TAB: Switched to tab: {selected_tab_text}")
        
        if selected_tab_text != "Main Monitor":
            self.fetch_data()
        else:
            self.update_main_monitor()
            
    def setup_individual_tabs(self):
        for ticker in self.tickers:
            self.create_new_tab(ticker)
        
    def create_new_tab(self, ticker):
        if ticker in self.tab_widgets:
            return

        tab_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab_frame, text=ticker)
        
        info_frame = ttk.Frame(tab_frame)
        info_frame.pack(fill='x', pady=5)
        
        price_label = ttk.Label(info_frame, text="Current Price: N/A", font=('Helvetica', 16, 'bold'), foreground='white')
        price_label.pack(pady=5, padx=10, anchor='w')
        
        # UPDATED LABELS FOR SEPARATE % and $ DISPLAY
        daily_change_pct_label = ttk.Label(info_frame, text="Daily Change %: N/A (0.00%)", font=('Helvetica', 14), foreground='white')
        daily_change_pct_label.pack(pady=2, padx=10, anchor='w')
        daily_change_abs_label = ttk.Label(info_frame, text="Daily Change $: N/A ($0.00)", font=('Helvetica', 14), foreground='white')
        daily_change_abs_label.pack(pady=2, padx=10, anchor='w')
        
        hourly_change_pct_label = ttk.Label(info_frame, text="Hourly Change %: N/A (0.00%)", font=('Helvetica', 14), foreground='white')
        hourly_change_pct_label.pack(pady=2, padx=10, anchor='w')
        hourly_change_abs_label = ttk.Label(info_frame, text="Hourly Change $: N/A ($0.00)", font=('Helvetica', 14), foreground='white')
        hourly_change_abs_label.pack(pady=2, padx=10, anchor='w')
        # END UPDATED LABELS

        open_label = ttk.Label(info_frame, text="Open Price: N/A", font=('Helvetica', 12), foreground='gray')
        open_label.pack(pady=5, padx=10, anchor='e')
        
        graph_container = ttk.Frame(tab_frame)
        graph_container.pack(fill='both', expand=True)

        bg_color = self._get_safe_bg_color()
            
        fig, ax = plt.subplots(figsize=(5, 3), facecolor=bg_color)
        ax.set_facecolor(bg_color)
        
        canvas = FigureCanvasTkAgg(fig, master=graph_container)
        canvas_widget = canvas.get_tk_widget()
        canvas_widget.pack(side=tk.TOP, fill='both', expand=True)
        
        toolbar = CustomToolbar(canvas, graph_container, ticker=ticker) 
        toolbar.update()
        toolbar.pack(side=tk.BOTTOM, fill=tk.X)

        self.tab_widgets[ticker] = {
            'frame': tab_frame,
            'price': price_label,
            'daily_change_pct': daily_change_pct_label,
            'daily_change_abs': daily_change_abs_label,
            'hourly_change_pct': hourly_change_pct_label,
            'hourly_change_abs': hourly_change_abs_label,
            'open': open_label,
            'fig': fig,
            'ax': ax,
            'canvas': canvas
        }
        
    def destroy_tab(self, ticker):
        if ticker in self.tab_widgets:
            frame_to_destroy = self.tab_widgets[ticker]['frame']
            self.notebook.forget(frame_to_destroy)
            del self.tab_widgets[ticker]

    def add_stock(self):
        ticker = self.ticker_entry.get().strip().upper()
        
        if ticker and '.' not in ticker:
            ticker += '.AX'
            
        ticker = ticker.strip('.')
            
        if ticker and ticker not in self.tickers:
            self.tickers.append(ticker)
            self.create_new_tab(ticker) 
            self.ticker_entry.delete(0, tk.END)
            save_stocks(self.tickers)
            print(f"[{time.strftime('%H:%M:%S')}] STOCK: Added new ticker: {ticker}. Triggering fetch.")
            self.fetch_data()
        
        elif ticker in self.tickers:
            self.status_label.config(text=f"Status: {ticker} is already being monitored.", foreground='orange')
        elif not ticker:
            self.status_label.config(text="Status: Please enter a ticker symbol.", foreground='red')

    def remove_stock(self):
        try:
            selected_tab_id = self.notebook.select()
            ticker_to_remove = self.notebook.tab(selected_tab_id, "text")
            
            if ticker_to_remove == "Main Monitor":
                 self.status_label.config(text="Status: Cannot remove the Main Monitor tab.", foreground='red')
                 return
            
            if ticker_to_remove in self.tickers:
                self.tickers.remove(ticker_to_remove)
                self.destroy_tab(ticker_to_remove)
                
                # Remove from visibility tracker
                if ticker_to_remove in self.line_visibility:
                    del self.line_visibility[ticker_to_remove]
                
                save_stocks(self.tickers)
                self.status_label.config(text=f"Status: Removed {ticker_to_remove} successfully.", foreground='yellow')
                print(f"[{time.strftime('%H:%M:%S')}] STOCK: Removed ticker: {ticker_to_remove}. Redrawing.")
                self.update_main_monitor() # Redraw chart after removal

        except tk.TclError:
            self.status_label.config(text="Status: No tab selected or no tabs to remove.", foreground='red')

    def fetch_data(self):
        if not self.tickers:
            self.status_label.config(text="Status: No stocks to monitor.", foreground='white')
            self.update_main_monitor()
            return
        
        self.status_label.config(text=f"Status: Fetching data...", foreground='yellow')
        self.refresh_button.config(state=tk.DISABLED)
        
        selected_range = self.time_range_combo.get() 
        graph_period, graph_interval = TIME_RANGES.get(selected_range, TIME_RANGES[DEFAULT_TIME_RANGE])

        hourly_hist_period = "1d"
        hourly_hist_interval = "1m"

        future = self.executor.submit(self._run_fetch, graph_period, graph_interval, hourly_hist_period, hourly_hist_interval)
        future.add_done_callback(lambda f: self.after(0, self._handle_fetch_result, f))

    def _handle_fetch_result(self, future):
        try:
            new_data = future.result()
            self.all_stock_data.update(new_data)
            print(f"[{time.strftime('%H:%M:%S')}] PROCESS: Data refreshed successfully. Updating UI.")
            self.update_tabs(new_data)
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] ERROR: Failed to process refreshed data: {e}")
            self.status_label.config(text=f"Status: Critical error during data process.", foreground='red')
            self.refresh_button.config(state=tk.NORMAL)

    def _run_fetch(self, graph_period, graph_interval, hourly_hist_period, hourly_hist_interval):
        new_data = {}
        for ticker in self.tickers:
            try:
                print(f"[{time.strftime('%H:%M:%S')}] FETCH: Starting fetch for {ticker}...")
                ticker_obj = yf.Ticker(ticker)
                info = ticker_obj.info
                
                price = info.get('regularMarketPrice')
                open_price = info.get('regularMarketOpen')
                
                hist = ticker_obj.history(period=graph_period, interval=graph_interval)['Close']
                hourly_hist = ticker_obj.history(period=hourly_hist_period, interval=hourly_hist_interval)['Close']
                
                if price is None or open_price is None:
                    if not hist.empty:
                        price = hist.iloc[-1]
                        open_price = hist.iloc[0] 
                    else:
                        raise ValueError(f"No usable price data found for {ticker}.")

                daily_change_abs = price - open_price
                daily_change_pct = (daily_change_abs / open_price) * 100
                
                hourly_change_pct = 0.0
                hourly_change_abs = 0.0
                if len(hourly_hist) >= 60 and price > 0:
                    price_one_hour_ago = hourly_hist.iloc[-60]
                    hourly_change_abs = price - price_one_hour_ago
                    hourly_change_pct = (hourly_change_abs / price_one_hour_ago) * 100

                change_color = "green" if daily_change_abs >= 0 else "red"
                
                new_data[ticker] = {
                    "price": price,
                    "open_price": open_price,
                    "change_abs": daily_change_abs,
                    "daily_change_pct": daily_change_pct,
                    "hourly_change_abs": hourly_change_abs, 
                    "hourly_change_pct": hourly_change_pct,
                    "color": change_color,
                    "history": hist,
                    "range_text": self.time_range_combo.get()
                }
                print(f"[{time.strftime('%H:%M:%S')}] FETCH: Completed fetch for {ticker}.")
            
            except Exception as e:
                print(f"[{time.strftime('%H:%M:%S')}] ERROR: Error fetching data for {ticker}: {e}")
                new_data[ticker] = {"price": None, "error": True}
        
        return new_data
        
    def update_tabs(self, new_data):
        gain_color = 'green'
        loss_color = 'red'
        error_color = 'red'
        
        for ticker, data in new_data.items():
            if ticker in self.tab_widgets:
                widgets = self.tab_widgets[ticker]
                
                if data.get("error"):
                    widgets['price'].config(text=f"Current Price: N/A", foreground=error_color)
                    widgets['daily_change_pct'].config(text=f"Daily Change %: DATA ERROR", foreground=error_color)
                    widgets['daily_change_abs'].config(text=f"Daily Change $: N/A", foreground='gray')
                    widgets['hourly_change_pct'].config(text=f"Hourly Change %: N/A", foreground='gray')
                    widgets['hourly_change_abs'].config(text=f"Hourly Change $: N/A", foreground='gray')
                    self._clear_plot(widgets['ax'], widgets['canvas'], "DATA ERROR")
                    continue
                
                daily_pct = data['daily_change_pct']
                daily_abs = data['change_abs']
                hourly_pct = data['hourly_change_pct']
                hourly_abs = data['hourly_change_abs']
                
                display_color = 'green' if daily_pct >= 0 else 'red'
                hourly_color = 'green' if hourly_pct >= 0 else 'red'
                
                widgets['price'].config(text=f"Current Price: ${data['price']:,.2f}", foreground=display_color)
                
                # Update individual labels
                widgets['daily_change_pct'].config(
                    text=f"Daily Change %: {self._format_change_data(daily_pct, daily_abs)[0]}", 
                    foreground=display_color
                )
                widgets['daily_change_abs'].config(
                    text=f"Daily Change $: {self._format_change_data(daily_pct, daily_abs)[1]}", 
                    foreground=display_color
                )
                widgets['hourly_change_pct'].config(
                    text=f"Hourly Change %: {self._format_change_data(hourly_pct, hourly_abs)[0]}", 
                    foreground=hourly_color
                )
                widgets['hourly_change_abs'].config(
                    text=f"Hourly Change $: {self._format_change_data(hourly_pct, hourly_abs)[1]}", 
                    foreground=hourly_color
                )
                
                widgets['open'].config(text=f"Open Price: ${data['open_price']:,.2f}", foreground='gray')
                
                self._plot_history(widgets['ax'], widgets['fig'], widgets['canvas'], data['history'], display_color, data['range_text'], ticker)
        
        self.update_main_monitor()
                
        self.status_label.config(text=f"Status: Data loaded successfully | Last update: {time.strftime('%H:%M:%S')}", foreground='white')
        self.refresh_button.config(state=tk.NORMAL)

    def _get_safe_bg_color(self):
        try:
            bg_color = self.cget('bg') 
            if not bg_color.startswith('#') or len(bg_color) not in [4, 5, 7, 9]:
                raise ValueError
        except Exception:
            bg_color = '#1e1e1e' 
        return bg_color

    def _clear_plot(self, ax, canvas, error_text="NO HISTORICAL DATA"):
        ax.clear()
        bg_color = self._get_safe_bg_color() 
        ax.set_facecolor(bg_color)
        ax.text(0.5, 0.5, error_text, transform=ax.transAxes, color='red', 
                fontsize=12, ha='center', va='center')
        ax.axis('off')
        canvas.draw_idle()

    # --- HOVER ANNOTATION SETUP ---
    def _setup_hover_annotation(self, ax, canvas, history_data, ticker=None):
        """Sets up the interactive crosshair and floating annotation (tooltip)."""
        
        if ticker:
            lines = ax.get_lines()
            if not lines: return
            data_lines = {ticker: lines[0]}
            base_data = self.all_stock_data.get(ticker, {})
        else:
            data_lines = {line.get_label(): line for line in ax.get_lines() if line.get_label()}
            if not data_lines: return
            base_data = None 

        # --- CLEANUP AND RE-INITIALIZE ANNOTATION OBJECTS ---
        if hasattr(ax, 'motion_cid'):
            canvas.mpl_disconnect(ax.motion_cid)
        if hasattr(ax, 'leave_cid'):
            canvas.mpl_disconnect(ax.leave_cid)
            
        if hasattr(ax, 'annot') and ax.annot in ax.texts:
            ax.annot.remove()
        if hasattr(ax, 'vline') and ax.vline in ax.lines:
            ax.vline.remove()
        if hasattr(ax, 'cursor_marker') and ax.cursor_marker in ax.lines:
            ax.cursor_marker.remove()
        
        # --- RE-INITIALIZE ---
        bg_color = self._get_safe_bg_color()
        text_color = '#FFFFFF'
        
        ax.cursor_marker = ax.plot([], [], marker='o', markersize=6, color='yellow', linestyle='None', zorder=10)[0]
        ax.annot = ax.annotate("", xy=(0, 0), xytext=(5, 5), textcoords="offset points",
                            bbox=dict(boxstyle="round,pad=0.5", fc=bg_color, alpha=0.9, ec='yellow'),
                            color=text_color,
                            zorder=10) 
        ax.annot.set_visible(False)
        ax.vline = ax.axvline(x=0, color='yellow', linestyle='--', linewidth=0.5, alpha=0.7, zorder=10)
        ax.vline.set_visible(False)
        # --- END RE-INITIALIZE ---


        # Function to handle mouse movement
        def on_motion(event):
            # Check for valid event coordinates and axis
            if event.inaxes != ax or event.xdata is None or event.ydata is None:
                ax.annot.set_visible(False)
                ax.cursor_marker.set_visible(False)
                ax.vline.set_visible(False)
                canvas.draw_idle()
                return

            closest_line_ticker = None
            min_distance = float('inf')
            best_x_data_num = None
            best_y_data = None
            
            for t, line in data_lines.items():
                x_data_dt = line.get_xdata()
                y_data = line.get_ydata()
                
                if not len(x_data_dt): continue
                
                x_data_num = mdates.date2num(x_data_dt)
                idx = (np.abs(x_data_num - event.xdata)).argmin()
                
                point = ax.transData.transform((x_data_num[idx], y_data[idx]))
                mouse = np.array([event.x, event.y])
                
                distance = abs(point[0] - mouse[0])
                
                if distance < min_distance and distance < 20: 
                    min_distance = distance
                    closest_line_ticker = t
                    best_x_data_num = x_data_num[idx]
                    best_y_data = y_data[idx]
            
            if closest_line_ticker:
                if ticker:
                    current_data = base_data
                else:
                    current_data = self.all_stock_data.get(closest_line_ticker, {})
                
                tz = pytz.timezone(self.settings.get('timezone', DEFAULT_TIMEZONE))
                
                # FIX: Use mdates.num2date with the target timezone (tz)
                dt_local = mdates.num2date(best_x_data_num, tz=tz)
                
                is_intraday = best_x_data_num > mdates.date2num(datetime.datetime.now() - datetime.timedelta(days=1.5))
                time_format = "%Y-%m-%d %H:%M:%S" if is_intraday else "%Y-%m-%d"
                time_str = dt_local.strftime(time_format)
                
                daily_pct = current_data.get('daily_change_pct', 0.0)
                daily_abs = current_data.get('change_abs', 0.0)
                hourly_pct = current_data.get('hourly_change_pct', 0.0)
                hourly_abs = current_data.get('hourly_change_abs', 0.0)
                
                daily_pct_display, daily_abs_display = self._format_change_data(daily_pct, daily_abs)
                hourly_pct_display, hourly_abs_display = self._format_change_data(hourly_pct, hourly_abs)
                
                tooltip_text = (
                    f"**{closest_line_ticker}**\n"
                    f"Price: ${best_y_data:,.2f}\n"
                    f"Time ({tz.zone.split('/')[-1]}): {time_str}\n"
                    f"\n"
                    f"Daily %: {daily_pct_display}\n"
                    f"Daily $: {daily_abs_display}\n"
                    f"Hourly %: {hourly_pct_display}\n"
                    f"Hourly $: {hourly_abs_display}"
                )
                
                ax.annot.xy = (best_x_data_num, best_y_data)
                ax.annot.set_text(tooltip_text)
                ax.annot.set_visible(True)
                
                ax.vline.set_xdata([best_x_data_num]) 
                ax.vline.set_visible(True)
                ax.cursor_marker.set_data([best_x_data_num], [best_y_data]) 
                ax.cursor_marker.set_visible(True)
                
                canvas.draw_idle()
            else:
                ax.annot.set_visible(False)
                ax.cursor_marker.set_visible(False)
                ax.vline.set_visible(False)
                canvas.draw_idle()

        # Reconnect event handler
        ax.motion_cid = canvas.mpl_connect("motion_notify_event", on_motion)
            
        def on_leave(event):
            ax.annot.set_visible(False)
            ax.cursor_marker.set_visible(False)
            ax.vline.set_visible(False)
            canvas.draw_idle()
        
        ax.leave_cid = canvas.mpl_connect('axes_leave_event', on_leave)


    # --- PLOTTING FUNCTION (Main Dashboard) ---
    def _plot_main_monitor(self, ax, fig, canvas):
        print(f"[{time.strftime('%H:%M:%S')}] PLOT: Starting plot update for Main Monitor.")
        ax.clear()
        
        bg_color = self._get_safe_bg_color() 
        text_color = '#FFFFFF'
        
        ax.set_facecolor(bg_color)
        ax.tick_params(axis='x', colors=text_color)
        ax.tick_params(axis='y', colors=text_color)
        
        for spine in ax.spines.values():
            spine.set_color(text_color)
        ax.spines['right'].set_visible(False)
        ax.spines['top'].set_visible(False)
        
        has_data = False
        
        if hasattr(ax, 'annot'): ax.annot.set_visible(False)
        if hasattr(ax, 'cursor_marker'): ax.cursor_marker.set_visible(False)
        if hasattr(ax, 'vline'): ax.vline.set_visible(False)
        
        min_date_num = float('inf')
        max_date_num = float('-inf')

        # Only plot lines that are marked as visible in self.line_visibility
        for ticker, data in self.all_stock_data.items():
            if self.line_visibility.get(ticker, True) and not data.get("error") and 'history' in data:
                history_data = data['history']
                
                if not history_data.empty:
                    # Explicitly handle timezone for plotting
                    if history_data.index.tzinfo is None:
                        history_data.index = history_data.index.tz_localize(pytz.utc)

                    ax.plot(history_data.index, history_data.values, label=ticker)
                    
                    # Track min/max date range of the PLOTTED data
                    dates_num = mdates.date2num(history_data.index)
                    if len(dates_num) > 0:
                        min_date_num = min(min_date_num, dates_num.min())
                        max_date_num = max(max_date_num, dates_num.max())

                    has_data = True
                    
        if has_data:
            range_text = self.time_range_combo.get()
            ax.set_title(f"Closing Price Chart ({range_text})", color=text_color, fontsize=10)
            ax.set_ylabel('Price (AUD)', color=text_color) 
            ax.legend(loc='upper left', frameon=False, fontsize=8)

            tz_name = self.settings.get('timezone', DEFAULT_TIMEZONE)
            tz_abbr = tz_name.split('/')[-1]
            tz = pytz.timezone(tz_name)
            
            # --- FIX 1: Set explicit X-limits to data range to prevent 1970 view ---
            if min_date_num != float('inf') and max_date_num != float('-inf'):
                date_range_padding = (max_date_num - min_date_num) * 0.005
                ax.set_xlim(min_date_num - date_range_padding, max_date_num + date_range_padding)
                print(f"[{time.strftime('%H:%M:%S')}] PLOT: Setting X-limits manually to actual data range to fix 1970 issue.")

            # --- FIX 2: Specific Formatter for Intraday Ranges ---
            current_range_key = self.time_range_combo.get()

            if current_range_key in ["24 Hrs", "6 Hrs", "10 Mins"]:
                # Use MinuteLocator/HourLocator for cleaner, more compact time ticks
                # AutoDateLocator can be too coarse for short ranges, but we'll use specific locators/formatters.
                locator = mdates.HourLocator(interval=1) if current_range_key == "24 Hrs" else mdates.AutoDateLocator(minticks=5, maxticks=10)
                formatter = DateFormatter("%H:%M", tz=tz) # Time only
                ax.set_xlabel(f'Time ({tz_abbr})', color=text_color)
            else:
                # Use AutoDateLocator/Formatter for long ranges (Date and Time/Date mix)
                locator = mdates.AutoDateLocator(minticks=5, maxticks=10)
                formatter = mdates.AutoDateFormatter(locator, tz=tz)
                ax.set_xlabel(f'Time/Date ({tz_abbr})', color=text_color)
            
            ax.xaxis.set_major_locator(locator)
            ax.xaxis.set_major_formatter(formatter)
            # --- END FIX 2 ---

            
            plt.xticks(rotation=45, ha='right')
            
            self._setup_hover_annotation(ax, canvas, None, ticker=None)
            
        else:
            self._clear_plot(ax, canvas, "ADD STOCKS TO VIEW COMBINED CHART")
            if hasattr(ax, 'annot'): ax.annot.set_visible(False)
            
        plt.tight_layout(pad=0.5)
        canvas.draw_idle()
        print(f"[{time.strftime('%H:%M:%S')}] PLOT: Main Monitor plot updated.")


    # --- PLOTTING FUNCTION (Individual Tabs) ---
    def _plot_history(self, ax, fig, canvas, history_data, color, range_text, ticker):
        print(f"[{time.strftime('%H:%M:%S')}] PLOT: Starting plot update for {ticker}.")
        ax.clear()
        
        bg_color = self._get_safe_bg_color() 
        text_color = '#FFFFFF' 
        
        ax.set_facecolor(bg_color)
        ax.tick_params(axis='x', colors=text_color)
        ax.tick_params(axis='y', colors=text_color)
        
        for spine in ax.spines.values():
            spine.set_color(text_color)
        ax.spines['right'].set_visible(False)
        ax.spines['top'].set_visible(False)
        
        if hasattr(ax, 'annot'): ax.annot.set_visible(False)
        if hasattr(ax, 'cursor_marker'): ax.cursor_marker.set_visible(False)
        if hasattr(ax, 'vline'): ax.vline.set_visible(False)
        
        if history_data is not None and not history_data.empty:
            # Explicitly handle timezone for plotting
            if history_data.index.tzinfo is None:
                history_data.index = history_data.index.tz_localize(pytz.utc)

            # --- FIX 1: Set explicit X-limits to data range to prevent 1970 view ---
            dates_num = mdates.date2num(history_data.index)
            if len(dates_num) > 0:
                min_date_num = dates_num.min()
                max_date_num = dates_num.max()
                date_range_padding = (max_date_num - min_date_num) * 0.005
                ax.set_xlim(min_date_num - date_range_padding, max_date_num + date_range_padding)
                print(f"[{time.strftime('%H:%M:%S')}] PLOT: {ticker} X-limits set manually.")
            # --- END FIX ---
            
            ax.plot(history_data.index, history_data.values, color=color, linewidth=2, label=ticker)
        
        ax.set_title(f"{range_text} Closing Price", color=text_color, fontsize=10)
        ax.set_ylabel('Price', color=text_color)
        
        current_range_key = self.time_range_combo.get()
        tz_name = self.settings.get('timezone', DEFAULT_TIMEZONE)
        tz_abbr = tz_name.split('/')[-1]
        tz = pytz.timezone(tz_name)
        
        # --- FIX 2: Specific Formatter for Intraday Ranges ---
        if current_range_key in ["24 Hrs", "6 Hrs", "10 Mins"]:
            # Use MinuteLocator/HourLocator for cleaner, more compact time ticks
            locator = mdates.HourLocator(interval=1) if current_range_key == "24 Hrs" else mdates.AutoDateLocator(minticks=5, maxticks=10)
            formatter = DateFormatter("%H:%M", tz=tz) # Time only
            ax.set_xlabel(f'Time ({tz_abbr})', color=text_color)
        else:
            # Use AutoDateLocator/Formatter for long ranges (Date and Time/Date mix)
            locator = mdates.AutoDateLocator(minticks=5, maxticks=10)
            formatter = mdates.AutoDateFormatter(locator, tz=tz)
            ax.set_xlabel(f'Time/Date ({tz_abbr})', color=text_color)
        
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(formatter)
        # --- END FIX 2 ---
             
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout(pad=0.5)
        
        self._setup_hover_annotation(ax, canvas, history_data, ticker=ticker)
        
        canvas.draw_idle()
        print(f"[{time.strftime('%H:%M:%S')}] PLOT: {ticker} plot updated.")

    # --- Graceful Shutdown (Unchanged) ---
    def on_close(self):
        print(f"[{time.strftime('%H:%M:%S')}] SHUTDOWN: Application closed by user.")
        self.is_running = False
        self.executor.shutdown(wait=False, cancel_futures=True)
        save_stocks(self.tickers)
        self.destroy()
        sys.exit(0)

if __name__ == "__main__":
    try:
        from PIL import Image, ImageTk
    except ImportError:
        print("Pillow (PIL) is required for image handling. Please install it: pip install Pillow")
        sys.exit(1)
        
    try:
        import pytz 
    except ImportError:
        print("Pytz is required for timezone handling. Please install it: pip install pytz")
        sys.exit(1)
        
    try:
        plt.switch_backend('TkAgg')
    except Exception:
        pass
         
    app = TabbedStockMonitor()
    app.mainloop()
