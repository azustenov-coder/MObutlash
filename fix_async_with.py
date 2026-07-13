import re

with open("database.py", "r", encoding="utf-8") as f:
    content = f.read()

# Replace `async with db.execute(sql, args) as cursor:`
# with `async with db.cursor() as cursor:\n    await cursor.execute(sql, args)`

def replace_async_with(match):
    args = match.group(1)
    cursor_var = match.group(2)
    # The original indentation is before the `async with`
    # We can just return the new string with an extra indentation for the inner line.
    return f"async with db.cursor() as {cursor_var}:\n        await {cursor_var}.execute({args})"

# We need to catch the exact indentation to indent the await correctly.
def replace_async_with_indent(match):
    indent = match.group(1)
    args = match.group(2)
    cursor_var = match.group(3)
    return f"{indent}async with db.cursor() as {cursor_var}:\n{indent}    await {cursor_var}.execute({args})"

content = re.sub(r"([ \t]*)async with db\.execute\((.*?)\)\s+as\s+([a-zA-Z0-9_]+):", replace_async_with_indent, content, flags=re.DOTALL)

with open("database_pg.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Created database_pg.py with async with fixes")
