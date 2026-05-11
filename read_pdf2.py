# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r'E:\Program Files (x86)\QClaw\resources\openclaw\config\skills\pdf\scripts')
import pdfplumber

pdf_path = r'D:\文档文件\26.5.8横三.pdf'
with pdfplumber.open(pdf_path) as pdf:
    print(f'Pages: {len(pdf.pages)}')
    for i, page in enumerate(pdf.pages):
        print(f'\n--- Page {i+1} ---')
        text = page.extract_text()
        if text and text.strip():
            print(text[:3000])
        else:
            # Try extracting tables
            tables = page.extract_tables()
            if tables:
                print('Tables found:', len(tables))
                for t in tables:
                    print(t)
            else:
                print('No text or tables found')
                # Check if it's an image
                images = page.images
                print(f'Images: {len(images)}')