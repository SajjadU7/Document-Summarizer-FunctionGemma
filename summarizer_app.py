import sys
import re
import os
import json
import torch
from transformers import AutoProcessor, AutoModelForCausalLM
from pypdf import PdfReader
from docx import Document
from pptx import Presentation

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QFileDialog, 
                             QComboBox, QTextEdit, QProgressBar, QMessageBox,
                             QFrame, QGroupBox, QLineEdit)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QIcon

# --- 1. Core Logic (Unchanged) ---
def read_file_content(file_path):
    if not os.path.exists(file_path):
        return None
    
    ext = file_path.split('.')[-1].lower()
    text = ""
    try:
        if ext == 'pdf':
            reader = PdfReader(file_path)
            for page in reader.pages:
                text += page.extract_text() + "\n"
        elif ext in ['docx', 'doc']:
            doc = Document(file_path)
            text = "\n".join([para.text for para in doc.paragraphs])
        elif ext == 'pptx':
            prs = Presentation(file_path)
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text"):
                        text += shape.text + "\n"
        elif ext in ['txt', 'md']:
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
        else:
            return None
    except Exception:
        return None
    
    clean_text = re.sub(r'\s+', ' ', text).strip()
    return clean_text[:5000]

def perform_summarization(file_path, tone="Normal"):
    content = read_file_content(file_path)
    if content is None:
        return json.dumps({"status": "error", "message": "File not found/unsupported", "file_path": file_path}, indent=4)

    word_count = len(content.split())
    summary_intro = "Here is a summary:"
    if tone.lower() == "casual": summary_intro = "Hey! Here's the gist:"
    elif tone.lower() == "formal": summary_intro = "The core information follows:"
    elif tone.lower() == "concise": summary_intro = "Key points:"

    response_data = {
        "status": "success",
        "file_path": file_path,
        "tone": tone,
        "meta": {"word_count": word_count},
        "summary": {
            "intro": summary_intro,
            "preview_text": content[:500] + "..." 
        }
    }
    return json.dumps(response_data, indent=4)

def parse_and_execute(output_text):
    match = re.search(r"<start_function_call>call:(.*?)\{(.*?)\}<end_function_call>", output_text)
    if match:
        func_name = match.group(1)
        args_str = match.group(2)
        args = {}
        string_params = re.findall(r'(\w+):<escape>(.*?)<escape>', args_str)
        for k, v in string_params: args[k] = v
        simple_params = re.findall(r'(\w+):([^<,]+)', args_str)
        for k, v in simple_params: 
            if k not in args: args[k] = v

        if func_name == "summarize_document":
            return perform_summarization(args.get("file_path"), args.get("tone", "Normal"))
    return json.dumps({"status": "error", "message": "No function call detected."}, indent=4)

# --- 2. Background Worker ---
class AIWorker(QObject):
    finished = pyqtSignal(str)
    progress = pyqtSignal(str)
    model_loaded = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.processor = None
        self.model = None
        self.tools_schema = [
            {
                "type": "function",
                "function": {
                    "name": "summarize_document",
                    "description": "Summarizes a document file with a specific tone.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_path": {"type": "string"},
                            "tone": {"type": "string", "enum": ["Casual", "Formal", "Normal", "Concise"]},
                        },
                        "required": ["file_path"],
                    },
                },
            }
        ]

    def load_model(self):
        self.progress.emit("Loading FunctionGemma (270M)...")
        try:
            model_id = "google/functiongemma-270m-it"
            self.processor = AutoProcessor.from_pretrained(model_id, device_map="auto")
            self.model = AutoModelForCausalLM.from_pretrained(model_id, device_map="auto", torch_dtype="auto")
            self.progress.emit("Model Ready.")
            self.model_loaded.emit()
        except Exception as e:
            self.progress.emit(f"Error loading model: {str(e)}")

    def run_inference(self, file_path, tone):
        if not self.model or not self.processor:
            self.finished.emit("Error: Model not loaded.")
            return

        self.progress.emit("Analyzing document...")
        
        user_prompt = f"Summarize the file at {file_path} with a {tone} tone."
        messages = [
            {"role": "developer", "content": "You are a model that can do function calling."},
            {"role": "user", "content": user_prompt}
        ]

        try:
            inputs = self.processor.apply_chat_template(messages, tools=self.tools_schema, add_generation_prompt=True, return_dict=True, return_tensors="pt")
            inputs = {k: v.to(self.model.device) for k, v in inputs.items()}

            out = self.model.generate(**inputs, max_new_tokens=128)
            raw_output = self.processor.decode(out[0][len(inputs["input_ids"][0]):], skip_special_tokens=False)
            
            final_json = parse_and_execute(raw_output)
            self.finished.emit(final_json)
            
        except Exception as e:
            self.finished.emit(json.dumps({"status": "critical_error", "message": str(e)}, indent=4))

