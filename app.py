import queue
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from llm import LLMError, stream_answer
from transcriber import Transcriber


class App:
    def __init__(self, root):
        self.root = root
        self.events = queue.Queue()
        self.transcriber = Transcriber(lambda kind, value: self.events.put((kind, value)))
        self.answering = False
        self._build_window()
        self.root.after(50, self._drain_events)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_window(self):
        self.root.title("Parakeet Mini")
        self.root.geometry("780x680")
        self.root.minsize(560, 480)
        frame = ttk.Frame(self.root, padding=12)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(3, weight=1)
        frame.rowconfigure(5, weight=1)

        buttons = ttk.Frame(frame)
        buttons.grid(row=0, column=0, sticky="w")
        self.start_button = ttk.Button(buttons, text="Start", command=self._start)
        self.stop_button = ttk.Button(buttons, text="Stop", command=self._stop, state="disabled")
        self.suggest_button = ttk.Button(buttons, text="Suggest Answer", command=self._suggest)
        self.start_button.pack(side="left")
        self.stop_button.pack(side="left", padx=(8, 0))
        self.suggest_button.pack(side="left", padx=(24, 0))

        self.status = tk.StringVar(value="Ready")
        ttk.Label(frame, textvariable=self.status).grid(row=1, column=0, sticky="w", pady=(8, 8))

        ttk.Label(frame, text="Transcript (you can edit it before asking for an answer)").grid(
            row=2, column=0, sticky="w", pady=(0, 4)
        )
        self.transcript = self._text_box(frame, 3)
        ttk.Label(frame, text="Suggested answer").grid(row=4, column=0, sticky="w", pady=(12, 4))
        self.answer = self._text_box(frame, 5)

    def _text_box(self, parent, row):
        box = scrolledtext.ScrolledText(parent, wrap="word", height=8, font=("Segoe UI", 11))
        box.grid(row=row, column=0, sticky="nsew")
        return box

    def _start(self):
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.transcriber.start()

    def _stop(self):
        self.stop_button.config(state="disabled")
        self.status.set("Finishing...")
        self.transcriber.stop()

    def _suggest(self):
        question = self.transcript.get("1.0", "end").strip()
        if not question:
            self.status.set("Nothing transcribed yet. Press Start and speak.")
            return
        if self.answering:
            return
        self.answering = True
        self.suggest_button.config(state="disabled")
        self.answer.delete("1.0", "end")
        self.status.set("Generating answer...")
        threading.Thread(target=self._generate, args=(question,), daemon=True).start()

    def _generate(self, question):
        try:
            for piece in stream_answer(question):
                self.events.put(("token", piece))
            self.events.put(("answer_done", None))
        except LLMError as error:
            self.events.put(("answer_error", str(error)))
        except Exception as error:
            self.events.put(("answer_error", f"Unexpected error: {error}"))

    def _drain_events(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                self._handle(kind, value)
        except queue.Empty:
            pass
        self.root.after(50, self._drain_events)

    def _handle(self, kind, value):
        if kind == "status":
            self.status.set(value)
        elif kind == "text":
            self.transcript.insert("end", value + "\n")
            self.transcript.see("end")
        elif kind == "error":
            self.status.set("Error")
            messagebox.showerror("Parakeet Mini", value)
        elif kind == "finished":
            self.start_button.config(state="normal")
            self.stop_button.config(state="disabled")
        elif kind == "token":
            self.answer.insert("end", value)
            self.answer.see("end")
        elif kind == "answer_done":
            self.answering = False
            self.suggest_button.config(state="normal")
            self.status.set("Answer ready")
        elif kind == "answer_error":
            self.answering = False
            self.suggest_button.config(state="normal")
            self.status.set("Error")
            messagebox.showerror("Parakeet Mini", value)

    def _on_close(self):
        self.transcriber.stop()
        self.root.destroy()


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
