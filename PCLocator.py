import ast
import sys
import re

class AdvancedSubstitution(ast.NodeTransformer):
    def __init__(self, source):
        self.source_lines = source.splitlines()
        self.tree = ast.parse(source)
        self.env = {}
        self.func_params = {}
        self.calls = []
        
    def _get_full_name(self, node):
        """Recursively reconstruct names like cfg.camReboot"""
        if isinstance(node, ast.Name):
            return self.env.get(node.id, node.id)
        if isinstance(node, ast.Attribute):
            return f"{self._get_full_name(node.value)}.{node.attr}"
        return None


    def build_map(self):
        for node in ast.walk(self.tree):
            # 1. Map assignments: b = cfg.camReboot
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
                val = self._get_full_name(node.value)
                # ONLY map if we actually found a meaningful substitution string
                if val and val != "None" and val != "":
                    self.env[node.targets[0].id] = val
            
            # 2. Map function signatures
            if isinstance(node, ast.FunctionDef):
                self.func_params[node.name] = [arg.arg for arg in node.args.args]
            
            # 3. Collect calls to link parameters later
            if isinstance(node, ast.Call):
                self.calls.append(node)

        # Link parameters: a -> cfg.camReboot
        for call in self.calls:
            if isinstance(call.func, ast.Name) and call.func.id in self.func_params:
                for i, arg_node in enumerate(call.args):
                    param_name = self.func_params[call.func.id][i]
                    val = self._get_full_name(arg_node)
                    if val: self.env[param_name] = val




    def get_modified_code(self):
        self.build_map()
        modified_lines = []
        sorted_vars = sorted(self.env.keys(), key=len, reverse=True)
        
        for line_text in self.source_lines:
            # SKIP substitution if the line is a function definition header
            if line_text.strip().startswith("def "):
                modified_lines.append(line_text)
                continue
                
            new_line = line_text

            for var in sorted_vars:
                # Use a negative lookbehind (?<!\.) to ensure the variable 
                # isn't preceded by a dot (meaning it's an attribute, not a variable)
                pattern = rf'(?<!\.)\b{var}\b'
                
                def replace_func(match):
                    prefix = new_line[:match.start()]
                    if prefix.count('"') % 2 != 0 or prefix.count("'") % 2 != 0:
                        return match.group(0)
                    return self.env[var]
                
                new_line = re.sub(pattern, replace_func, new_line)
            modified_lines.append(new_line)
            
        return "\n".join(modified_lines)


