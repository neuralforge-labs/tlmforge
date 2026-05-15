from src.greeter import greet

def format_greeting(name: str, style: str = "title") -> str:
    g = greet(name)
    if style == "upper":
        return g.upper()
    if style == "lower":
        return g.lower()
    return g.title()
