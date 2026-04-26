"""Download Equalizer APO from SourceForge with proper session handling."""
import urllib.request
import http.cookiejar
import os
import time

outpath = os.path.join(os.environ['TEMP'], 'EqualizerAPO-x64-1.4.2.exe')
if os.path.exists(outpath):
    os.remove(outpath)

# Create a cookie jar to handle SourceForge session cookies
cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(cj),
    urllib.request.HTTPRedirectHandler()
)
opener.addheaders = [
    ('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'),
    ('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'),
    ('Accept-Language', 'en-US,en;q=0.5'),
]

# Step 1: Visit the project page to get session cookies
print('Step 1: Getting session cookies from SourceForge...')
try:
    resp1 = opener.open('https://sourceforge.net/projects/equalizerapo/', timeout=30)
    html = resp1.read().decode('utf-8', errors='replace')
    print(f'  Got page: {len(html)} bytes, cookies: {len(list(cj))}')
except Exception as e:
    print(f'  Warning: {e}')

# Step 2: Get the redirect URL from the download page
print('Step 2: Following download redirect...')
try:
    req = urllib.request.Request('https://sourceforge.net/projects/equalizerapo/files/latest/download')
    resp2 = opener.open(req, timeout=30)
    final_url = resp2.url
    print(f'  Final URL: {final_url}')
    cl = resp2.headers.get('Content-Length', 'unknown')
    ct = resp2.headers.get('Content-Type', 'unknown')
    print(f'  Content-Length: {cl}, Content-Type: {ct}')
    
    # Check if we got the actual file (should be ~11MB, content-type: application/octet-stream or application/x-msdownload)
    if cl and int(cl) > 1000000:
        print('Step 3: Downloading actual file...')
        with open(outpath, 'wb') as f:
            downloaded = 0
            total = int(cl)
            while True:
                chunk = resp2.read(65536)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                pct = int(downloaded / total * 100)
                if pct % 10 == 0:
                    print(f'  {pct}% ({downloaded/1024/1024:.1f} MB)')
        
        size = os.path.getsize(outpath)
        print(f'Done: {size/1024/1024:.2f} MB -> {outpath}')
    else:
        # We got HTML, need to extract the actual download link
        body = resp2.read().decode('utf-8', errors='replace')
        # Look for direct download links
        import re
        links = re.findall(r'href="(https://[^"]*\.exe[^"]*)"', body)
        print(f'  Found {len(links)} exe links in HTML')
        for l in links[:5]:
            print(f'  Link: {l}')
        
        if links:
            print('Step 3: Downloading from extracted link...')
            dl_url = links[0]
            resp3 = opener.open(dl_url, timeout=120)
            with open(outpath, 'wb') as f:
                downloaded = 0
                while True:
                    chunk = resp3.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
            
            size = os.path.getsize(outpath)
            print(f'Done: {size/1024/1024:.2f} MB -> {outpath}')
        else:
            print('Could not find download link. Trying direct CDN URL...')
            # Last resort: try the CDN URL we already know
            cdn_url = 'https://zenlayer.dl.sourceforge.net/project/equalizerapo/1.4.2/EqualizerAPO-x64-1.4.2.exe'
            resp3 = opener.open(cdn_url, timeout=120)
            with open(outpath, 'wb') as f:
                downloaded = 0
                while True:
                    chunk = resp3.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
            size = os.path.getsize(outpath)
            print(f'Done: {size/1024/1024:.2f} MB -> {outpath}')
            
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()
