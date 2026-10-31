"""Desktop interface for the Shodan Excel exporter (standard-library Tkinter)."""

import ipaddress
import os
from pathlib import Path
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from shodan_export import ShodanError, collect, export


def validate(key, network, pages, output):
    if not key.strip():
        raise ValueError('Shodan API 키를 입력하세요.')
    try:
        network = str(ipaddress.ip_network(network.strip(), strict=False))
    except ValueError:
        raise ValueError('유효한 IP 또는 CIDR 대역을 입력하세요.') from None
    try:
        pages = int(pages)
        if pages < 1:
            raise ValueError()
    except ValueError:
        raise ValueError('최대 페이지 수는 1 이상의 정수여야 합니다.') from None
    if not output.strip():
        raise ValueError('저장할 Excel 파일 경로를 지정하세요.')
    path = Path(output.strip()).expanduser().absolute()
    if path.suffix.lower() != '.xlsx':
        raise ValueError('저장 파일의 확장자는 .xlsx여야 합니다.')
    if path.exists():
        raise ValueError('이미 존재하는 파일입니다. 새 파일명을 지정하세요.')
    if not path.parent.is_dir():
        raise ValueError('저장 폴더가 존재하지 않습니다.')
    return key.strip(), network, pages, path


def run_export(events, key, network, pages, output):
    """The worker only sends queue events; Tk is accessed on the main thread."""
    try:
        rows, total = collect(key, network, pages,
                              progress=lambda text: events.put(('progress', text)))
        events.put(('progress', 'Excel 파일을 저장하고 있습니다…'))
        export(rows, total, network, output)
        message = f'{output}\n\n{len(rows)}개 서비스 / {len({r["ip_str"] for r in rows})}개 IP'
        if len(rows) < total:
            message += '\n일부 결과만 저장했습니다. 전체 조회가 필요하면 최대 페이지 수를 늘리세요.'
        events.put(('done', message))
    except (ShodanError, OSError) as exc:
        events.put(('error', str(exc)))
    except Exception:
        # Never expose an exception that might contain an API key in a URL.
        events.put(('error', '처리 중 오류가 발생했습니다. 입력값과 Shodan 응답을 확인하세요.'))


class App:
    def __init__(self, root):
        self.root = root
        self.events = queue.Queue()
        self.busy = False
        root.title('Shodan · IP 대역 Excel 내보내기')
        root.minsize(680, 420)
        frame = ttk.Frame(root, padding=24)
        frame.pack(fill='both', expand=True)
        frame.columnconfigure(1, weight=1)
        ttk.Label(frame, text='Shodan Excel 내보내기', font=('', 18, 'bold')).grid(
            row=0, column=0, columnspan=3, sticky='w', pady=(0, 8))
        ttk.Label(frame, text='IP 대역의 수집된 서비스 정보를 Excel 파일로 저장합니다.').grid(
            row=1, column=0, columnspan=3, sticky='w', pady=(0, 20))
        self.key = tk.StringVar(value=os.environ.get('SHODAN_API_KEY', ''))
        self.network = tk.StringVar()
        self.pages = tk.StringVar(value='1')
        self.output = tk.StringVar(value=str(Path.cwd() / 'shodan_report.xlsx'))
        self.controls = []
        for row, label, variable in [(2, 'API 키', self.key), (3, 'IP 또는 CIDR', self.network),
                                     (4, '최대 페이지 수', self.pages), (5, 'Excel 저장 경로', self.output)]:
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky='w', padx=(0, 16), pady=8)
            entry = ttk.Entry(frame, textvariable=variable, show='*' if row == 2 else '')
            entry.grid(row=row, column=1, sticky='ew', pady=8)
            self.controls.append(entry)
        browse = ttk.Button(frame, text='찾아보기…', command=self.browse)
        browse.grid(row=5, column=2, padx=(8, 0))
        self.controls.append(browse)
        ttk.Label(frame, text='예: 203.0.113.0/24 · 페이지당 최대 100개 서비스\n'
                  'Shodan 요금제/크레딧이 필요할 수 있습니다. API 키는 파일에 저장하지 않습니다.').grid(
            row=6, column=0, columnspan=3, sticky='w', pady=12)
        self.status = tk.StringVar(value='조회할 대역을 입력하세요.')
        ttk.Label(frame, textvariable=self.status, wraplength=600).grid(
            row=7, column=0, columnspan=3, sticky='w', pady=8)
        self.bar = ttk.Progressbar(frame, mode='indeterminate')
        self.bar.grid(row=8, column=0, columnspan=3, sticky='ew', pady=8)
        start = ttk.Button(frame, text='조회 후 Excel 저장', command=self.start)
        start.grid(row=9, column=0, columnspan=3, sticky='e', pady=8)
        self.controls.append(start)
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(100, self.poll)

    def browse(self):
        path = filedialog.asksaveasfilename(parent=self.root, title='Excel 저장 경로',
                                          defaultextension='.xlsx',
                                          filetypes=[('Excel 파일', '*.xlsx')])
        if path:
            self.output.set(path)

    def start(self):
        if self.busy:
            return
        try:
            args = validate(self.key.get(), self.network.get(), self.pages.get(), self.output.get())
        except ValueError as exc:
            messagebox.showerror('입력 확인', str(exc), parent=self.root)
            return
        self.busy = True
        for control in self.controls:
            control.configure(state='disabled')
        self.status.set(f'{args[1]} 조회 중…')
        self.bar.start()
        threading.Thread(target=run_export, args=(self.events, *args), daemon=True).start()

    def poll(self):
        try:
            while True:
                kind, text = self.events.get_nowait()
                if kind == 'progress':
                    self.status.set(text)
                    continue
                self.busy = False
                self.bar.stop()
                for control in self.controls:
                    control.configure(state='normal')
                self.status.set('저장 완료' if kind == 'done' else '오류 발생')
                dialog = messagebox.showinfo if kind == 'done' else messagebox.showerror
                dialog('저장 완료' if kind == 'done' else '조회 실패', text, parent=self.root)
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def close(self):
        if self.busy:
            messagebox.showinfo('조회 중', '파일 저장이 끝난 후 창을 닫아주세요.', parent=self.root)
            return
        self.root.destroy()


if __name__ == '__main__':
    root = tk.Tk()
    App(root)
    if '--smoke-test' in sys.argv:
        root.update()
        root.destroy()
    else:
        root.mainloop()