class PresenceConditionVisitor(ast.NodeVisitor):
    def __init__(self, supported_features, code):
        self.conditions = {}
        self.path_condition = "1"
        self.env = {}
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
        if not new or new in ("1", "!()"): return base
        if base == "1": return new
        
        # Only wrap 'base' or 'new' if they contain an OR operator 
        # to respect Boolean precedence (AND > OR)
        left = f"({base})" if " || " in base else base
        right = f"({new})" if " || " in new else new
        return f"{left} && {right}"

    def expr_to_str(self, expr, target_id=None):
        if expr is None: return ""
        
        # 1. Base Cases (No parens needed)
        if isinstance(expr, ast.Name):
            if expr.id in self.env: return self.env[expr.id]
            if expr.id in self.supported_features: return expr.id
            return expr.id if target_id and expr.id == target_id else ""
        
        if isinstance(expr, ast.Attribute):
            if expr.attr in self.supported_features or (target_id and expr.attr == target_id):
                return expr.attr
            val_str = self.expr_to_str(expr.value, target_id=target_id)
            #return f"{val_str}.{expr.attr}" if val_str else ""
            return f"{val_str}.{expr.attr}" if val_str else ""

        if isinstance(expr, ast.Constant): return str(expr.value)

        # 2. Boolean Logic (Smart Wrapping)
        if isinstance(expr, ast.BoolOp):
            is_or = isinstance(expr.op, ast.Or)
            op_sym = " || " if is_or else " && "
            parts = [v for v in [self.expr_to_str(v) for v in expr.values] if v and v != "1"]
            if not parts: return "1"
            if len(parts) == 1: return parts[0]
            
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
            if not operand or operand == "1": return "1"
            # Wrap only if operand has spaces (meaning it's a compound expression)
            return f"!({operand})" if " " in operand else f"!{operand}"

        # 3. Comparisons (Parens usually safer but optional if simple)

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
            return f"({left} {op_sym} {right})" if left and right else ""

        if isinstance(expr, ast.Call):
            if isinstance(expr.func, ast.Name):
                if expr.func.id == "any" and isinstance(expr.args[0], ast.List):
                    elts = [e for e in [self.expr_to_str(x, target_id=target_id) for x in expr.args[0].elts] if e]
                    return " || ".join(elts) if elts else ""
                if expr.func.id == "range" and target_id:
                    stop = self.expr_to_str(expr.args[0], target_id=target_id)
                    return f"{target_id} < {stop}" if stop else ""
        return ""

    def visit_ImportFrom(self, node):
        self.record(node)
        module_path = node.module if node.module else ""
        for alias in node.names:
            local_name = alias.asname if alias.asname else alias.name
            if alias.name in self.supported_features:
                self.env[local_name] = alias.name
            else:
                self.env[local_name] = f"{module_path}.{alias.name}" if module_path else alias.name
        self.generic_visit(node)

    def visit_Assign(self, node):
        self.record(node)
        if isinstance(node.targets[0], ast.Name):
            self.env[node.targets[0].id] = self.expr_to_str(node.value)
        self.generic_visit(node)

    def visit_If(self, node, current_path=None):
        effective_path = current_path if current_path is not None else self.path_condition
        cond_str = self.expr_to_str(node.test)
        
        header_start = node.lineno
        body_start = node.body[0].lineno
        for line in range(header_start, body_start):
            self.conditions[line] = effective_path

        old_path = self.path_condition
        true_path = self.combine_logic(effective_path, cond_str)
        self.path_condition = true_path
        for stmt in node.body:
            self.visit(stmt)
            
        if node.orelse:
            # Negate: wrap only if cond_str is complex
            negated_cond = f"!({cond_str})" if " " in cond_str else f"!{cond_str}" if cond_str else ""
            false_path = self.combine_logic(effective_path, negated_cond)
            
            if isinstance(node.orelse[0], ast.If):
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
        t_id = node.target.id if isinstance(node.target, (ast.Name, ast.Attribute)) else None
        cond_str = self.expr_to_str(node.iter, target_id=t_id)
        for line in range(node.lineno, node.body[0].lineno):
            self.conditions[line] = self.path_condition
            
        old_path = self.path_condition
        self.path_condition = self.combine_logic(old_path, cond_str)
        for stmt in node.body: self.visit(stmt)
        self.path_condition = old_path

    def visit_Try(self, node):
        for line in range(node.lineno, node.body[0].lineno):
            self.conditions[line] = self.path_condition
            
        old_path = self.path_condition
        accum_excs = []
        
        for stmt in node.body: 
            self.visit(stmt)
        
        for handler in node.handlers:
            # 1. Extract name
            if handler.type is None:
                exc_name = "Exception"
            elif isinstance(handler.type, ast.Name):
                exc_name = handler.type.id
            elif isinstance(handler.type, ast.Attribute):
                parts = []
                curr = handler.type
                while isinstance(curr, ast.Attribute):
                    parts.append(curr.attr)
                    curr = curr.value
                if isinstance(curr, ast.Name): parts.append(curr.id)
                exc_name = ".".join(reversed(parts))
            else:
                exc_name = self.expr_to_str(handler.type)
            
            # 2. Build logic without redundant inner parens
            not_prev_str = " && ".join([f"!{e}" if "." not in e and " " not in e else f"!({e})" for e in accum_excs])
            
            # Logic: (!(Prev)) && Current
            if not_prev_str:
                # not_prev_str already contains &&, so it doesn't need parens when joined with another &&
                current_exc_logic = f"{not_prev_str} && {exc_name}"
            else:
                current_exc_logic = exc_name
            
            h_cond = self.combine_logic(old_path, current_exc_logic)
            
            header_end = handler.body[0].lineno
            for line in range(handler.lineno, header_end):
                self.conditions[line] = h_cond
                
            self.path_condition = h_cond
            for stmt in handler.body: self.visit(stmt)
            accum_excs.append(exc_name)
            
        if node.orelse:
            not_any_exc = " && ".join([f"!{e}" for e in accum_excs])
            else_path = self.combine_logic(old_path, not_any_exc)
            else_keyword_line = node.orelse[0].lineno - 1
            self.conditions[else_keyword_line] = else_path
            self.path_condition = else_path
            for stmt in node.orelse: self.visit(stmt)
            
        self.path_condition = old_path
        if node.finalbody:
            finally_keyword_line = node.finalbody[0].lineno - 1
            self.conditions[finally_keyword_line] = old_path
            for stmt in node.finalbody: self.visit(stmt)

    def visit_IfExp(self, node):
        cond_str = self.expr_to_str(node.test)
        # Negate the condition for the else branch
        negated_cond = f"!({cond_str})" if " " in cond_str else f"!{cond_str}" if cond_str else ""
        
        old_path = self.path_condition

        # 1. Handle the "True" branch (body)
        # This is the value BEFORE the 'if'
        t_start = node.body.lineno
        t_end = getattr(node.body, "end_lineno", t_start)
        true_path = self.combine_logic(old_path, cond_str)
        for line in range(t_start, t_end + 1):
            self.conditions[line] = true_path

        # 2. Handle the "False" branch (orelse)
        # This is the value AFTER the 'else'
        f_start = node.orelse.lineno
        f_end = getattr(node.orelse, "end_lineno", f_start)
        false_path = self.combine_logic(old_path, negated_cond)
        for line in range(f_start, f_end + 1):
            self.conditions[line] = false_path
            
        # We do NOT visit children normally here because we've manually 
        # handled the line mapping for the sub-expressions.

    # Standard visitors
    def visit_FunctionDef(self, node): self.record(node); self.generic_visit(node)
    def visit_ClassDef(self, node): self.record(node); self.generic_visit(node)
    def visit_Return(self, node): self.record(node)
    def visit_Raise(self, node): self.record(node)
    def visit_Expr(self, node): self.record(node)
    def visit_AugAssign(self, node): self.record(node)


