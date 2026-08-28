# Python 3 — bulk-download via files.json (no extra dependencies)
import json, os, time, urllib.request, urllib.error

with open('files.json') as f:
    manifest = json.load(f)

base_url = manifest['base_url']
files    = manifest['files']
os.makedirs('audio', exist_ok=True)

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/124.0.0.0 Safari/537.36'
}

def download(url, dest, retries=6):
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp, open(dest, 'wb') as out:
                out.write(resp.read())
            return True
        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            print(f'  attempt {attempt} failed: {e}')
            time.sleep(2)
    return False

failed = []
for i, filename in enumerate(files, 1):
    dest = os.path.join('audio', filename)
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        continue  # already downloaded
    print(f'[{i}/{len(files)}] {filename}')
    if not download(base_url + filename, dest):
        failed.append(filename)

print(f'Done! {len(files) - len(failed)} files saved to ./audio/')
if failed:
    print(f'{len(failed)} files failed:')
    for fn in failed:
        print('  ', fn)
