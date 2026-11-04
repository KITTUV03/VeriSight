import urllib.request
import json
import time
import os
import re
from html import unescape

def clean_html(raw_html):
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return unescape(cleantext).strip()

def download_page(page_num):
    os.makedirs('data/forum_dump', exist_ok=True)
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    url = f'https://verificationacademy.com/forums/c/uvm/5.json?page={page_num}'
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        cat_data = json.loads(resp.read().decode('utf-8'))
        
    topics = cat_data.get('topic_list', {}).get('topics', [])
    print(f"Total topics retrieved on Page {page_num}: {len(topics)}")
    
    topics_list = []
    for idx, t in enumerate(topics):
        t_id = t['id']
        title = t['title']
        if t_id == 20:
            print(f"Skipping pinned category info: {title}")
            continue
            
        json_path = f"data/forum_dump/topic_{t_id}.json"
        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                topic_record = json.load(f)
            topics_list.append(topic_record)
            continue

        print(f"Fetching [{idx+1}/{len(topics)}] ID: {t_id} - {title}")
        t_url = f"https://verificationacademy.com/forums/t/{t_id}.json"
        try:
            t_req = urllib.request.Request(t_url, headers=headers)
            with urllib.request.urlopen(t_req, timeout=15) as t_resp:
                t_detail = json.loads(t_resp.read().decode('utf-8'))
                
            posts = t_detail.get('post_stream', {}).get('posts', [])
            first_post = posts[0] if posts else {}
            replies = posts[1:] if len(posts) > 1 else []
            
            topic_record = {
                'id': t_id,
                'title': title,
                'slug': t.get('slug'),
                'created_at': t.get('created_at'),
                'bumped_at': t.get('bumped_at'),
                'posts_count': t.get('posts_count'),
                'question_raw': first_post.get('cooked', ''),
                'question_text': clean_html(first_post.get('cooked', '')),
                'author': first_post.get('username', ''),
                'replies': [
                    {
                        'id': r.get('id'),
                        'author': r.get('username'),
                        'raw': r.get('cooked', ''),
                        'text': clean_html(r.get('cooked', '')),
                        'created_at': r.get('created_at')
                    }
                    for r in replies
                ]
            }
            topics_list.append(topic_record)
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(topic_record, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"Error fetching topic {t_id}: {e}")
            
        time.sleep(0.2)
        
    with open(f'data/forum_topics_page{page_num}.json', 'w', encoding='utf-8') as f:
        json.dump(topics_list, f, indent=2, ensure_ascii=False)
        
    print(f"Successfully saved {len(topics_list)} topics to data/forum_topics_page{page_num}.json")

if __name__ == '__main__':
    download_page(1)