def extract_presence_conditions(code, supported_features, output_file):
    # --- FIRST PASS: Substitution ---
    sub_engine = AdvancedSubstitution(code)
    substituted_code = sub_engine.get_modified_code()
    
    # --- SECOND PASS: Logic Analysis ---
    # We parse the SUBSTITUTED code so the AST contains the resolved names
    tree = ast.parse(substituted_code)
    
    # We pass the substituted code strings to the visitor so line indexing matches
    visitor = PresenceConditionVisitor(supported_features, substituted_code)
    visitor.visit(tree)

    # Finalize and write to file
    total_lines = len(substituted_code.splitlines())
    visitor.finalize(total_lines)

    with open(output_file, "w") as f:
        # Now we iterate through the filled dictionary
        for i in range(1, total_lines + 1):
            # We can now safely use the dictionary because finalize filled every key
            # print(f"Line {i}: {visitor.conditions[i]}")
            print(f"{visitor.conditions[i]}", file=f)

#     # Now we iterate through the filled dictionary
#     for i in range(1, total_lines + 1):
#         # We can now safely use the dictionary because finalize filled every key
#         # print(f"Line {i}: {visitor.conditions[i]}")
#         print(f"{visitor.conditions[i]}")


# if __name__ == "__main__":
#     if len(sys.argv) > 1:
#         with open(sys.argv[1], "r") as f:
#             code = f.read()
#         supported_features = []
#         with open(f"code_map/map_ua", "r") as f:
#             lines = f.readlines()
#             for line in lines:
#                 items = line.split()
#                 if len(items) == 2:
#                     supported_features.append(items[1].strip())
#         print(f"supported_features: {supported_features}")
#         extract_presence_conditions(code, supported_features, None)
        
