import re

file_path = 'handlers/assembler.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace Markdown with HTML parse_mode
content = content.replace('parse_mode="Markdown"', 'parse_mode="HTML"')

# Replace **bold** with <b>bold</b>
content = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', content)

# Replace `code` with <code>code</code>
content = re.sub(r'`(.*?)`', r'<code>\1</code>', content)

# Replace *(text)* or *text* with <i>text</i>.
# We will just replace *(...)* manually since it's the only one used for italic in assembler.py.
content = content.replace("*(Бугун топширилган заявкалар мавжуд эмас)*", "<i>(Бугун топширилган заявкалар мавжуд эмас)</i>")

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Regex replacements done successfully!")
