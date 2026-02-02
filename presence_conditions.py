import ast
import sys

class PresenceConditionVisitor(ast.NodeVisitor):
    def __init__(self, supported_features):
        self.conditions = {}
        # 1. Change evaluation output from "True" to "1"
        self.path_condition = "1"
        self.env = {}
        self.supported_features = supported_features

    def record(self, node, alt_cond=None):
        if hasattr(node, "lineno"):
            cond = alt_cond if alt_cond else self.path_condition
            self.conditions[node.lineno] = cond

    def combine_logic(self, base, new):
        if new == "" or new == "1" or new == "!()":
            return base
        if base == "1":
            return new
        return f"({base}) && ({new})"

    def expr_to_str(self, expr, target_id=None):
        if expr is None:
            return ""

        if isinstance(expr, ast.Name):
            if expr.id in self.env:
                return self.env[expr.id]
            if expr.id in self.supported_features:
                return expr.id
            if target_id and expr.id == target_id:
                return expr.id
            return ""

        if isinstance(expr, ast.Attribute):
            if expr.attr in self.supported_features or (target_id and expr.attr == target_id):
                return expr.attr
            val_str = self.expr_to_str(expr.value, target_id=target_id)
            if not val_str:
                return expr.attr
            return f"{val_str}.{expr.attr}"

        if isinstance(expr, ast.Constant):
            return str(expr.value)

        if isinstance(expr, ast.BoolOp):
            op = " || " if isinstance(expr.op, ast.Or) else " && "
            valid_parts = [self.expr_to_str(v) for v in expr.values]
            # 1. Check for "1" instead of "True"
            valid_parts = [v for v in valid_parts if v and v != "1"]
            if valid_parts:
                return f"({op.join(valid_parts)})"
            return "1"

        if isinstance(expr, ast.UnaryOp) and isinstance(expr.op, ast.Not):
            operand = self.expr_to_str(expr.operand)
            if not operand or operand == "1":
                return "1"
            return f"!({operand})"

        if isinstance(expr, ast.Compare):
            left = self.expr_to_str(expr.left)
            ops = {ast.Eq: "==", ast.NotEq: "!=", ast.Lt: "<", ast.Gt: ">"}
            op_sym = ops.get(type(expr.ops[0]), "?")
            right = self.expr_to_str(expr.comparators[0])
            if not left or not right:
                return ""
            return f"({left} {op_sym} {right})"

        if isinstance(expr, ast.Call):
            if isinstance(expr.func, ast.Name):
                if expr.func.id == "any" and isinstance(expr.args[0], ast.List):
                    elts = [self.expr_to_str(e, target_id=target_id) for e in expr.args[0].elts]
                    elts = [e for e in elts if e]
                    return f"({' || '.join(elts)})" if elts else ""
                
                if expr.func.id == "range" and target_id:
                    stop = self.expr_to_str(expr.args[0], target_id=target_id)
                    if stop:
                        return f"{target_id} < {stop}"
            return ""
        return ""

    def visit_FunctionDef(self, node):
        self.record(node)
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        self.record(node)
        self.generic_visit(node)

    def visit_Assign(self, node):
        self.record(node)
        if isinstance(node.targets[0], ast.Name):
            var_name = node.targets[0].id
            self.env[var_name] = self.expr_to_str(node.value)
        self.generic_visit(node)

    def visit_If(self, node):
        self.record(node)
        cond_str = self.expr_to_str(node.test)
        old_path = self.path_condition
        self.path_condition = self.combine_logic(old_path, cond_str)
        for stmt in node.body: self.visit(stmt)
        if node.orelse:
            negated_cond = f"!({cond_str})" if cond_str else ""
            self.path_condition = self.combine_logic(old_path, negated_cond)
            if not isinstance(node.orelse[0], ast.If):
                self.conditions[node.orelse[0].lineno - 1] = self.path_condition
            for stmt in node.orelse: self.visit(stmt)
        self.path_condition = old_path

    def visit_Try(self, node):
        self.record(node)
        old_path = self.path_condition
        accumulated_exceptions = []
        for stmt in node.body: self.visit(stmt)
        for handler in node.handlers:
            exc_name = "BaseException" if handler.type is None else self.expr_to_str(handler.type)
            not_prev = "".join([f"!({e}) && " for e in accumulated_exceptions])
            handler_cond = f"{not_prev}({exc_name})"
            if old_path != "1":
                handler_cond = f"({old_path}) && {handler_cond}"
            self.conditions[handler.lineno] = handler_cond
            self.path_condition = handler_cond
            for stmt in handler.body: self.visit(stmt)
            accumulated_exceptions.append(exc_name)
        if node.orelse:
            not_all_exc = "".join([f"!({e}) && " for e in accumulated_exceptions]).strip(" && ")
            else_cond = self.combine_logic(old_path, not_all_exc)
            self.conditions[node.orelse[0].lineno - 1] = else_cond
            self.path_condition = else_cond
            for stmt in node.orelse: self.visit(stmt)
        self.path_condition = old_path
        if node.finalbody:
            self.conditions[node.finalbody[0].lineno - 1] = old_path
            for stmt in node.finalbody: self.visit(stmt)

    def visit_For(self, node):
        target_id = node.target.id if isinstance(node.target, ast.Name) else (node.target.attr if isinstance(node.target, ast.Attribute) else None)
        cond_str = self.expr_to_str(node.iter, target_id=target_id)
        old_path = self.path_condition
        self.path_condition = self.combine_logic(old_path, cond_str)
        self.record(node) 
        for stmt in node.body: self.visit(stmt)
        if node.orelse:
            negated = f"!({cond_str})" if cond_str else ""
            self.path_condition = self.combine_logic(old_path, negated)
            self.conditions[node.orelse[0].lineno - 1] = self.path_condition
            for stmt in node.orelse: self.visit(stmt)
        self.path_condition = old_path

    def visit_While(self, node):
        self.record(node)
        cond_str = self.expr_to_str(node.test)
        old_path = self.path_condition
        self.path_condition = self.combine_logic(old_path, cond_str)
        for stmt in node.body: self.visit(stmt)
        if node.orelse:
            negated = f"!({cond_str})" if cond_str else ""
            self.path_condition = self.combine_logic(old_path, negated)
            self.conditions[node.orelse[0].lineno - 1] = self.path_condition
            for stmt in node.orelse: self.visit(stmt)
        self.path_condition = old_path

    def visit_Return(self, node): self.record(node)
    def visit_Raise(self, node): self.record(node)
    def visit_Expr(self, node): self.record(node)
    def visit_AugAssign(self, node): self.record(node)

def extract_presence_conditions(code, supported_features):
    tree = ast.parse(code)
    visitor = PresenceConditionVisitor(supported_features)
    visitor.visit(tree)
    
    # 2 & 3. Remove "Line XX" and handle blank lines/comments
    lines = code.splitlines()
    for i in range(1, len(lines) + 1):
        # If the line was visited, print its condition; otherwise, it's blank/comment so print "1"
        print(visitor.conditions.get(i, "1"))


if __name__ == "__main__":
    supported_features = [
        "ENABLE_AEB", "TEST_MODE", "ENABLE_X", "ENABLE_Y", "ENABLE_Z", "ENABLE_P", 
        "DEBUG", "VERBOSE", "getFrames", "getPose", "autoFocus", "Exception", 
        "camera_type", "ZeroDivisionError", "allied"
    ]

    if len(sys.argv) > 1:
        with open(sys.argv[1], "r") as f:
            code = f.read()
        extract_presence_conditions(code, supported_features)

