# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r'E:\Program Files (x86)\QClaw\resources\openclaw\config\skills\pdf\scripts')
from pypdf import PdfReader

pdf_path = r'D:\文档文件\26.5.8横三.pdf'
reader = PdfReader(pdf_path)

# Get metadata
print('Metadata:')
meta = reader.metadata
if meta:
    for key in ['/Title', '/Author', '/Subject', '/Creator', '/Producer', '/CreationDate', '/ModDate']:
        try:
            val = meta.get(key)
            if val:
                print(f'{key}: {val}')
        except:
            pass

print(f'\nTotal pages: {len(reader.pages)}')

# Try extracting text from page 0
page = reader.pages[0]
print('\n--- Trying different extraction methods ---')

# Method 1: Basic extract
text1 = page.extract_text()
print(f'Basic extract length: {len(text1) if text1 else 0}')
print(f'First 500 chars: {text1[:500] if text1 else "None"}')

# Method 2: Check if there are images
print(f'\nImages on page: {len(page.images)}')

# Method 3: Check /Contents
if '/Contents' in page:
    print('Has Contents')