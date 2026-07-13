import ast
import os
import re

with open("database.py", "r", encoding="utf-8") as f:
    source = f.read()

class SQLStringReplacer(ast.NodeTransformer):
    def visit_Call(self, node):
        self.generic_visit(node)
        if isinstance(node.func, ast.Attribute) and node.func.attr == 'execute':
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                sql = node.args[0].value
                # Replace ? with %s
                new_sql = sql.replace('?', '%s')
                node.args[0].value = new_sql
        return node

tree = ast.parse(source)
replacer = SQLStringReplacer()
new_tree = replacer.visit(tree)
ast.fix_missing_locations(new_tree)

new_source = ast.unparse(new_tree)

# Post-processing imports and connection
new_source = new_source.replace("import aiosqlite", "import psycopg\nfrom psycopg.rows import dict_row\nimport os")
new_source = new_source.replace("aiosqlite.Error", "psycopg.Error")
new_source = re.sub(
    r"async with aiosqlite\.connect\(DB_PATH\) as db:\s*db\.row_factory = aiosqlite\.Row",
    r"async with await psycopg.AsyncConnection.connect(os.environ.get('DATABASE_URL'), row_factory=dict_row) as db:",
    new_source
)
new_source = re.sub(
    r"async with aiosqlite\.connect\(DB_PATH\) as db:",
    r"async with await psycopg.AsyncConnection.connect(os.environ.get('DATABASE_URL'), row_factory=dict_row) as db:",
    new_source
)

# Auto increment replacements
new_source = new_source.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
new_source = new_source.replace("integer primary key autoincrement", "SERIAL PRIMARY KEY")
new_source = new_source.replace("DATETIME DEFAULT CURRENT_TIMESTAMP", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

with open("database_pg.py", "w", encoding="utf-8") as f:
    f.write(new_source)

print("Created database_pg.py using ast.unparse")
