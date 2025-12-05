import ast
import sys

class PresenceConditionExtractor():
    def __init__(self):
        self.line_no = 0

    def print_line(self, line_no, stmt, stmt_type):
        while line_no > self.line_no + 1:
            self.line_no += 1
            print(f"{self.line_no:5d}:")
        print(f"{line_no:5d}: {stmt:60s} [{stmt_type}]")
        self.line_no += 1

    def elif_handling(self, node):
        while len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
            node = node.orelse[0]
            self.print_line(node.lineno, f"if {ast.unparse(node.test)}", "elif")
            for stmt in node.body:
                self.process_node(stmt)
        return node
        
    def expr_handling(self, node):
        self.print_line(node.lineno, ast.unparse(node), "expr")

    def else_handling(self, node):
        if len(node) != 0:
            self.print_line(node[0].lineno - 1, "else", "else")
        for stmt in node:
            self.process_node(stmt)

    def if_handling(self, node):
        self.print_line(node.lineno, f"if {ast.unparse(node.test)}", "if")
        for stmt in node.body:
            self.process_node(stmt)
        # process "elif" block if there exists
        node = self.elif_handling(node)
        # process "else" block if there exists
        self.else_handling(node.orelse)

    def while_handling(self, node):
        self.print_line(node.lineno, f"while {ast.unparse(node.test)}", "while")
        for stmt in node.body:
            self.process_node(stmt)
        # process "else" block if there exists
        self.else_handling(node.orelse)

    def for_handling(self, node):
        for_cond = ast.unparse(node).splitlines()[0]
        self.print_line(node.lineno, for_cond, "for")
        for stmt in node.body:
            self.process_node(stmt)
        # process "else" block if there exists
        self.else_handling(node.orelse)

    def function_handling(self, node):
        func = ast.unparse(node).splitlines()[0]
        self.print_line(node.lineno, func, "function")
        for stmt in node.body:
            self.process_node(stmt)

    def class_handling(self, node):
        class_node = ast.unparse(node).splitlines()[0]
        self.print_line(node.lineno, class_node, "class")
        for stmt in node.body:
            self.process_node(stmt)

    def finally_handling(self, node):
        if len(node) != 0:
            self.print_line(node[0].lineno - 1, "finally", "finally")
        for stmt in node:
            self.process_node(stmt)

    def except_handling(self, node):
        for handler in node:
            etype = ast.unparse(handler.type) if handler.type else "Any"
            if handler.name is not None:
                self.print_line(handler.lineno, f"except {etype} as {handler.name}:", "except")
            else:
                self.print_line(handler.lineno, f"except {etype}:", "except")
            for stmt in handler.body:
                self.process_node(stmt)

    def try_handling(self, node):
        self.print_line(node.lineno, "try", "try")
        for stmt in node.body:
            self.process_node(stmt)
        self.except_handling(node.handlers)
        self.else_handling(node.orelse)
        self.finally_handling(node.finalbody)

    def process_node(self, node):
        if isinstance(node, ast.Try):
            self.try_handling(node)
        elif isinstance(node, ast.ClassDef):
            self.class_handling(node)
        elif isinstance(node, ast.FunctionDef):
            self.function_handling(node)
        elif isinstance(node, ast.If):
            self.if_handling(node)
        elif isinstance(node, ast.While):
            self.while_handling(node)
        elif isinstance(node, ast.For):
            self.for_handling(node)
        else:
            self.expr_handling(node)

def extract_presence_conditions(code):
    tree = ast.parse(code)
    pc = PresenceConditionExtractor()
    for node in tree.body:
        pc.process_node(node)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 presence_conditions.py <file.py>")
        sys.exit(1)

    with open(sys.argv[1], "r") as f:
        code = f.read()

    extract_presence_conditions(code)
