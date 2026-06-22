import ast
import sys
import re

class PresenceConditionVisitor(ast.NodeVisitor):
    def __init__(self, supported_features, code):
        self.conditions = {}
        self.path_condition = "1"
        self.supported_features = supported_features
        self.source_lines = code.splitlines()

    def record(self, node, alt_cond=None):
        if hasattr(node, "lineno"):
            start = node.lineno
            end = getattr(node, "end_lineno", start)
            cond = alt_cond if alt_cond else self.path_condition
            for line in range(start, end + 1):
                self.conditions[line] = cond

    def finalize(self, total_lines):
        last_known_cond = "1"
        for line in range(1, total_lines + 1):
            if line in self.conditions:
                last_known_cond = self.conditions[line]
            else:
                self.conditions[line] = last_known_cond

    def combine_logic(self, base, new):
        if not new or new in ("1", "!()", "!1", "0"): 
            return base
        if not base or base == "1": 
            return new
        # Only wrap 'base' or 'new' if they contain an OR operator 
        # to respect Boolean precedence (AND > OR)
        # left = f"({base})" if " || " in base else base
        # right = f"({new})" if " || " in new else new
        # Respect Boolean precedence (AND > OR)
        # If a sub-expression contains an unparenthesized OR, wrap it
        left = f"({base})" if " || " in base and not (base.startswith("(") and base.endswith(")")) else base
        right = f"({new})" if " || " in new and not (new.startswith("(") and new.endswith(")")) else new
        return f"{left} && {right}"

    def expr_to_str(self, expr, target_id=None):
        if expr is None: 
            return ""

        # Base Cases (No parens needed)
        if isinstance(expr, ast.Name):
            if expr.id in self.supported_features:
                return expr.id
            if target_id and expr.id == target_id:
                return expr.id
            else:
                return ""
        
        if isinstance(expr, ast.Attribute):
            if expr.attr in self.supported_features or (target_id and expr.attr == target_id):
                return expr.attr
            val_str = self.expr_to_str(expr.value, target_id=target_id)
            if val_str:
                return f"{val_str}.{expr.attr}" 
            else:
                return ""

        if isinstance(expr, ast.Constant):
            # If the constant is a boolean, map it to logic digits
            if isinstance(expr.value, bool):
                return "1" if expr.value else "0"
            return str(expr.value)

        # 2. Boolean Logic (Smart Wrapping)
        if isinstance(expr, ast.BoolOp):
            is_or = isinstance(expr.op, ast.Or)
            op_sym = " || " if is_or else " && "
            parts = [v for v in [self.expr_to_str(v) for v in expr.values] if v and v != "1"]
            if not parts: 
                return "1"
            if len(parts) == 1: 
                return parts[0]
            
            # Sub-parts need parens ONLY if we are doing AND over OR children
            processed_parts = []
            for p in parts:
                if not is_or and " || " in p:
                    processed_parts.append(f"({p})")
                else:
                    processed_parts.append(p)
            return op_sym.join(processed_parts)

        if isinstance(expr, ast.UnaryOp) and isinstance(expr.op, ast.Not):
            operand = self.expr_to_str(expr.operand)
            if not operand or operand == "1": 
                 return "1"
            # Wrap only if operand has spaces (meaning it's a compound expression)
            if " " in operand:
                return f"!({operand})"
            else:
                return f"!{operand}"

        # Comparisons (Parens usually safer but optional if simple)

        if isinstance(expr, ast.Compare):
            left = self.expr_to_str(expr.left)
            ops = {
                ast.Eq: "==", 
                ast.NotEq: "!=", 
                ast.Lt: "<", 
                ast.Gt: ">",
                ast.LtE: "<=",  # Added Less Than or Equal
                ast.GtE: ">="   # Added Greater Than or Equal
            }
            op_sym = ops.get(type(expr.ops[0]), "?")
            right = self.expr_to_str(expr.comparators[0])
            if left and right:
                return f"({left} {op_sym} {right})"
            else:
                return ""

        if isinstance(expr, ast.Call):
            if isinstance(expr.func, ast.Name):
                if expr.func.id == "any" and isinstance(expr.args[0], ast.List):
                    elts = [e for e in [self.expr_to_str(x, target_id=target_id) for x in expr.args[0].elts] if e]
                    if elts:
                        return " || ".join(elts)
                    else:
                        return ""
                if expr.func.id == "range" and target_id:
                    stop = self.expr_to_str(expr.args[0], target_id=target_id)
                    if stop:
                        return f"{target_id} < {stop}"
                    else:
                        return ""
        return ""

    def record_node_lines(self, node):
        """Ensures all lines spanning a node are tagged with the active path condition."""
        if hasattr(node, 'lineno'):
            end = node.end_lineno if hasattr(node, 'end_lineno') else node.lineno
            for line in range(node.lineno, end + 1):
                if line not in self.conditions or self.conditions[line] == "1":
                    # Apply the tracked condition to the exact line span
                    self.conditions[line] = self.path_condition

    def visit_ImportFrom(self, node):
        self.record_node_lines(node)  # Explicitly map the path condition first!
        self.record(node)
        self.generic_visit(node)

    def visit_Assign(self, node):
        # Explicitly record line metrics before diving into sub-nodes
        self.record_node_lines(node)
        self.record(node)
        self.generic_visit(node)

    def parse_if_condition(self, node):
        """
        Recursively reduces:
        - 'X == True' / 'X is True' -> 'X'
        - 'X == False' / 'X is False' -> 'not X'
        - 'X is None' -> 'not X'
        - 'X is not None' -> 'X'
        - 'not(not X)' -> 'X'
        - 'X in [A, B]' -> 'X == A or X == B'
        - 'X not in [A, B]' -> 'X != A and X != B'
        """
        # Handle logical combinations like 'and' / 'or'
        if isinstance(node, ast.BoolOp):
            node.values = [self.parse_if_condition(val) for val in node.values]
            return node

        # Handle explicit 'not' operators
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            # Recursively parse the inner expression first
            inner_node = self.parse_if_condition(node.operand)
            
            # Double Negation Optimization: if inner node is already a 'not', they cancel out!
            # e.g., not(not A) -> A
            if isinstance(inner_node, ast.UnaryOp) and isinstance(inner_node.op, ast.Not):
                return inner_node.operand
                
            node.operand = inner_node
            return node

        # Handle comparisons
        if isinstance(node, ast.Compare):
            if len(node.ops) == 1 and len(node.comparators) == 1:
                op = node.ops[0]
                comparator = node.comparators[0]

                # Converts: feature in ["optionA", "optionB"] 
                # Into:     feature == "optionA" or feature == "optionB"
                # and
                # Converts: feature not in ["optionA", "optionB"] 
                # Into:     feature != "optionA" and feature != "optionB"               
                if isinstance(op, (ast.In, ast.NotIn)) and isinstance(comparator, (ast.List, ast.Tuple)):
                    if isinstance(op, ast.In):
                        # X in [A, B]  ->  X == A or X == B
                        inner_ops = [
                            ast.Compare(left=node.left, ops=[ast.Eq()], comparators=[elt])
                            for elt in comparator.elts
                        ]
                        bool_node = ast.BoolOp(op=ast.Or(), values=inner_ops)
                    else:
                        # X not in [A, B]  ->  X != A and X != B
                        inner_ops = [
                            ast.Compare(left=node.left, ops=[ast.NotEq()], comparators=[elt])
                            for elt in comparator.elts
                        ]
                        bool_node = ast.BoolOp(op=ast.And(), values=inner_ops) 
                    return self.parse_if_condition(bool_node)

                if isinstance(comparator, ast.Constant):
                    val = comparator.value
                    
                    # --- Rule Set 1: Evaluate to 'A' (Truthy Outcome) ---
                    # 1. A == True
                    # 2. A is True
                    # 3. A != False
                    # 4. A is not False
                    if (isinstance(op, (ast.Eq, ast.Is)) and val is True) or \
                       (isinstance(op, (ast.NotEq, ast.IsNot)) and val is False) or \
                       (isinstance(op, ast.IsNot) and val is None):
                        return self.parse_if_condition(node.left)

                    # --- Rule Set 2: Evaluate to 'not A' (Falsy Outcome) ---
                    # 1. A == False
                    # 2. A is False
                    # 3. A != True
                    # 4. A is not True
                    # 5. A is None
                    elif (isinstance(op, (ast.Eq, ast.Is)) and val is False) or \
                         (isinstance(op, (ast.NotEq, ast.IsNot)) and val is True) or \
                         (isinstance(op, ast.Is) and val is None):
                        
                        normalized_left = self.parse_if_condition(node.left)
                        # Strip double negations if nested: e.g., if left was already 'not A' -> 'A'
                        if isinstance(normalized_left, ast.UnaryOp) and isinstance(normalized_left.op, ast.Not):
                            return normalized_left.operand
                        return ast.UnaryOp(op=ast.Not(), operand=normalized_left)
        return node

    def visit_If(self, node, current_path=None):
        effective_path = current_path if current_path is not None else self.path_condition
        if_cond = self.parse_if_condition(node.test)
        cond_str = self.expr_to_str(if_cond)
        
        # Fallback: If expr_to_str returns empty because it's not in supported_features,
        # fallback to trying to read raw source, or fallback to the attribute name string literal.
        if not cond_str:
            if isinstance(node.test, ast.Attribute):
                # Attributes like cfg.camReboot can fall back if the attribute is recognized
                if node.test.attr in self.supported_features:
                    cond_str = node.test.attr
            elif isinstance(node.test, ast.Name):
                # Simple variables only fall back if they are explicitly supported features
                if node.test.id in self.supported_features:
                    cond_str = node.test.id
 
        header_start = node.lineno
        body_start = node.body[0].lineno
        for line in range(header_start, body_start):
            self.conditions[line] = effective_path

        old_path = self.path_condition
        true_path = self.combine_logic(effective_path, cond_str) if cond_str else effective_path
        self.path_condition = true_path
        
        # Ensure all statements in the body are stamped explicitly with the path condition
        for stmt in node.body:
            self.visit(stmt)
            
        if node.orelse:
            if cond_str:
                negated_cond = f"!({cond_str})" if " " in cond_str else f"!{cond_str}"
            else:
                negated_cond = ""

            if negated_cond:
                false_path = self.combine_logic(effective_path, negated_cond)
            else:
                false_path = effective_path

            # FIX: Only treat as an 'elif' chain if the 'if' is the ONLY statement in the else block.
            # If len(node.orelse) > 1, it contains siblings (like an if AND a try block).
            if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
                self.visit_If(node.orelse[0], current_path=false_path)
            else:
                else_body_start = node.orelse[0].lineno
                last_body_line = node.body[-1].end_lineno if hasattr(node.body[-1], 'end_lineno') else node.body[-1].lineno
                
                found_else_line = else_body_start - 1
                for l_idx in range(else_body_start - 1, last_body_line, -1):
                    line_text = self.source_lines[l_idx - 1].strip()
                    if line_text.startswith("else:"):
                        found_else_line = l_idx
                        break
                
                self.conditions[found_else_line] = false_path
                self.path_condition = false_path
                for stmt in node.orelse:
                    self.visit(stmt)
        
        self.path_condition = old_path


    def visit_While(self, node):
        cond_str = self.expr_to_str(node.test)
        for line in range(node.lineno, node.body[0].lineno):
            self.conditions[line] = self.path_condition
        
        old_path = self.path_condition
        self.path_condition = self.combine_logic(old_path, cond_str)
        for stmt in node.body: self.visit(stmt)
        self.path_condition = old_path

    def visit_For(self, node):
        for line in range(node.lineno, node.body[0].lineno):
            self.conditions[line] = self.path_condition
        
        old_path = self.path_condition
        for stmt in node.body: 
            self.visit(stmt)
        self.path_condition = old_path


    def visit_Try(self, node):
        # Map the 'try:' header lines to the current condition path
        for line in range(node.lineno, node.body[0].lineno):
            self.conditions[line] = self.path_condition
        
        old_path = self.path_condition
        # Visit the body statements to process internal nested loops (like our inner 'if')
        for stmt in node.body: 
            self.visit(stmt)
            
        self.path_condition = old_path


    def visit_IfExp(self, node):
        cond_str = self.expr_to_str(node.test)
        # Negate the condition for the else branch
        negated_cond = f"!({cond_str})" if " " in cond_str else f"!{cond_str}" if cond_str else ""
        
        old_path = self.path_condition

        # Handle the "True" branch (body)
        # This is the value BEFORE the 'if'
        t_start = node.body.lineno
        t_end = getattr(node.body, "end_lineno", t_start)
        true_path = self.combine_logic(old_path, cond_str)
        for line in range(t_start, t_end + 1):
            self.conditions[line] = true_path

        # Handle the "False" branch (orelse)
        # This is the value AFTER the 'else'
        f_start = node.orelse.lineno
        f_end = getattr(node.orelse, "end_lineno", f_start)
        false_path = self.combine_logic(old_path, negated_cond)
        for line in range(f_start, f_end + 1):
            self.conditions[line] = false_path
            


    def visit_With(self, node):
        for line in range(node.lineno, node.body[0].lineno):
            self.conditions[line] = self.path_condition

        # Visit everything inside the context body
        old_path = self.path_condition
        for stmt in node.body:
            self.visit(stmt)
        self.path_condition = old_path

    def visit_AsyncWith(self, node):
        for line in range(node.lineno, node.body[0].lineno):
            self.conditions[line] = self.path_condition

        # Visit everything inside the context body
        old_path = self.path_condition
        for stmt in node.body:
            self.visit(stmt)
        self.path_condition = old_path

    # Standard visitors
    def visit_FunctionDef(self, node): self.record(node); self.generic_visit(node)
    def visit_ClassDef(self, node): self.record(node); self.generic_visit(node)
    def visit_Return(self, node): self.record(node)
    def visit_Raise(self, node): self.record(node)
    def visit_Expr(self, node): self.record(node)
    def visit_AugAssign(self, node): self.record(node)


def extract_presence_conditions(code, supported_features, output_file):
    tree = ast.parse(code)
    visitor = PresenceConditionVisitor(supported_features, code)
    visitor.visit(tree)

    # Finalize and write to file
    total_lines = len(code.splitlines())
    visitor.finalize(total_lines)

    with open(output_file, "w") as f:
        # Now we iterate through the filled dictionary
        for i in range(1, total_lines + 1):
            # We can now safely use the dictionary because finalize filled every key
            print(f"{visitor.conditions[i]}", file=f)

