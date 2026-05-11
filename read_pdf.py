# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r'E:\Program Files (x86)\QClaw\resources\openclaw\config\skills\pdf\scripts')
from pypdf import PdfReader

pdf_path = r'D:\文档文件\26.5.8横三.pdf'
reader = PdfReader(pdf_path)
print(f'Pages: {len(reader.pages)}')
for i, page in enumerate(reader.pages):
    print(f'\n--- Page {i+1} ---')
    text = page.extract_text()
    if text:
        print(text)
    else:
        print('No text extracted')