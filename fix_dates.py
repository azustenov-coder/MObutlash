import os, glob, re

for file in glob.glob('handlers/*.py') + ['database.py']:
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace anything like req['created_at'][:16] to str(req['created_at'])[:16]
    content = re.sub(r"(r|req|u|orig|item)\['created_at'\]\[:(\d+)\]", r"str(\1['created_at'])[:\2]", content)
    
    with open(file, 'w', encoding='utf-8') as f:
        f.write(content)
print("Done")
