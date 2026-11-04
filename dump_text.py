import json

with open('data/forum_topics_page0.json', 'r', encoding='utf-8') as f:
    topics = json.load(f)

with open('data/all_29_topics_detailed.txt', 'w', encoding='utf-8') as out:
    for idx, t in enumerate(topics):
        out.write(f"\n{'='*80}\n")
        out.write(f"TOPIC #{idx+1} [ID: {t['id']}] : {t['title']}\n")
        out.write(f"Author: {t['author']} | Created: {t['created_at']} | Bumped: {t['bumped_at']} | Posts: {t['posts_count']}\n")
        out.write(f"{'-'*80}\n")
        out.write(f"QUESTION (Post 1):\n{t['question_text']}\n")
        out.write(f"{'-'*80}\n")
        out.write(f"REPLIES ({len(t['replies'])}):\n")
        for r_idx, r in enumerate(t['replies']):
            out.write(f"\n--- Reply #{r_idx+1} by {r['author']} at {r['created_at']} ---\n")
            out.write(r['text'] + "\n")
        out.write(f"{'='*80}\n")

print("Saved detailed dump to data/all_29_topics_detailed.txt")
