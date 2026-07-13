import ast
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

import astor # Wait, astor is not installed usually. Let's just use simple regex safely.
