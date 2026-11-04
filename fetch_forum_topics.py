import urllib.request
import json
import time

def main():
    url = 'https://verificationacademy.com/forums/c/uvm/5.json'
    headers = {'User-Agent': 'Mozilla/5.0'}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode('utf-8'))
    
    tl = data.get('topic_list', {})
    topics = tl.get('topics', [])
    print(f"Page 0 topics count: {len(topics)}")
    print(f"more_topics_url: {tl.get('more_topics_url')}")
    
    for i, t in enumerate(topics):
        print(f"[{i+1}] ID: {t.get('id')} - {t.get('title')} (posts: {t.get('posts_count')}, created: {t.get('created_at')})")

if __name__ == '__main__':
    main()
