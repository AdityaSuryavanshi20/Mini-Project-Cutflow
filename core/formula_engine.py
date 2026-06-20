"""
CutFlow – Formula Engine

Provides safe AST-based evaluation for profile and hardware formulas.
Supported variables:
  W, H, n_panels, qty, offset_l, offset_r, offset_t, offset_b
Supported operators:
  +, -, *, /, (), min(), max(), round()

The evaluator rejects unsafe constructs and raises ValueError for invalid formulas.
"""
import ast
from typing import Any, Dict

_ALLOWED_FUNCTIONS = {
    'min': min,
    'max': max,
    'round': round,
}

_ALLOWED_BINARY_OPERATORS = {
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
}

_ALLOWED_UNARY_OPERATORS = {
    ast.UAdd,
    ast.USub,
}

_ALLOWED_NODE_TYPES = {
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Call,
    ast.Name,
    ast.Constant,
    ast.Load,
}


def _normalize_numeric(value: Any) -> Any:
    if isinstance(value, bool):
        raise ValueError('Boolean values are not allowed in formula context')
    if isinstance(value, (int, float)):
        return value
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError(f'Unsupported context value type: {type(value).__name__}')


def _validate_node(node: ast.AST) -> None:
    if type(node) not in _ALLOWED_NODE_TYPES:
        raise ValueError(f'Unsupported syntax in formula: {type(node).__name__}')
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _ALLOWED_FUNCTIONS:
            raise ValueError(f'Unsupported function in formula: {ast.dump(node.func)}')
        for arg in node.args:
            _validate_node(arg)
        if node.keywords:
            raise ValueError('Keyword arguments are not supported in formulas')
    elif isinstance(node, ast.BinOp):
        if type(node.op) not in _ALLOWED_BINARY_OPERATORS:
            raise ValueError(f'Unsupported binary operator: {type(node.op).__name__}')
        _validate_node(node.left)
        _validate_node(node.right)
    elif isinstance(node, ast.UnaryOp):
        if type(node.op) not in _ALLOWED_UNARY_OPERATORS:
            raise ValueError(f'Unsupported unary operator: {type(node.op).__name__}')
        _validate_node(node.operand)
    elif isinstance(node, ast.Name):
        pass
    elif isinstance(node, ast.Constant):
        if not isinstance(node.value, (int, float)):
            raise ValueError(f'Unsupported constant type: {type(node.value).__name__}')
    elif isinstance(node, ast.Expression):
        _validate_node(node.body)
    else:
        raise ValueError(f'Unsupported syntax in formula: {type(node).__name__}')


def _eval_node(node: ast.AST, context: Dict[str, Any]) -> Any:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, context)
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id in context:
            return _normalize_numeric(context[node.id])
        if node.id in _ALLOWED_FUNCTIONS:
            return _ALLOWED_FUNCTIONS[node.id]
        raise ValueError(f"Unknown variable or function: {node.id}")
    if isinstance(node, ast.BinOp):
        left = _eval_node(node.left, context)
        right = _eval_node(node.right, context)
        if type(node.op) is ast.Add:
            return left + right
        if type(node.op) is ast.Sub:
            return left - right
        if type(node.op) is ast.Mult:
            return left * right
        if type(node.op) is ast.Div:
            return left / right
        raise ValueError(f"Unsupported binary operator: {type(node.op).__name__}")
    if isinstance(node, ast.UnaryOp):
        operand = _eval_node(node.operand, context)
        if type(node.op) is ast.UAdd:
            return +operand
        if type(node.op) is ast.USub:
            return -operand
        raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
    if isinstance(node, ast.Call):
        func = _eval_node(node.func, context)
        args = [_eval_node(arg, context) for arg in node.args]
        return func(*args)
    raise ValueError(f'Unsupported expression element: {type(node).__name__}')


def build_formula_context(
    width: int,
    height: int,
    n_panels: int = 1,
    offset_l: int = 0,
    offset_r: int = 0,
    offset_t: int = 0,
    offset_b: int = 0,
    qty: int = 1,
    **extra,
) -> Dict[str, Any]:
    context = {
        'W': width,
        'H': height,
        'n_panels': n_panels,
        'offset_l': offset_l,
        'offset_r': offset_r,
        'offset_t': offset_t,
        'offset_b': offset_b,
        'qty': qty,
    }
    context.update(extra)
    return context


def evaluate_formula(formula: str, context: Dict[str, Any]) -> float:
    if formula is None or not str(formula).strip():
        return 0.0
    expression = str(formula).strip()
    try:
        tree = ast.parse(expression, mode='eval')
    except SyntaxError as exc:
        raise ValueError(f"Syntax error in formula '{expression}': {exc}")
    _validate_node(tree)
    value = _eval_node(tree, context)
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Formula did not resolve to a number: '{expression}' -> {exc}")
