import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import os
import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path
import base64
from typing import List, Dict
import requests
import certifi
from urllib.parse import urlencode
import urllib3
from tkcalendar import DateEntry
import time

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class TwilioConfig:
    def __init__(self):
        self.config_path = Path.home() / '.twilio_gui_config.json'
        self.accounts = self.load_accounts()
    
    def load_accounts(self) -> Dict:
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                return json.load(f)
        return {}
    
    def save_accounts(self):
        with open(self.config_path, 'w') as f:
            json.dump(self.accounts, f, indent=2)
    
    def add_account(self, name: str, account_sid: str, auth_token: str):
        self.accounts[name] = {
            'account_sid': account_sid,
            'auth_token': base64.b64encode(auth_token.encode()).decode()
        }
        self.save_accounts()
    
    def get_account(self, name: str) -> Dict:
        if name in self.accounts:
            acc = self.accounts[name].copy()
            acc['auth_token'] = base64.b64decode(acc['auth_token']).decode()
            return acc
        return None
    
    def delete_account(self, name: str):
        if name in self.accounts:
            del self.accounts[name]
            self.save_accounts()

class TwilioAPI:
    def __init__(self, account_sid: str, auth_token: str):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.base_url = f'https://api.twilio.com/2010-04-01/Accounts/{account_sid}'
        self.timeout = 30
        self.max_retries = 3
    
    def _make_request(self, url: str, params: Dict = None) -> requests.Response:
        """Make HTTP request with timeout and retry logic"""
        auth = (self.account_sid, self.auth_token)
        
        for attempt in range(self.max_retries):
            try:
                return requests.get(url, auth=auth, params=params, verify=False, timeout=self.timeout)
            except requests.exceptions.Timeout:
                if attempt == self.max_retries - 1:
                    raise Exception(f"Request timed out after {self.max_retries} attempts")
                time.sleep(1)
            except requests.exceptions.ConnectionError:
                if attempt == self.max_retries - 1:
                    raise Exception(f"Connection failed after {self.max_retries} attempts. Check your internet connection.")
                time.sleep(1)
            except requests.exceptions.RequestException as e:
                raise Exception(f"Network error: {str(e)}")
    
    def get_incoming_phone_numbers(self) -> List[Dict]:
        """Fetch all phone numbers in the account"""
        url = f'{self.base_url}/IncomingPhoneNumbers.json'
        all_numbers = []
        
        while url:
            response = self._make_request(url)
            if response.status_code != 200:
                raise Exception(f"API Error: {response.status_code}\nResponse: {response.text}")
            
            data = response.json()
            for num in data.get('incoming_phone_numbers', []):
                all_numbers.append({
                    'phone_number': num['phone_number'],
                    'friendly_name': num['friendly_name'],
                    'sid': num['sid']
                })
            
            url = data.get('next_page_uri')
            if url:
                url = f'https://api.twilio.com{url}'
        
        return all_numbers
    
    def get_phone_number_config(self, phone_number_sid: str) -> Dict:
        """Fetch configuration for a specific phone number"""
        url = f'{self.base_url}/IncomingPhoneNumbers/{phone_number_sid}.json'
        
        response = self._make_request(url)
        if response.status_code != 200:
            raise Exception(f"API Error: {response.status_code}\nResponse: {response.text}")
        
        return response.json()
    
    def check_number_activity(self, phone_number: str, days: int) -> Dict:
        """Check if a number has any calls or messages in the last X days"""
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        end_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        
        # Check for calls TO the number (inbound)
        calls = self._fetch_calls({'To': phone_number, 'StartTime>': cutoff_date, 'StartTime<': end_date})
        
        # Check for messages FROM the number (outbound)
        messages = self._fetch_messages({'From': phone_number, 'DateSent>': cutoff_date, 'DateSent<': end_date})
        
        return {
            'phone_number': phone_number,
            'call_count': len(calls),
            'message_count': len(messages),
            'total_activity': len(calls) + len(messages),
            'is_inactive': len(calls) + len(messages) == 0
        }
    
    def get_calls(self, phone_number: str, start_date: str, end_date: str) -> List[Dict]:
        """Fetch calls to and from a phone number"""
        calls = []
        
        # Get calls TO the number
        calls.extend(self._fetch_calls({'To': phone_number, 'StartTime>': start_date, 'StartTime<': end_date}))
        
        # Get calls FROM the number
        calls.extend(self._fetch_calls({'From': phone_number, 'StartTime>': start_date, 'StartTime<': end_date}))
        
        # Sort by date
        calls.sort(key=lambda x: x.get('sort_key', 0), reverse=True)
        return calls
    
    def _fetch_calls(self, params: Dict) -> List[Dict]:
        """Fetch calls with pagination"""
        url = f'{self.base_url}/Calls.json'
        all_calls = []
        
        params['PageSize'] = 100
        first_request = True
        
        while url:
            response = self._make_request(url, params if first_request else None)
            first_request = False
            
            if response.status_code != 200:
                raise Exception(f"API Error: {response.status_code}\nResponse: {response.text}")
            
            data = response.json()
            for call in data.get('calls', []):
                # Convert UTC timestamp to local time, preserving milliseconds
                start_time_utc = call['start_time']
                try:
                    dt = datetime.strptime(start_time_utc, '%a, %d %b %Y %H:%M:%S %z')
                    local_time = dt.astimezone().strftime('%Y-%m-%d %H:%M:%S')
                    sort_key = dt.timestamp()  # Use Unix timestamp for precise sorting
                except:
                    local_time = start_time_utc
                    sort_key = 0
                
                all_calls.append({
                    'direction': 'Outbound' if call['direction'].startswith('outbound') else 'Inbound',
                    'from': call['from'],
                    'to': call['to'],
                    'start_time': local_time,
                    'duration': call['duration'],
                    'status': call['status'],
                    'sid': call['sid'],
                    'events_uri': call.get('subresource_uris', {}).get('events', ''),
                    'sort_key': sort_key
                })
            
            # Check for next page
            url = data.get('next_page_uri')
            if url:
                url = f'https://api.twilio.com{url}'
        
        return all_calls
    
    def get_call_events(self, call_sid: str) -> List[Dict]:
        """Fetch events for a specific call"""
        url = f'{self.base_url}/Calls/{call_sid}/Events.json'
        
        response = self._make_request(url)
        if response.status_code != 200:
            raise Exception(f"API Error: {response.status_code}\nResponse: {response.text}")
        
        data = response.json()
        return data.get('events', [])
    
    def get_message_details(self, message_sid: str) -> Dict:
        """Fetch full details for a specific message"""
        url = f'{self.base_url}/Messages/{message_sid}.json'
        
        response = self._make_request(url)
        if response.status_code != 200:
            raise Exception(f"API Error: {response.status_code}\nResponse: {response.text}")
        
        return response.json()
    
    def get_messages(self, phone_number: str, start_date: str, end_date: str) -> List[Dict]:
        """Fetch messages to and from a phone number"""
        messages = []
        messages.extend(self._fetch_messages({'To': phone_number, 'DateSent>': start_date, 'DateSent<': end_date}))
        messages.extend(self._fetch_messages({'From': phone_number, 'DateSent>': start_date, 'DateSent<': end_date}))
        messages.sort(key=lambda x: x.get('sort_key', 0), reverse=True)
        return messages
    
    def _fetch_messages(self, params: Dict) -> List[Dict]:
        """Fetch messages with pagination"""
        url = f'{self.base_url}/Messages.json'
        all_messages = []
        params['PageSize'] = 100
        first_request = True
        
        while url:
            response = self._make_request(url, params if first_request else None)
            first_request = False
            
            if response.status_code != 200:
                raise Exception(f"API Error: {response.status_code}\nResponse: {response.text}")
            
            data = response.json()
            for msg in data.get('messages', []):
                # Convert UTC timestamp to local time, preserving milliseconds
                date_sent_utc = msg['date_sent']
                try:
                    dt = datetime.strptime(date_sent_utc, '%a, %d %b %Y %H:%M:%S %z')
                    local_time = dt.astimezone().strftime('%Y-%m-%d %H:%M:%S')
                    sort_key = dt.timestamp()  # Use Unix timestamp for precise sorting
                except:
                    local_time = date_sent_utc
                    sort_key = 0
                
                # Replace newlines with space for grid display
                body_text = msg['body'].replace('\n', ' ').replace('\r', '')
                body_preview = body_text[:50] + '...' if len(body_text) > 50 else body_text
                
                all_messages.append({
                    'direction': 'Outbound' if msg['direction'] == 'outbound-api' else 'Inbound',
                    'from': msg['from'],
                    'to': msg['to'],
                    'date_sent': local_time,
                    'body': body_preview,
                    'status': msg['status'],
                    'sid': msg['sid'],
                    'error_code': msg.get('error_code', ''),
                    'error_message': msg.get('error_message', ''),
                    'sort_key': sort_key
                })
            
            url = data.get('next_page_uri')
            if url:
                url = f'https://api.twilio.com{url}'
        
        return all_messages

class TwilioGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Twilio Manager")
        self.root.geometry("1000x700")
        
        self.config = TwilioConfig()
        self.current_account = tk.StringVar()
        self.data_mode = tk.StringVar(value="calls")
        self.sort_reverse = {}  # Track sort direction per column
        self.tree_data = {}  # Store hidden data like sort_key for each tree item
        self.all_data = []  # Store all fetched data for filtering
        
        self.setup_ui()
    
    def setup_ui(self):
        # Create notebook for tabs
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        notebook.bind('<<NotebookTabChanged>>', self.on_tab_changed)
        
        # Tab 1: Call/Message Lookup
        lookup_frame = ttk.Frame(notebook)
        notebook.add(lookup_frame, text="Call/Message Lookup")
        self.setup_lookup_tab(lookup_frame)
        
        # Tab 2: Inactive Numbers
        inactive_frame = ttk.Frame(notebook)
        notebook.add(inactive_frame, text="Inactive Numbers")
        self.setup_inactive_tab(inactive_frame)
        
        # Tab 3: Number Configuration
        config_frame = ttk.Frame(notebook)
        notebook.add(config_frame, text="Number Configuration")
        self.setup_config_tab(config_frame)
        
        # Refresh accounts after all tabs are created
        self.refresh_accounts()
    
    def on_tab_changed(self, event=None):
        """Sync account selection across tabs when switching"""
        # Auto-load numbers for config tab if account is selected
        if hasattr(self, 'config_account_combo') and self.current_account.get():
            self.load_numbers_for_config()
    
    def setup_lookup_tab(self, parent):
        # Main container
        main_frame = ttk.Frame(parent, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Account Management Section
        account_frame = ttk.LabelFrame(main_frame, text="Account", padding="5")
        account_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(account_frame, text="Select Account:").grid(row=0, column=0, padx=5)
        self.account_combo = ttk.Combobox(account_frame, textvariable=self.current_account, width=20)
        self.account_combo.grid(row=0, column=1, padx=5)
        
        ttk.Button(account_frame, text="Add Account", command=self.add_account_dialog).grid(row=0, column=2, padx=5)
        ttk.Button(account_frame, text="Delete", command=self.delete_account).grid(row=0, column=3, padx=5)
        
        # Query Section
        query_frame = ttk.LabelFrame(main_frame, text="Query Parameters", padding="5")
        query_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(query_frame, text="Data Type:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        mode_frame = ttk.Frame(query_frame)
        mode_frame.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        ttk.Radiobutton(mode_frame, text="Calls", variable=self.data_mode, value="calls").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(mode_frame, text="Messages", variable=self.data_mode, value="messages").pack(side=tk.LEFT, padx=5)
        
        ttk.Label(query_frame, text="Phone Number:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.phone_entry = ttk.Entry(query_frame, width=20)
        self.phone_entry.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        ttk.Label(query_frame, text="(e.g., +17246134570)").grid(row=1, column=2, sticky=tk.W)
        
        ttk.Label(query_frame, text="Start Date:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.start_date = DateEntry(query_frame, width=18, background='darkblue', foreground='white', borderwidth=2, date_pattern='yyyy-mm-dd')
        self.start_date.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        self.start_date.set_date(datetime.now() - timedelta(days=7))
        
        ttk.Label(query_frame, text="End Date:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.end_date = DateEntry(query_frame, width=18, background='darkblue', foreground='white', borderwidth=2, date_pattern='yyyy-mm-dd')
        self.end_date.grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)
        self.end_date.set_date(datetime.now())
        
        ttk.Button(query_frame, text="Fetch Data", command=self.fetch_data).grid(row=4, column=1, pady=10)
        ttk.Button(query_frame, text="Export CSV", command=self.export_csv).grid(row=4, column=2, pady=10, padx=5)
        
        # Search/Filter Section
        filter_frame = ttk.Frame(main_frame)
        filter_frame.grid(row=1, column=3, sticky=(tk.W, tk.E, tk.N), padx=(10, 0))
        
        ttk.Label(filter_frame, text="Filter:").pack()
        self.filter_entry = ttk.Entry(filter_frame, width=20)
        self.filter_entry.pack(pady=5)
        self.filter_entry.bind('<KeyRelease>', self.filter_results)
        ttk.Button(filter_frame, text="Clear Filter", command=self.clear_filter).pack()
        
        # Results Section
        results_frame = ttk.LabelFrame(main_frame, text="Results (Double-click row for events)", padding="5")
        results_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        main_frame.rowconfigure(2, weight=1)
        
        # Treeview for results
        self.tree = ttk.Treeview(results_frame, show='headings', height=20)
        
        scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        
        self.tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)
        
        self.setup_tree_columns("calls")
        
        # Bind double-click to show events
        self.tree.bind('<Double-Button-1>', self.show_call_message_events)
        
        # Bind right-click for copy menu
        self.tree.bind('<Button-3>', self.show_context_menu)
        
        # Create context menu
        self.context_menu = tk.Menu(self.tree, tearoff=0)
        self.context_menu.add_command(label="Copy SID", command=lambda: self.copy_to_clipboard('sid'))
        self.context_menu.add_command(label="Copy From Number", command=lambda: self.copy_to_clipboard('from'))
        self.context_menu.add_command(label="Copy To Number", command=lambda: self.copy_to_clipboard('to'))
        
        # Status bar
        self.status_label = ttk.Label(main_frame, text="Ready", relief=tk.SUNKEN)
        self.status_label.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E))
    
    def setup_inactive_tab(self, parent):
        # Main container
        main_frame = ttk.Frame(parent, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        
        # Account Selection
        account_frame = ttk.LabelFrame(main_frame, text="Account", padding="5")
        account_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(account_frame, text="Select Account:").grid(row=0, column=0, padx=5)
        self.inactive_account_combo = ttk.Combobox(account_frame, textvariable=self.current_account, width=20)
        self.inactive_account_combo.grid(row=0, column=1, padx=5)
        
        ttk.Label(account_frame, text="Inactive Days:").grid(row=0, column=2, padx=5)
        self.inactive_days = ttk.Spinbox(account_frame, from_=1, to=365, width=10)
        self.inactive_days.set(30)
        self.inactive_days.grid(row=0, column=3, padx=5)
        
        ttk.Button(account_frame, text="Find Inactive Numbers", command=self.find_inactive_numbers).grid(row=0, column=4, padx=5)
        
        # Results
        results_frame = ttk.LabelFrame(main_frame, text="Inactive Numbers", padding="5")
        results_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        main_frame.rowconfigure(1, weight=1)
        
        # Progress bar
        self.inactive_progress = ttk.Progressbar(results_frame, mode='determinate')
        self.inactive_progress.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        self.inactive_progress.grid_remove()  # Hide initially
        
        columns = ('Phone Number', 'Friendly Name', 'Calls', 'Messages', 'Total Activity')
        self.inactive_tree = ttk.Treeview(results_frame, columns=columns, show='headings', height=20)
        
        for col in columns:
            self.inactive_tree.heading(col, text=col)
            self.inactive_tree.column(col, width=150)
        
        scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.inactive_tree.yview)
        self.inactive_tree.configure(yscroll=scrollbar.set)
        
        self.inactive_tree.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=1, column=1, sticky=(tk.N, tk.S))
        
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)
        
        # Status
        self.inactive_status_label = ttk.Label(main_frame, text="Ready", relief=tk.SUNKEN)
        self.inactive_status_label.grid(row=2, column=0, sticky=(tk.W, tk.E))
    
    def setup_config_tab(self, parent):
        # Main container
        main_frame = ttk.Frame(parent, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        
        # Account and Number Selection
        select_frame = ttk.LabelFrame(main_frame, text="Select Number", padding="5")
        select_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(select_frame, text="Account:").grid(row=0, column=0, padx=5, pady=5)
        self.config_account_combo = ttk.Combobox(select_frame, textvariable=self.current_account, width=20)
        self.config_account_combo.grid(row=0, column=1, padx=5, pady=5)
        self.config_account_combo.bind('<<ComboboxSelected>>', self.load_numbers_for_config)
        
        ttk.Label(select_frame, text="Phone Number:").grid(row=0, column=2, padx=5, pady=5)
        self.config_number_combo = ttk.Combobox(select_frame, width=20)
        self.config_number_combo.grid(row=0, column=3, padx=5, pady=5)
        
        ttk.Button(select_frame, text="Load Configuration", command=self.load_number_config).grid(row=0, column=4, padx=5, pady=5)
        
        # Configuration Display
        config_display_frame = ttk.LabelFrame(main_frame, text="Configuration", padding="5")
        config_display_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        main_frame.rowconfigure(1, weight=1)
        
        # Text widget for config display
        text_frame = ttk.Frame(config_display_frame)
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        self.config_text = tk.Text(text_frame, wrap=tk.WORD, height=25, width=80)
        config_scrollbar = ttk.Scrollbar(text_frame, command=self.config_text.yview)
        self.config_text.configure(yscrollcommand=config_scrollbar.set)
        
        self.config_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        config_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Status
        self.config_status_label = ttk.Label(main_frame, text="Ready", relief=tk.SUNKEN)
        self.config_status_label.grid(row=2, column=0, sticky=(tk.W, tk.E))
    
    def refresh_accounts(self):
        accounts = list(self.config.accounts.keys())
        self.account_combo['values'] = accounts
        if hasattr(self, 'inactive_account_combo'):
            self.inactive_account_combo['values'] = accounts
            if not self.inactive_account_combo.get() and accounts:
                self.inactive_account_combo.set(self.current_account.get())
        if hasattr(self, 'config_account_combo'):
            self.config_account_combo['values'] = accounts
            if not self.config_account_combo.get() and accounts:
                self.config_account_combo.set(self.current_account.get())
        if accounts and not self.current_account.get():
            self.current_account.set(accounts[0])
    
    def add_account_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Twilio Account")
        dialog.geometry("400x200")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Account Name:").grid(row=0, column=0, padx=10, pady=10, sticky=tk.W)
        name_entry = ttk.Entry(dialog, width=30)
        name_entry.grid(row=0, column=1, padx=10, pady=10)
        
        ttk.Label(dialog, text="Account SID:").grid(row=1, column=0, padx=10, pady=10, sticky=tk.W)
        sid_entry = ttk.Entry(dialog, width=30)
        sid_entry.grid(row=1, column=1, padx=10, pady=10)
        
        ttk.Label(dialog, text="Auth Token:").grid(row=2, column=0, padx=10, pady=10, sticky=tk.W)
        token_entry = ttk.Entry(dialog, width=30, show="*")
        token_entry.grid(row=2, column=1, padx=10, pady=10)
        
        def save():
            name = name_entry.get().strip()
            sid = sid_entry.get().strip()
            token = token_entry.get().strip()
            
            if not name or not sid or not token:
                messagebox.showerror("Error", "All fields are required")
                return
            
            self.config.add_account(name, sid, token)
            self.refresh_accounts()
            self.current_account.set(name)
            dialog.destroy()
            messagebox.showinfo("Success", f"Account '{name}' added successfully")
        
        ttk.Button(dialog, text="Save", command=save).grid(row=3, column=1, pady=20)
    
    def delete_account(self):
        account = self.current_account.get()
        if not account:
            messagebox.showwarning("Warning", "No account selected")
            return
        
        if messagebox.askyesno("Confirm", f"Delete account '{account}'?"):
            self.config.delete_account(account)
            self.refresh_accounts()
            messagebox.showinfo("Success", f"Account '{account}' deleted")
    
    def setup_tree_columns(self, mode):
        """Configure tree columns based on data mode"""
        for col in self.tree['columns']:
            self.tree.heading(col, text='')
        
        if mode == "calls":
            columns = ('Direction', 'From', 'To', 'Start Time', 'Duration (s)', 'Status', 'SID')
        else:
            columns = ('Direction', 'From', 'To', 'Date Sent', 'Message', 'Status', 'SID')
        
        self.tree['columns'] = columns
        for col in columns:
            self.tree.heading(col, text=col, command=lambda c=col: self.sort_tree_column(c))
            self.tree.column(col, width=150)
    
    def show_context_menu(self, event):
        """Show right-click context menu"""
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)
    
    def copy_to_clipboard(self, field):
        """Copy field value to clipboard"""
        selection = self.tree.selection()
        if not selection:
            return
        
        item = self.tree.item(selection[0])
        values = item['values']
        
        if field == 'sid':
            value = values[-1]
        elif field == 'from':
            value = values[1]
        elif field == 'to':
            value = values[2]
        else:
            return
        
        self.root.clipboard_clear()
        self.root.clipboard_append(value)
        self.status_label.config(text=f"Copied {field}: {value}")
    
    def filter_results(self, event=None):
        """Filter displayed results based on search text"""
        search_text = self.filter_entry.get().lower()
        
        # Clear current display
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.tree_data.clear()
        
        # Re-populate with filtered data
        mode = self.data_mode.get()
        for item in self.all_data:
            # Search in all visible fields
            searchable = ' '.join(str(v).lower() for v in item.values() if v)
            if search_text in searchable:
                if mode == "calls":
                    item_id = self.tree.insert('', tk.END, values=(
                        item['direction'], item['from'], item['to'],
                        item['start_time'], item['duration'], item['status'], item['sid']
                    ))
                else:
                    item_id = self.tree.insert('', tk.END, values=(
                        item['direction'], item['from'], item['to'],
                        item['date_sent'], item['body'], item['status'], item['sid']
                    ))
                self.tree_data[item_id] = {'sort_key': item.get('sort_key', 0)}
        
        count = len(self.tree.get_children())
        self.status_label.config(text=f"Showing {count} of {len(self.all_data)} {mode}")
    
    def clear_filter(self):
        """Clear filter and show all results"""
        self.filter_entry.delete(0, tk.END)
        self.filter_results()
    
    def sort_tree_column(self, col):
        """Sort tree contents when column header is clicked"""
        # Toggle sort direction for this column
        self.sort_reverse[col] = not self.sort_reverse.get(col, False)
        
        items = []
        for item_id in self.tree.get_children(''):
            # For timestamp columns, use hidden sort_key if available
            if col in ('Start Time', 'Date Sent') and item_id in self.tree_data:
                sort_value = self.tree_data[item_id].get('sort_key', 0)
            else:
                sort_value = self.tree.set(item_id, col)
            items.append((sort_value, item_id))
        
        # Try numeric sort, otherwise alphabetic
        try:
            items.sort(key=lambda x: float(x[0]) if x[0] else 0, reverse=self.sort_reverse[col])
        except (ValueError, TypeError):
            items.sort(reverse=self.sort_reverse[col])
        
        for index, (val, item_id) in enumerate(items):
            self.tree.move(item_id, '', index)
        
        # Update column header to show sort direction
        for column in self.tree['columns']:
            current_text = column
            if column == col:
                arrow = ' ▼' if self.sort_reverse[col] else ' ▲'
                current_text = column + arrow
            self.tree.heading(column, text=current_text, command=lambda c=column: self.sort_tree_column(c))
    
    def fetch_data(self):
        account_name = self.current_account.get()
        if not account_name:
            messagebox.showerror("Error", "Please select an account")
            return
        
        phone = self.phone_entry.get().strip()
        if not phone:
            messagebox.showerror("Error", "Please enter a phone number")
            return
        
        # Auto-format phone number to E.164 if needed
        if not phone.startswith('+'):
            if len(phone) == 10:
                phone = f'+1{phone}'
            elif len(phone) == 11 and phone.startswith('1'):
                phone = f'+{phone}'
            else:
                messagebox.showerror("Error", "Phone must be E.164 format (+19193736940) or 10 digits")
                return
        
        start = self.start_date.get_date().strftime('%Y-%m-%d')
        end = (self.end_date.get_date() + timedelta(days=1)).strftime('%Y-%m-%d')
        
        mode = self.data_mode.get()
        self.setup_tree_columns(mode)
        
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.tree_data.clear()
        
        self.status_label.config(text=f"Fetching {mode}...")
        self.root.update()
        
        try:
            account = self.config.get_account(account_name)
            if not account:
                messagebox.showerror("Error", f"Account '{account_name}' not found")
                return
            
            # Debug: verify credentials format
            sid = account['account_sid']
            token = account['auth_token']
            
            if not sid.startswith('AC') or len(sid) != 34:
                self.show_error_dialog("Invalid Account SID", f"Account SID should start with 'AC' and be 34 characters.\nGot: {sid[:10]}... (length: {len(sid)})")
                return
            
            if len(token) < 32:
                self.show_error_dialog("Invalid Auth Token", f"Auth Token seems too short (length: {len(token)})")
                return
            
            api = TwilioAPI(sid, token)
            
            if mode == "calls":
                data = api.get_calls(phone, start, end)
                self.all_data = data  # Store for filtering
                for item in data:
                    item_id = self.tree.insert('', tk.END, values=(
                        item['direction'], item['from'], item['to'],
                        item['start_time'], item['duration'], item['status'], item['sid']
                    ))
                    self.tree_data[item_id] = {'sort_key': item.get('sort_key', 0)}
            else:
                data = api.get_messages(phone, start, end)
                self.all_data = data  # Store for filtering
                for item in data:
                    item_id = self.tree.insert('', tk.END, values=(
                        item['direction'], item['from'], item['to'],
                        item['date_sent'], item['body'], item['status'], item['sid']
                    ))
                    self.tree_data[item_id] = {'sort_key': item.get('sort_key', 0)}
            
            result_text = f"Found {len(data)} {mode}"
            if len(data) >= 1000:
                result_text += " (Large result - some data may not display. Try shorter date range)"
            self.status_label.config(text=result_text)
            
        except Exception as e:
            self.show_error_dialog(f"Failed to fetch {mode}", str(e))
            self.status_label.config(text="Error")
    
    def show_error_dialog(self, title, message):
        """Show error in a copyable text dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry("600x300")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text=title, font=('Arial', 10, 'bold')).pack(pady=10)
        
        text_frame = ttk.Frame(dialog)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        text_widget = tk.Text(text_frame, wrap=tk.WORD, height=10)
        scrollbar = ttk.Scrollbar(text_frame, command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        text_widget.insert('1.0', message)
        text_widget.config(state=tk.NORMAL)
        
        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)
    
    def export_csv(self):
        """Export current results to CSV"""
        if not self.tree.get_children():
            messagebox.showwarning("No Data", "No results to export. Fetch data first.")
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"twilio_{self.data_mode.get()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        
        if not filename:
            return
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # Write headers
                writer.writerow(self.tree['columns'])
                
                # Write data
                for item in self.tree.get_children():
                    writer.writerow(self.tree.item(item)['values'])
            
            messagebox.showinfo("Success", f"Exported {len(self.tree.get_children())} rows to {os.path.basename(filename)}")
            
        except Exception as e:
            self.show_error_dialog("Export Failed", str(e))
    
    def find_inactive_numbers(self):
        account_name = self.inactive_account_combo.get()
        if not account_name:
            messagebox.showerror("Error", "Please select an account")
            return
        
        try:
            days = int(self.inactive_days.get())
        except ValueError:
            messagebox.showerror("Error", "Invalid number of days")
            return
        
        for item in self.inactive_tree.get_children():
            self.inactive_tree.delete(item)
        
        self.inactive_status_label.config(text=f"Fetching phone numbers...")
        self.root.update()
        
        try:
            account = self.config.get_account(account_name)
            if not account:
                messagebox.showerror("Error", f"Account '{account_name}' not found")
                return
            
            api = TwilioAPI(account['account_sid'], account['auth_token'])
            
            # Get all phone numbers
            numbers = api.get_incoming_phone_numbers()
            self.inactive_status_label.config(text=f"Checking {len(numbers)} numbers for activity...")
            
            # Show and configure progress bar
            self.inactive_progress.grid()
            self.inactive_progress['maximum'] = len(numbers)
            self.inactive_progress['value'] = 0
            self.root.update()
            
            inactive_count = 0
            for i, num in enumerate(numbers):
                self.inactive_status_label.config(text=f"Checking {i+1}/{len(numbers)}: {num['phone_number']}")
                self.inactive_progress['value'] = i + 1
                self.root.update()
                
                activity = api.check_number_activity(num['phone_number'], days)
                
                if activity['is_inactive']:
                    self.inactive_tree.insert('', tk.END, values=(
                        activity['phone_number'],
                        num['friendly_name'],
                        activity['call_count'],
                        activity['message_count'],
                        activity['total_activity']
                    ))
                    inactive_count += 1
            
            self.inactive_status_label.config(text=f"Found {inactive_count} inactive numbers (out of {len(numbers)} total)")
            self.inactive_progress.grid_remove()  # Hide progress bar when done
            
        except Exception as e:
            self.inactive_progress.grid_remove()
            self.show_error_dialog("Error Finding Inactive Numbers", str(e))
            self.inactive_status_label.config(text="Error")
    
    def load_numbers_for_config(self, event=None):
        """Load phone numbers when account is selected"""
        account_name = self.config_account_combo.get()
        if not account_name:
            return
        
        self.config_status_label.config(text="Loading phone numbers...")
        self.root.update()
        
        try:
            account = self.config.get_account(account_name)
            if not account:
                self.config_status_label.config(text="Account not found")
                return
            
            api = TwilioAPI(account['account_sid'], account['auth_token'])
            numbers = api.get_incoming_phone_numbers()
            
            # Store numbers with their SIDs
            self.number_sid_map = {f"{num['phone_number']} ({num['friendly_name']})": num['sid'] for num in numbers}
            self.config_number_combo['values'] = list(self.number_sid_map.keys())
            
            self.config_status_label.config(text=f"Loaded {len(numbers)} phone numbers")
            return True
            
        except Exception as e:
            self.show_error_dialog("Error Loading Numbers", str(e))
            self.config_status_label.config(text="Error")
            return False
    
    def load_number_config(self):
        """Load and display configuration for selected number"""
        account_name = self.config_account_combo.get()
        number_display = self.config_number_combo.get()
        
        if not account_name:
            messagebox.showerror("Error", "Please select an account")
            return
        
        if not number_display:
            messagebox.showerror("Error", "Please select a phone number")
            return
        
        if not hasattr(self, 'number_sid_map') or number_display not in self.number_sid_map:
            # Try to load numbers first
            self.load_numbers_for_config()
            if not hasattr(self, 'number_sid_map') or number_display not in self.number_sid_map:
                messagebox.showerror("Error", "Failed to load phone numbers")
                return
        
        phone_sid = self.number_sid_map[number_display]
        
        self.config_status_label.config(text="Loading configuration...")
        self.root.update()
        
        try:
            account = self.config.get_account(account_name)
            api = TwilioAPI(account['account_sid'], account['auth_token'])
            
            config = api.get_phone_number_config(phone_sid)
            
            # Display configuration in readable format
            self.config_text.delete('1.0', tk.END)
            
            # Key configuration fields
            fields = [
                ('Phone Number', 'phone_number'),
                ('Friendly Name', 'friendly_name'),
                ('SID', 'sid'),
                ('Voice URL', 'voice_url'),
                ('Voice Method', 'voice_method'),
                ('Voice Fallback URL', 'voice_fallback_url'),
                ('Status Callback URL', 'status_callback'),
                ('SMS URL', 'sms_url'),
                ('SMS Method', 'sms_method'),
                ('SMS Fallback URL', 'sms_fallback_url'),
                ('Capabilities - Voice', 'capabilities.voice'),
                ('Capabilities - SMS', 'capabilities.sms'),
                ('Capabilities - MMS', 'capabilities.mms'),
                ('Emergency Enabled', 'emergency_status'),
                ('Trunk SID', 'trunk_sid'),
                ('Voice Application SID', 'voice_application_sid'),
                ('SMS Application SID', 'sms_application_sid')
            ]
            
            for label, key in fields:
                value = config
                for k in key.split('.'):
                    value = value.get(k, '') if isinstance(value, dict) else ''
                
                if value:
                    self.config_text.insert(tk.END, f"{label}:\n  {value}\n\n")
            
            self.config_status_label.config(text="Configuration loaded")
            
        except Exception as e:
            self.show_error_dialog("Error Loading Configuration", str(e))
            self.config_status_label.config(text="Error")
    
    def show_call_message_events(self, event):
        """Show events for selected call or message"""
        selection = self.tree.selection()
        if not selection:
            return
        
        item = self.tree.item(selection[0])
        values = item['values']
        
        # SID is the last column
        sid = values[-1]
        mode = self.data_mode.get()
        
        account_name = self.current_account.get()
        if not account_name:
            return
        
        # Create events dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(f"{mode.capitalize()} Events - {sid}")
        dialog.geometry("800x500")
        dialog.transient(self.root)
        
        # Info section
        info_frame = ttk.Frame(dialog, padding="10")
        info_frame.pack(fill=tk.X)
        
        ttk.Label(info_frame, text=f"From: {values[1]}  |  To: {values[2]}  |  Status: {values[5]}", font=('Arial', 9, 'bold')).pack()
        
        # Events display
        events_frame = ttk.Frame(dialog, padding="10")
        events_frame.pack(fill=tk.BOTH, expand=True)
        
        text_widget = tk.Text(events_frame, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(events_frame, command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        text_widget.insert('1.0', "Loading events...\n")
        dialog.update()
        
        try:
            account = self.config.get_account(account_name)
            api = TwilioAPI(account['account_sid'], account['auth_token'])
            
            if mode == "calls":
                events = api.get_call_events(sid)
                
                text_widget.delete('1.0', tk.END)
                
                if not events:
                    text_widget.insert(tk.END, "No events found for this call.\n")
                else:
                    for event in events:
                        text_widget.insert(tk.END, f"Event: {event.get('name', 'Unknown')}\n")
                        text_widget.insert(tk.END, f"Timestamp: {event.get('timestamp', 'N/A')}\n")
                        if event.get('request'):
                            text_widget.insert(tk.END, f"Request: {event['request'].get('url', 'N/A')}\n")
                            text_widget.insert(tk.END, f"Method: {event['request'].get('method', 'N/A')}\n")
                        if event.get('response'):
                            text_widget.insert(tk.END, f"Response Status: {event['response'].get('status_code', 'N/A')}\n")
                        text_widget.insert(tk.END, "\n" + "-"*80 + "\n\n")
            else:
                # For messages, show full message details
                msg_details = api.get_message_details(sid)
                
                text_widget.delete('1.0', tk.END)
                
                text_widget.insert(tk.END, f"Message SID: {sid}\n\n")
                text_widget.insert(tk.END, f"Direction: {msg_details.get('direction', 'N/A')}\n")
                text_widget.insert(tk.END, f"From: {msg_details.get('from', 'N/A')}\n")
                text_widget.insert(tk.END, f"To: {msg_details.get('to', 'N/A')}\n")
                text_widget.insert(tk.END, f"Date Sent: {msg_details.get('date_sent', 'N/A')}\n")
                text_widget.insert(tk.END, f"Date Updated: {msg_details.get('date_updated', 'N/A')}\n")
                text_widget.insert(tk.END, f"Status: {msg_details.get('status', 'N/A')}\n\n")
                
                # Full message body
                text_widget.insert(tk.END, f"Message Body:\n{msg_details.get('body', 'N/A')}\n\n")
                
                # Error info if present
                if msg_details.get('error_code'):
                    text_widget.insert(tk.END, f"ERROR CODE: {msg_details.get('error_code')}\n")
                    text_widget.insert(tk.END, f"ERROR MESSAGE: {msg_details.get('error_message', 'N/A')}\n\n")
                
                # Pricing
                if msg_details.get('price'):
                    text_widget.insert(tk.END, f"Price: {msg_details.get('price')} {msg_details.get('price_unit', '')}\n")
                
                # Segments (for long SMS)
                if msg_details.get('num_segments'):
                    text_widget.insert(tk.END, f"Segments: {msg_details.get('num_segments')}\n")
                
                # Media (MMS)
                if msg_details.get('num_media') and int(msg_details.get('num_media', 0)) > 0:
                    text_widget.insert(tk.END, f"\nMedia Attachments: {msg_details.get('num_media')}\n")
        
        except Exception as e:
            text_widget.delete('1.0', tk.END)
            text_widget.insert(tk.END, f"Error loading events:\n\n{str(e)}")
        
        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)

def main():
    root = tk.Tk()
    app = TwilioGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
