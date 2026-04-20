# Multilingual Resume Support

This document explains how multilingual resumes are handled in the Resume AI project.

## Overview

The app can ingest resumes in multiple languages, detect the language, translate non-English text to English, and then run the normal scoring pipeline.

Main implementation: `core/multilingual.py`

## Supported Languages

Current supported labels:

- English
- Hindi
- Marathi
- German
- Russian
- Chinese
- Mixed

## How It Works

### 1. Text Extraction

Resumes are first converted to text in `core/utils.py`:

- PDF: `PyPDF2`
- Image files: `pytesseract` (OCR)

### 2. Language Detection

`detect_resume_language(text)` in `core/multilingual.py` uses script-ratio and marker heuristics:

- Cyrillic dominant -> Russian
- Han script dominant -> Chinese
- Devanagari dominant -> Hindi or Marathi (marker-based)
- Latin script with German markers/umlauts -> German
- Multiple major scripts -> Mixed

Note: The detector is tuned to avoid misclassifying resumes as Mixed when a non-Latin resume includes some English skill tokens.

### 3. Translation

`translate_to_english(text, detected_language)` translates non-English text to English using:

- `deep-translator` (`GoogleTranslator`)

If translation dependency is unavailable or translation fails, the original text is preserved and scoring continues.

### 4. Scoring Pipeline Integration

In `core/views.py` (`upload_resumes`):

1. Extract raw text
2. Call `prepare_text_for_analysis(raw_text)`
3. Store and score using `translated_text`

This means scoring logic receives English text even when the original resume is German/Russian/Hindi/etc.

## German and Russian Resume Support

### Text-based PDFs

German and Russian text-based PDFs are supported out of the box:

- Language detection includes German and Russian.
- Non-English text is translated to English before scoring.

### Scanned/Image Resumes

For scanned resumes, OCR quality depends on installed Tesseract language data.

Current OCR call in `core/utils.py` does not pass explicit language codes (`lang=...`), so behavior depends on your system Tesseract defaults.

Recommended for better German/Russian OCR:

- Install Tesseract language packs for `deu` and `rus`.
- Optionally update OCR call to pass language hints.

## Dependencies

Required Python packages are already listed in `requirements.txt`:

- `deep-translator`
- `pytesseract`
- `PyPDF2`
- `Pillow`

System dependency for OCR:

- Tesseract OCR binary installed on machine

## Troubleshooting

### Non-English resume not translating

- Check internet connectivity (Google translation backend).
- Verify `deep-translator` is installed in the active environment.
- Confirm text extraction is returning readable text.

### Scanned Russian/German resume gives poor text

- Install Tesseract `rus` and `deu` language data.
- Verify OCR is enabled and `tesseract` is available in PATH.

### Resume appears as Mixed

- Mixed is expected when multiple scripts are present in significant proportions.
- If needed, tune script thresholds in `core/multilingual.py`.

## Suggested Validation Tests

Use these sample scenarios:

1. German text PDF -> Detect German -> Translate -> Score generated
2. Russian text PDF -> Detect Russian -> Translate -> Score generated
3. Mixed-script resume (English + Russian) -> Mixed or Russian (depending on ratio)
4. Translation failure simulation -> Original text fallback without crash

## File References

- `core/multilingual.py` - Language detection and translation
- `core/utils.py` - PDF/OCR text extraction
- `core/views.py` - Upload pipeline integration
- `requirements.txt` - Python dependencies
