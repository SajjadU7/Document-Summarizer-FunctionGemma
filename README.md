# Document-Summarizer-FunctionGemma

# 📄 AI Document Summarizer with FunctionGemma

This project is an AI-powered tool that bridges natural language commands with file processing operations. It uses **Google's FunctionGemma** (a specialized 270M parameter model) to translate user requests (e.g., *"Give me a casual summary of this PDF"*) into structured code execution.

The tool supports multiple file formats, customizable output tones, and returns data in a clean, parsed **JSON format**.

## 🚀 Features

* **Natural Language Control:** No need to write code or complex CLI args. Just ask the AI to do it.
* **Multi-Format Support:** Reads text from:
* PDF (`.pdf`)
* Word (`.docx`, `.doc`)
* PowerPoint (`.pptx`)
* Text/Markdown (`.txt`, `.md`)


* **Tone Customization:** Supports four distinct summary styles:
* `Normal` (Default)
* `Casual`
* `Formal`
* `Concise`


* **Structured JSON Output:** Returns results in a machine-readable JSON format, perfect for API integrations or web frontends.
* **Efficient:** Uses the lightweight `functiongemma-270m-it` model, optimized for laptop/local usage.

## 🛠️ Architecture

1. **User Input:** "Can you summarize report.pdf casually?"
2. **FunctionGemma:** Analyzes intent and outputs a structured function call: `summarize_document(file_path="report.pdf", tone="Casual")`.
3. **Python Logic:** catche the call, reads the file content, cleans whitespace, and generates the summary.
4. **Output:** Returns a JSON object with metadata and the summary.

## 📦 Installation

### 1. Prerequisites

* Python 3.8+
* A Hugging Face account (to access the model).

### 2. Install Dependencies

Install the required libraries for the model and file handling:

```bash
pip install torch transformers huggingface_hub pypdf python-docx python-pptx

```

### 3. Model Access

FunctionGemma is a gated model. You must accept the license on Hugging Face before using it.

1. Go to [google/functiongemma-270m-it](https://huggingface.co/google/functiongemma-270m-it) and click **"Acknowledge License"**.
2. Create an access token in your Hugging Face settings.
3. Login via your terminal:

```bash
huggingface-cli login
# Paste your token when prompted

```

## 💻 Usage

Run the script from your terminal. You can provide the prompt as an argument or run it interactively.

### Method 1: Command Line Argument

```bash
python summarizer_app.py "I need a concise summary of annual_report.pdf"

```

### Method 2: Interactive Mode

Simply run the script, and it will prompt you for input:

```bash
python summarizer_app.py

```

**Input:** `Can you read notes.txt and give me a casual summary?`

## 📂 Output Example

The tool outputs valid JSON. Example response:

```json
{
    "status": "success",
    "file_path": "project_notes.txt",
    "tone": "Casual",
    "meta": {
        "word_count": 450,
        "char_count": 2800
    },
    "summary": {
        "intro": "Hey! So here's the gist of what's in the file:",
        "preview_text": "The project kick-off went well. We decided to stick to the React framework for the frontend..."
    }
}

```

## 🧩 Project Structure

```
.
├── summarizer_app.py    # Main application logic
├── requirements.txt     # (Optional) List of dependencies
├── README.md            # This file
└── test_files/          # Folder for your PDFs, Docs to test

```

## ⚠️ Limitations & Future Improvements

* **Summarization Logic:** Currently, the script extracts text and provides a heuristic preview. To generate a full abstractive summary (AI writing new sentences), you should integrate a generation model (like Gemma 2B or Gemini API) inside the `perform_summarization` function.
* **File Images:** This tool currently extracts text only; it does not perform OCR on images within PDFs.

## 📄 License

This project uses the `google/functiongemma-270m-it` model. Please adhere to the [Gemma Terms of Use](https://ai.google.dev/gemma/terms).
