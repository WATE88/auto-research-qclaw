import urllib.request
import os

url = 'https://zenlayer.dl.sourceforge.net/project/equalizerapo/1.4.2/EqualizerAPO-x64-1.4.2.exe'
outpath = os.path.join(os.environ['TEMP'], 'EqualizerAPO-x64-1.4.2.exe')

opener = urllib.request.build_opener()
opener.addheaders = [
    ('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'),
    ('Accept', '*/*'),
    ('Referer', 'https://sourceforge.net/')
]

print('Downloading from CDN...')
try:
    resp = opener.open(url, timeout=120)
    cl = resp.headers.get('Content-Length', 'unknown')
    ct = resp.headers.get('Content-Type', 'unknown')
    print(f'Content-Length: {cl}')
    print(f'Content-Type: {ct}')

    with open(outpath, 'wb') as f:
        downloaded = 0
        while True:
            chunk = resp.read(65536)
            if not chunk:
                break
            f.write(chunk)
            downloaded += len(chunk)
            if downloaded % (2 * 1024 * 1024) < 65536:
                print(f'  {downloaded/1024/1024:.1f} MB...')

    size = os.path.getsize(outpath)
    print(f'Done: {size/1024/1024:.2f} MB -> {outpath}')
except Exception as e:
    print(f'Error: {e}')
