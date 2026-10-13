from __future__ import annotations

import ast
import operator
import re


OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _evaluate(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _evaluate(node.body)
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and type(node.op) in OPS:
        return OPS[type(node.op)](_evaluate(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in OPS:
        left, right = _evaluate(node.left), _evaluate(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 10:
            raise ValueError("expoente muito alto")
        return OPS[type(node.op)](left, right)
    raise ValueError("expressão não permitida")


def extract_expression(text: str) -> str | None:
    clean = text.lower().replace("×", "*").replace("÷", "/").replace(",", ".")
    clean = re.sub(r"^(quanto (é|da)|calcule|calcula|resultado de)\s*", "", clean).strip(" ?")
    if re.fullmatch(r"[\d\s.+\-*/()%]+", clean) and re.search(r"\d", clean):
        return clean
    return None


def calculate(expression: str) -> int | float:
    if len(expression) > 100:
        raise ValueError("expressão muito longa")
    tree = ast.parse(expression, mode="eval")
    result = _evaluate(tree)
    return int(result) if result.is_integer() else round(result, 10)
