# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r'E:\Program Files (x86)\QClaw\resources\openclaw\config\skills\pdf\scripts')
from pypdf import PdfReader

pdf_path = r'D:\文档文件\26.5.8横三.pdf'
reader = PdfReader(pdf_path)
page = reader.pages[0]
text = page.extract_text()

# The text extraction is garbled - let's try to detect the encoding
# by looking at the raw bytes

# Try GBK decode
try:
    text_gbk = text.encode('latin1').decode('gbk')
    print('=== GBK decoded ===')
    print(text_gbk[:500])
except Exception as e:
    print(f'GBK failed: {e}')

print('\n--- Trying GB2312 ---')
try:
    text_gb2312 = text.encode('latin1').decode('gb2312', errors='replace')
    print(text_gb2312[:500])
except Exception as e:
    print(f'GB2312 failed: {e}')
    
print('\n--- Trying Big5 ---')
try:
    text_big5 = text.encode('latin1').decode('big5', errors='replace')
    print(text_big5[:500])
except Exception as e:
    print(f'Big5 failed: {e}')

print('\n--- Trying cp936 ---')
try:
    text_cp936 = text.encode('latin1').decode('cp936', errors='replace')
    print(text_cp936[:500])
except Exception as e:
    print(f'cp936 failed: {e}')