# --- 3. The Modern Main Window ---
class MainWindow(QMainWindow):
    # Signal to trigger worker
    run_worker_signal = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("FunctionGemma Summarizer")
        self.resize(900, 700)
        self.selected_file = None
        self.apply_styles()

        # Central Widget & Layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # --- Top Header ---
        header = QLabel("AI Document Summarizer")
        header.setObjectName("header")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(header)

        # --- Configuration Box ---
        config_group = QGroupBox("Configuration")
        config_layout = QVBoxLayout()

        # File Selection Row
        file_layout = QHBoxLayout()
        
        # FIX: Using QLineEdit instead of QLabel for better visibility and overflow handling
        self.file_input = QLineEdit()
        self.file_input.setPlaceholderText("No file selected...")
        self.file_input.setReadOnly(True)
        
        btn_browse = QPushButton("Browse")
        btn_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_browse.setFixedWidth(100)
        btn_browse.clicked.connect(self.browse_file)
        
        file_layout.addWidget(self.file_input)
        file_layout.addWidget(btn_browse)
        config_layout.addLayout(file_layout)

        # Tone Selection Row
        tone_layout = QHBoxLayout()
        tone_label = QLabel("Summary Tone:")
        tone_label.setFixedWidth(100)
        
        self.tone_combo = QComboBox()
        self.tone_combo.addItems(["Normal", "Casual", "Formal", "Concise"])
        self.tone_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        
        tone_layout.addWidget(tone_label)
        tone_layout.addWidget(self.tone_combo)
        config_layout.addLayout(tone_layout)

        config_group.setLayout(config_layout)
        main_layout.addWidget(config_group)

        # --- Progress Bar & Status ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0) # Indeterminate mode (loading)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(True) # Visible on start for model loading
        main_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Initializing model...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #AAA;")
        main_layout.addWidget(self.status_label)

        # --- Generate Button ---
        self.btn_run = QPushButton("Generate Summary")
        self.btn_run.setObjectName("action_button")
        self.btn_run.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_run.setEnabled(False) 
        self.btn_run.clicked.connect(self.start_summarization)
        main_layout.addWidget(self.btn_run)

        # --- Output Area ---
        self.output_area = QTextEdit()
        self.output_area.setReadOnly(True)
        self.output_area.setPlaceholderText("Summary JSON will appear here...")
        main_layout.addWidget(self.output_area)

        # --- Threading Setup ---
        self.thread = QThread()
        self.worker = AIWorker()
        self.worker.moveToThread(self.thread)
        
        self.thread.started.connect(self.worker.load_model)
        self.worker.progress.connect(self.update_status)
        self.worker.model_loaded.connect(self.on_model_loaded)
        self.worker.finished.connect(self.display_result)
        self.run_worker_signal.connect(self.worker.run_inference)
        
        self.thread.start()

    def browse_file(self):
        file_filter = "Documents (*.pdf *.docx *.doc *.pptx *.txt *.md)"
        fname, _ = QFileDialog.getOpenFileName(self, "Select Document", "", file_filter)
        if fname:
            self.selected_file = fname
            # Explicitly setting text on the QLineEdit
            self.file_input.setText(fname)
            # Ensure the cursor starts at the end so user sees filename
            self.file_input.setCursorPosition(len(fname))

    def update_status(self, text):
        self.status_label.setText(text)

    def on_model_loaded(self):
        self.btn_run.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText("Model Ready. Select a file to summarize.")

    def start_summarization(self):
        if not self.selected_file:
            QMessageBox.warning(self, "Warning", "Please select a file first.")
            return
        
        self.btn_run.setEnabled(False)
        self.output_area.clear()
        self.progress_bar.setVisible(True)
        self.status_label.setText("Processing...")
        
        self.run_worker_signal.emit(self.selected_file, self.tone_combo.currentText())

    def display_result(self, json_result):
        self.output_area.setText(json_result)
        self.btn_run.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText("Summary Generated.")

    def apply_styles(self):
        # Dark Theme QSS
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2b2b2b;
            }
            QLabel {
                color: #e0e0e0;
                font-size: 14px;
            }
            #header {
                font-size: 24px;
                font-weight: bold;
                color: #ffffff;
                margin-bottom: 10px;
            }
            QGroupBox {
                border: 1px solid #555;
                border-radius: 6px;
                margin-top: 20px;
                font-weight: bold;
                color: #e0e0e0;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QLineEdit {
                padding: 8px;
                border: 1px solid #555;
                border-radius: 4px;
                background-color: #3a3a3a;
                color: #ffffff;
                font-size: 13px;
            }
            QPushButton {
                padding: 8px;
                border-radius: 4px;
                background-color: #444;
                color: white;
                border: 1px solid #555;
            }
            QPushButton:hover {
                background-color: #555;
            }
            QPushButton#action_button {
                background-color: #0078d7;
                font-weight: bold;
                padding: 12px;
                font-size: 15px;
                border: none;
            }
            QPushButton#action_button:hover {
                background-color: #0063b1;
            }
            QPushButton#action_button:disabled {
                background-color: #555;
                color: #aaa;
            }
            QComboBox {
                padding: 6px;
                border: 1px solid #555;
                border-radius: 4px;
                background-color: #3a3a3a;
                color: white;
            }
            QTextEdit {
                background-color: #1e1e1e;
                color: #00ff00; /* Hacker green text */
                font-family: Consolas, monospace;
                border: 1px solid #444;
                border-radius: 4px;
            }
            QProgressBar {
                border: 1px solid #444;
                border-radius: 4px;
                text-align: center;
                height: 6px;
            }
            QProgressBar::chunk {
                background-color: #0078d7;
            }
        """)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
